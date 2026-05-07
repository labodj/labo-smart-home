"""Adapter that asks ``lsh-core`` for its controller-derived stack contract."""
# ruff: noqa: ANN401

from __future__ import annotations

import contextlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from .errors import StackConfigError
from .models import CoreSettings, JsonObject

_TOOL_RELATIVE_PATH = Path("tools/generate_lsh_static_config.py")
_LSH_BASE_PATH = "LSH/"
_HOMIE_BASE_PATH = "homie/5/"
_SERVICE_TOPIC = "LSH/Node-RED/SRV"
_TOPIC_SUFFIX_INPUT = "IN"
_TOPIC_SUFFIX_CONF = "conf"
_TOPIC_SUFFIX_STATE = "state"
_TOPIC_SUFFIX_EVENTS = "events"
_TOPIC_SUFFIX_BRIDGE = "bridge"
_BRIDGE_QOS_POLICY = {
    "deviceCommands": 2,
    "serviceCommands": 1,
    "confPublishes": 1,
    "statePublishes": 1,
    "eventsPublishes": 2,
    "bridgePublishes": 1,
}
_COORDINATOR_SUBSCRIPTION_QOS = {
    _TOPIC_SUFFIX_CONF: 2,
    _TOPIC_SUFFIX_STATE: 2,
    _TOPIC_SUFFIX_EVENTS: 2,
    _TOPIC_SUFFIX_BRIDGE: 2,
    "homieState": 1,
}
_CORE_TO_BRIDGE_DEFINE_MAP = {
    "CONFIG_COM_SERIAL_BAUD": "CONFIG_ARDCOM_SERIAL_BAUD",
    "CONFIG_COM_SERIAL_TIMEOUT_MS": "CONFIG_ARDCOM_SERIAL_TIMEOUT_MS",
    "CONFIG_COM_SERIAL_MSGPACK_FRAME_IDLE_TIMEOUT_MS": (
        "CONFIG_ARDCOM_SERIAL_MSGPACK_FRAME_IDLE_TIMEOUT_MS"
    ),
    "CONFIG_COM_SERIAL_MAX_RX_BYTES_PER_LOOP": "CONFIG_ARDCOM_SERIAL_MAX_RX_BYTES_PER_LOOP",
    "CONFIG_CONNECTION_TIMEOUT_MS": "CONFIG_CONNECTION_TIMEOUT_CONTROLLINO_MS",
    "CONFIG_BRIDGE_BOOT_RETRY_INTERVAL_MS": "CONFIG_BOOTSTRAP_REQUEST_INTERVAL_MS",
}
_CORE_DEFAULT_TIMING_DEFINES = {
    "CONFIG_COM_SERIAL_BAUD": "250000",
    "CONFIG_COM_SERIAL_TIMEOUT_MS": "5",
    "CONFIG_BRIDGE_BOOT_RETRY_INTERVAL_MS": "250",
}


def load_core_export(core: CoreSettings, *, override_tool: Path | None = None) -> JsonObject:
    """Run the lsh-core generator and return its machine-readable export."""
    tool = _resolve_core_tool(core, override_tool=override_tool)
    args = [
        sys.executable,
        str(tool),
        str(core.devices),
        "--print-stack-config",
    ]
    for device in core.selected_devices:
        args.extend(("--device", device))

    try:
        completed = subprocess.run(  # noqa: S603 - the explicit tool path is validated first.
            args,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise StackConfigError(f"cannot run lsh-core generator at {tool}: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if _missing_stack_export_flag(detail):
            return _load_core_export_from_python_api(core, tool, detail)
        raise StackConfigError(f"lsh-core generator failed: {detail}")

    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise StackConfigError(f"lsh-core generator did not return valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise StackConfigError("lsh-core generator returned a non-object JSON value.")
    return parsed


def _missing_stack_export_flag(detail: str) -> bool:
    return "--print-stack-config" in detail and "unrecognized arguments" in detail


def _load_core_export_from_python_api(
    core: CoreSettings,
    tool: Path,
    cli_error: str,
) -> JsonObject:
    """Build the stack export through older lsh-core packages without CLI support."""
    package_root = tool.resolve().parents[1]
    sys.path.insert(0, str(package_root))
    try:
        api = cast("Any", importlib.import_module("tools.lsh_static_config"))
        profile = cast("Any", importlib.import_module("tools.lsh_static_config.profile"))
        project = api.parse_project(core.devices)
        selected_devices = _selected_device_keys(project, core.selected_devices)
        return _build_stack_export(api, profile, project, selected_devices)
    except Exception as exc:
        raise StackConfigError(
            "lsh-core generator does not support --print-stack-config and the "
            f"Python API fallback failed: {exc}. Original generator error: {cli_error}"
        ) from exc
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(package_root))


def _selected_device_keys(project: Any, requested_devices: tuple[str, ...]) -> list[str]:
    devices = cast("dict[str, Any]", project.devices)
    if not requested_devices:
        return list(devices)

    selected: list[str] = []
    for requested in requested_devices:
        key = requested.lower()
        if key in devices:
            selected.append(key)
            continue
        for device_key, device in devices.items():
            if requested == device.device_name:
                selected.append(device_key)
                break
        else:
            choices = ", ".join(devices)
            raise StackConfigError(
                f"unknown lsh-core device {requested!r}. Available devices: {choices}."
            )
    return selected


def _build_stack_export(
    api: Any,
    profile: Any,
    project: Any,
    selected_devices: list[str],
) -> JsonObject:
    devices = [project.devices[device_key] for device_key in selected_devices]
    mqtt_protocol = _stack_mqtt_protocol(api, project, devices)
    device_exports = [
        _device_stack_export(api, profile, project, device, mqtt_protocol) for device in devices
    ]
    unmapped_network_clicks = [
        click
        for device_export in device_exports
        for click in cast("dict[str, Any]", device_export["coordinator"])["unmappedNetworkClicks"]
    ]
    system_devices = [{"name": device.device_name} for device in devices]
    return {
        "schema": "lsh-stack-config/v1",
        "source": str(project.source_path),
        "lshBasePath": _LSH_BASE_PATH,
        "homieBasePath": _HOMIE_BASE_PATH,
        "serviceTopic": _SERVICE_TOPIC,
        "protocol": mqtt_protocol,
        "qosPolicy": {
            "bridge": dict(_BRIDGE_QOS_POLICY),
            "coordinatorSubscriptions": dict(_COORDINATOR_SUBSCRIPTION_QOS),
        },
        "bridge": {
            "devices": {
                str(device_export["key"]): device_export["bridge"]
                for device_export in device_exports
            },
        },
        "controllers": {
            str(device_export["key"]): device_export["controller"]
            for device_export in device_exports
        },
        "coordinator": {
            "options": {
                "lshBasePath": _LSH_BASE_PATH,
                "homieBasePath": _HOMIE_BASE_PATH,
                "serviceTopic": _SERVICE_TOPIC,
                "protocol": mqtt_protocol,
                "subscriptionQos": dict(_COORDINATOR_SUBSCRIPTION_QOS),
            },
            "systemConfig": {"devices": system_devices},
            "subscriptions": _coordinator_subscriptions(devices),
            "unmappedNetworkClicks": unmapped_network_clicks,
        },
        "nodeRed": {
            "lshLogic": {
                "protocol": mqtt_protocol,
                "systemConfigJson": json.dumps({"devices": system_devices}, indent=2),
            },
        },
        "footprint": {
            str(device_export["key"]): device_export["footprint"]
            for device_export in device_exports
        },
    }


def _device_stack_export(
    api: Any,
    profile: Any,
    project: Any,
    device: Any,
    mqtt_protocol: str,
) -> JsonObject:
    return {
        "key": device.key,
        "bridge": {
            "deviceName": device.device_name,
            "platformioBuildFlags": _bridge_build_flags(api, project, device, mqtt_protocol),
            "topics": _bridge_topics(device.device_name),
        },
        "controller": _controller_contract(device),
        "coordinator": {
            "device": {"name": device.device_name},
            "unmappedNetworkClicks": _network_click_placeholders(device),
        },
        "footprint": _footprint(profile, device),
    }


def _stack_mqtt_protocol(api: Any, project: Any, devices: list[Any]) -> str:
    uses_msgpack = any("CONFIG_MSG_PACK" in _define_map(api, project, device) for device in devices)
    return "msgpack" if uses_msgpack else "json"


def _define_map(api: Any, project: Any, device: Any) -> dict[str, str | None]:
    return {define.name: define.value for define in api.merged_defines(project, device)}


def _bridge_build_flags(api: Any, project: Any, device: Any, mqtt_protocol: str) -> list[str]:
    define_value = api.DefineValue
    render_define = api.render_escaped_build_flag_define
    defines = _define_map(api, project, device)
    bridge_defines = [
        define_value("CONFIG_MAX_ACTUATORS", _uint_literal(len(device.actuators))),
        define_value("CONFIG_MAX_BUTTONS", _uint_literal(len(device.clickables))),
        define_value("CONFIG_MAX_NAME_LENGTH", _uint_literal(len(device.device_name))),
        define_value("CONFIG_MQTT_TOPIC_BASE", _quoted(_LSH_BASE_PATH.rstrip("/"))),
        define_value("CONFIG_MQTT_TOPIC_INPUT", _quoted(_TOPIC_SUFFIX_INPUT)),
        define_value("CONFIG_MQTT_TOPIC_STATE", _quoted(_TOPIC_SUFFIX_STATE)),
        define_value("CONFIG_MQTT_TOPIC_CONF", _quoted(_TOPIC_SUFFIX_CONF)),
        define_value("CONFIG_MQTT_TOPIC_EVENTS", _quoted(_TOPIC_SUFFIX_EVENTS)),
        define_value("CONFIG_MQTT_TOPIC_BRIDGE", _quoted(_TOPIC_SUFFIX_BRIDGE)),
        define_value("CONFIG_MQTT_TOPIC_SERVICE", _quoted(_SERVICE_TOPIC)),
        define_value(
            "CONFIG_MQTT_QOS_DEVICE_COMMANDS",
            _uint_literal(_BRIDGE_QOS_POLICY["deviceCommands"]),
        ),
        define_value(
            "CONFIG_MQTT_QOS_SERVICE_COMMANDS",
            _uint_literal(_BRIDGE_QOS_POLICY["serviceCommands"]),
        ),
        define_value("CONFIG_MQTT_QOS_CONF", _uint_literal(_BRIDGE_QOS_POLICY["confPublishes"])),
        define_value("CONFIG_MQTT_QOS_STATE", _uint_literal(_BRIDGE_QOS_POLICY["statePublishes"])),
        define_value(
            "CONFIG_MQTT_QOS_EVENTS", _uint_literal(_BRIDGE_QOS_POLICY["eventsPublishes"])
        ),
        define_value(
            "CONFIG_MQTT_QOS_BRIDGE", _uint_literal(_BRIDGE_QOS_POLICY["bridgePublishes"])
        ),
    ]
    for core_define, bridge_define in _CORE_TO_BRIDGE_DEFINE_MAP.items():
        value = defines.get(core_define, _CORE_DEFAULT_TIMING_DEFINES.get(core_define))
        if value is not None:
            bridge_defines.append(define_value(bridge_define, _uint_literal(value)))
    if "CONFIG_MSG_PACK" in defines:
        bridge_defines.append(define_value("CONFIG_MSG_PACK_ARDUINO"))
    if mqtt_protocol == "msgpack":
        bridge_defines.append(define_value("CONFIG_MSG_PACK_MQTT"))
    return [render_define(define) for define in bridge_defines]


def _controller_contract(device: Any) -> JsonObject:
    return {
        "deviceName": device.device_name,
        "actuators": [
            {"name": actuator.name, "id": actuator.actuator_id} for actuator in device.actuators
        ],
        "buttons": [
            {"name": clickable.name, "id": clickable.clickable_id}
            for clickable in device.clickables
        ],
        "indicators": [{"name": indicator.name} for indicator in device.indicators],
    }


def _coordinator_subscriptions(devices: list[Any]) -> JsonObject:
    subscriptions: JsonObject = {}
    for device in devices:
        prefix = f"{_LSH_BASE_PATH}{device.device_name}"
        subscriptions[f"{prefix}/{_TOPIC_SUFFIX_CONF}"] = {
            "qos": _COORDINATOR_SUBSCRIPTION_QOS[_TOPIC_SUFFIX_CONF],
        }
        subscriptions[f"{prefix}/{_TOPIC_SUFFIX_STATE}"] = {
            "qos": _COORDINATOR_SUBSCRIPTION_QOS[_TOPIC_SUFFIX_STATE],
        }
        subscriptions[f"{prefix}/{_TOPIC_SUFFIX_EVENTS}"] = {
            "qos": _COORDINATOR_SUBSCRIPTION_QOS[_TOPIC_SUFFIX_EVENTS],
        }
        subscriptions[f"{prefix}/{_TOPIC_SUFFIX_BRIDGE}"] = {
            "qos": _COORDINATOR_SUBSCRIPTION_QOS[_TOPIC_SUFFIX_BRIDGE],
        }
        subscriptions[f"{_HOMIE_BASE_PATH}{device.device_name}/$state"] = {
            "qos": _COORDINATOR_SUBSCRIPTION_QOS["homieState"],
        }
    return subscriptions


def _bridge_topics(device_name: str) -> JsonObject:
    prefix = f"{_LSH_BASE_PATH}{device_name}"
    return {
        "input": f"{prefix}/{_TOPIC_SUFFIX_INPUT}",
        "conf": f"{prefix}/{_TOPIC_SUFFIX_CONF}",
        "state": f"{prefix}/{_TOPIC_SUFFIX_STATE}",
        "events": f"{prefix}/{_TOPIC_SUFFIX_EVENTS}",
        "bridge": f"{prefix}/{_TOPIC_SUFFIX_BRIDGE}",
        "service": _SERVICE_TOPIC,
    }


def _network_click_placeholders(device: Any) -> list[JsonObject]:
    clicks: list[JsonObject] = []
    for clickable in device.clickables:
        if clickable.long.enabled and clickable.long.network:
            clicks.append(
                {
                    "device": device.device_name,
                    "buttonId": clickable.clickable_id,
                    "button": clickable.name,
                    "clickType": "long",
                }
            )
        if clickable.super_long.enabled and clickable.super_long.network:
            clicks.append(
                {
                    "device": device.device_name,
                    "buttonId": clickable.clickable_id,
                    "button": clickable.name,
                    "clickType": "superLong",
                }
            )
    return clicks


def _footprint(profile: Any, device: Any) -> JsonObject:
    profile_data = profile.collect_static_profile_data(device)
    packed_state_bytes = (len(device.actuators) + 7) >> 3
    auto_off_bytes = len(profile_data.auto_off_indexes) * 4
    pulse_bytes = len(profile_data.pulse_indexes) * 2
    network_click_bytes = len(profile_data.network_click_slots) * 6
    interlock_edges = sum(len(actuator.interlock_targets) for actuator in device.actuators)
    return {
        "actuators": len(device.actuators),
        "buttons": len(device.clickables),
        "indicators": len(device.indicators),
        "packedStateBytes": packed_state_bytes,
        "networkClickSlots": len(profile_data.network_click_slots),
        "autoOffActuators": len(profile_data.auto_off_indexes),
        "pulseActuators": len(profile_data.pulse_indexes),
        "interlockEdges": interlock_edges,
        "shortLinks": profile_data.short_links,
        "longLinks": profile_data.long_links,
        "superLongLinks": profile_data.super_long_links,
        "indicatorLinks": profile_data.indicator_links,
        "estimatedCoreDynamicBytes": (
            packed_state_bytes + auto_off_bytes + pulse_bytes + network_click_bytes
        ),
    }


def _quoted(value: str) -> str:
    return f'"{value}"'


def _uint_literal(value: object) -> str:
    text = str(value).strip()
    if text.endswith(("U", "u")):
        text = text[:-1]
    return f"{int(text)}U"


def _resolve_core_tool(core: CoreSettings, *, override_tool: Path | None) -> Path:
    if override_tool is not None:
        return _existing_tool(override_tool)
    if core.tool is not None:
        return _existing_tool(core.tool)

    env_tool = os.environ.get("LSH_CORE_TOOL")
    if env_tool:
        return _existing_tool(Path(env_tool).expanduser())

    # The common public and personal setup keeps lsh-core next to the project
    # that owns lsh_stack.toml or installs it through PlatformIO libdeps.  Try a
    # small, deterministic set of locations before asking for an explicit path.
    candidates = (
        *_installed_lsh_core_tools(core.devices.parent),
        core.devices.parent.parent / "lsh-core" / _TOOL_RELATIVE_PATH,
        Path.cwd() / "lsh-core" / _TOOL_RELATIVE_PATH,
        Path.cwd().parent / "lsh-core" / _TOOL_RELATIVE_PATH,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise StackConfigError(
        "cannot find lsh-core generator. Build the core PlatformIO project once from "
        "the IDE or CLI so dependencies are installed, set core.tool in lsh_stack.toml "
        "or set LSH_CORE_TOOL."
    )


def _installed_lsh_core_tools(project_dir: Path) -> tuple[Path, ...]:
    libdeps = project_dir / ".pio" / "libdeps"
    return tuple(sorted(libdeps.glob("*/lsh-core/tools/generate_lsh_static_config.py")))


def _existing_tool(path: Path) -> Path:
    candidate = path.resolve()
    if not candidate.is_file():
        raise StackConfigError(f"lsh-core generator not found: {candidate}")
    return candidate
