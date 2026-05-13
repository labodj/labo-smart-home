"""Compose a deployment-ready LSH stack config from core and stack contracts."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

from .errors import StackConfigError
from .models import (
    ActorTarget,
    BridgeEnvironmentOverrides,
    BridgeSettings,
    CoordinatorSettings,
    DefineValue,
    JsonObject,
    MqttSettings,
    NetworkClick,
    NodeRedSettings,
    StackConfig,
)

_TOPIC_SUFFIXES = {
    "input": "IN",
    "conf": "conf",
    "state": "state",
    "events": "events",
    "bridge": "bridge",
}
_DEFINE_FLAG_RE = re.compile(r"^-D\s*([A-Za-z_][A-Za-z0-9_]*)(?:=.*)?$")
_DEFINE_VALUE_RE = re.compile(r"^-D\s*([A-Za-z_][A-Za-z0-9_]*)(?:=(.*))?$")
_UINT_LITERAL_RE = re.compile(r"^([0-9]+)U?$")


@dataclass(frozen=True)
class _Actuator:
    name: str
    actuator_id: int


@dataclass(frozen=True)
class _Click:
    device: str
    button: str
    button_id: int
    click_type: Literal["long", "superLong"]


@dataclass
class _WideBridgeFlagState:
    order: list[tuple[str, str]]
    seen_raw: set[str]
    define_values: dict[str, str | None]
    max_define_values: dict[str, int]


def compose_stack(config: StackConfig, core_export: JsonObject) -> JsonObject:
    """Return a deployment config ready for bridge, coordinator and Node-RED."""
    if config.transport.mode != "serial_bridge":
        raise StackConfigError(
            "transport.mode = 'onboard_ethernet' is reserved for future bridgeless firmware."
        )

    stack = copy.deepcopy(core_export)
    if not isinstance(stack, dict):
        raise StackConfigError("core export must be a JSON object.")

    device_names = _device_names(stack)
    protocol = _resolve_mqtt_protocol(config.mqtt, stack)
    system_config = _build_system_config(config.network_clicks, stack, device_names)

    _apply_mqtt_settings(stack, config.mqtt, protocol, device_names)
    _apply_bridge_overrides(stack, config.bridge)
    _apply_bridge_wide_build_flags(stack)
    _apply_coordinator_settings(stack, config.coordinator, system_config)
    _apply_node_red_settings(stack, config.node_red, config.coordinator, system_config)

    stack["schema"] = "lsh-stack-config/v1"
    stack["stackSource"] = str(config.path)
    stack["transport"] = {"mode": config.transport.mode}
    stack["platformio"] = {
        "coreProject": str(config.platformio.core_project)
        if config.platformio.core_project is not None
        else None,
        "bridgeProject": str(config.platformio.bridge_project)
        if config.platformio.bridge_project is not None
        else None,
        "coreExtraScript": str(config.platformio.core_extra_script)
        if config.platformio.core_extra_script is not None
        else None,
        "coreBaseEnv": config.platformio.core_base_env,
        "coreProfiles": [
            {
                "name": profile.name,
                "extends": profile.base_env,
                "default": profile.default,
            }
            for profile in config.platformio.core_profiles
        ],
        "bridgeBaseEnv": config.platformio.bridge_base_env,
        "coreEnvPrefix": config.platformio.core_env_prefix,
        "bridgeEnvPrefix": config.platformio.bridge_env_prefix,
        "bridgeProfiles": [
            {
                "name": profile.name,
                "extends": profile.base_env,
                "default": profile.default,
                "ota": profile.ota,
            }
            for profile in config.platformio.bridge_profiles
        ],
        "corePreferSystemTools": config.platformio.core_prefer_system_tools,
    }
    stack["deploy"] = {
        "bridge": {
            "defaultMethod": config.deploy.bridge.default_method,
            "usbPortTemplate": config.deploy.bridge.usb_port_template,
            "ota": (
                {
                    "brokerHost": config.deploy.bridge.ota.broker_host,
                    "brokerPort": config.deploy.bridge.ota.broker_port,
                    "brokerUsername": config.deploy.bridge.ota.broker_username,
                    "brokerUsernameEnv": config.deploy.bridge.ota.broker_username_env,
                    "brokerPassword": config.deploy.bridge.ota.broker_password,
                    "brokerPasswordEnv": config.deploy.bridge.ota.broker_password_env,
                    "baseTopic": config.deploy.bridge.ota.base_topic,
                    "homieVersion": config.deploy.bridge.ota.homie_version,
                    "timeout": config.deploy.bridge.ota.timeout,
                    "brokerTlsCacert": config.deploy.bridge.ota.broker_tls_cacert,
                    "brokerTlsCertfile": config.deploy.bridge.ota.broker_tls_certfile,
                    "brokerTlsKeyfile": config.deploy.bridge.ota.broker_tls_keyfile,
                    "brokerTlsInsecure": config.deploy.bridge.ota.broker_tls_insecure,
                }
                if config.deploy.bridge.ota is not None
                else None
            ),
            "devices": [
                {
                    "device": target.device,
                    "usbPort": target.usb_port,
                }
                for target in config.deploy.bridge.devices
            ],
        }
    }
    stack["bridgeOverrides"] = _bridge_override_summary(config.bridge)
    stack["externalActors"] = [
        {"name": actor.name, **({"stateKey": actor.state_key} if actor.state_key else {})}
        for actor in config.external_actors
    ]
    stack["mappedNetworkClicks"] = _mapped_click_summary(config.network_clicks)
    return stack


def _apply_bridge_overrides(stack: JsonObject, bridge_settings: BridgeSettings) -> None:
    bridge_devices = _object(
        _object(stack.get("bridge"), "bridge").get("devices"), "bridge.devices"
    )
    for device_key, raw_device in bridge_devices.items():
        device = _object(raw_device, f"bridge.devices.{device_key}")
        flags = _string_list(
            device.get("platformioBuildFlags"),
            f"bridge.devices.{device_key}.platformioBuildFlags",
        )
        device["platformioBuildFlags"] = _merge_bridge_flags(
            flags,
            bridge_settings.defaults,
        )


def _merge_bridge_flags(
    generated_flags: list[str],
    defaults: BridgeEnvironmentOverrides,
) -> list[str]:
    define_values: dict[str, DefineValue] = {
        override.name: override.value for override in defaults.defines
    }

    blocked_names = set(define_values)
    merged = [
        flag
        for flag in generated_flags
        if (define_name := _define_flag_name(flag)) is None or define_name not in blocked_names
    ]
    for name, value in define_values.items():
        flag = _define_override_flag(name, value)
        if flag is not None:
            merged.append(flag)
    merged.extend(defaults.build_flags.append)
    return merged


def _apply_bridge_wide_build_flags(stack: JsonObject) -> None:
    """Collapse per-device bridge limits into one stack-wide firmware profile."""
    bridge = _object(stack.get("bridge"), "bridge")
    bridge_devices = _object(bridge.get("devices"), "bridge.devices")
    flags_by_device: dict[str, list[str]] = {}
    for device_key, raw_device in bridge_devices.items():
        device = _object(raw_device, f"bridge.devices.{device_key}")
        flags_by_device[device_key] = _string_list(
            device.get("platformioBuildFlags"),
            f"bridge.devices.{device_key}.platformioBuildFlags",
        )

    wide_flags = _wide_bridge_flags(flags_by_device)
    bridge["platformioBuildFlags"] = wide_flags
    bridge["buildProfile"] = {
        "mode": "wide",
        "sourceDevices": list(flags_by_device),
        "rule": "CONFIG_MAX_* defines use the maximum value across stack devices.",
    }

    for device_key, raw_device in bridge_devices.items():
        device = _object(raw_device, f"bridge.devices.{device_key}")
        device["platformioBuildFlags"] = list(wide_flags)


def _wide_bridge_flags(flags_by_device: dict[str, list[str]]) -> list[str]:
    state = _WideBridgeFlagState(
        order=[],
        seen_raw=set(),
        define_values={},
        max_define_values={},
    )

    for device, flags in flags_by_device.items():
        for flag in flags:
            _collect_wide_bridge_flag(state, device, flag)

    wide_flags: list[str] = []
    for kind, value in state.order:
        if kind == "raw":
            wide_flags.append(value)
        elif kind == "max_define":
            wide_flags.append(f"-D{value}={state.max_define_values[value]}U")
        else:
            define_value = state.define_values[value]
            wide_flags.append(f"-D{value}" if define_value is None else f"-D{value}={define_value}")
    return wide_flags


def _collect_wide_bridge_flag(state: _WideBridgeFlagState, device: str, flag: str) -> None:
    parsed = _parse_define_flag(flag)
    if parsed is None:
        if flag not in state.seen_raw:
            state.seen_raw.add(flag)
            state.order.append(("raw", flag))
        return

    name, value = parsed
    uint_value = _uint_define_value(value)
    if name.startswith("CONFIG_MAX_") and uint_value is not None:
        if name not in state.max_define_values:
            state.order.append(("max_define", name))
            state.max_define_values[name] = uint_value
        else:
            state.max_define_values[name] = max(state.max_define_values[name], uint_value)
        return

    if name in state.define_values:
        if state.define_values[name] != value:
            raise StackConfigError(
                "bridge devices cannot be collapsed into one wide firmware because "
                f"{name} differs on {device}."
            )
        return

    state.define_values[name] = value
    state.order.append(("define", name))


def _parse_define_flag(flag: str) -> tuple[str, str | None] | None:
    match = _DEFINE_VALUE_RE.fullmatch(flag.strip())
    if match is None:
        return None
    return match.group(1), match.group(2)


def _uint_define_value(value: str | None) -> int | None:
    if value is None:
        return None
    match = _UINT_LITERAL_RE.fullmatch(value.strip())
    return int(match.group(1)) if match is not None else None


def _define_flag_name(flag: str) -> str | None:
    match = _DEFINE_FLAG_RE.fullmatch(flag.strip())
    return match.group(1) if match is not None else None


def _define_override_flag(name: str, value: DefineValue) -> str | None:
    if isinstance(value, bool):
        return f"-D{name}" if value else None
    return f"-D{name}={value}"


def _bridge_override_summary(bridge_settings: BridgeSettings) -> JsonObject:
    return {
        "precedence": [
            "generated bridge flags",
            "bridge.defaults.defines",
            "bridge.defaults.build_flags.append",
        ],
        "defaults": _override_summary(bridge_settings.defaults),
    }


def _override_summary(overrides: BridgeEnvironmentOverrides) -> JsonObject:
    return {
        "defines": {item.name: item.value for item in overrides.defines},
        "buildFlagsAppend": list(overrides.build_flags.append),
    }


def _resolve_mqtt_protocol(mqtt: MqttSettings, stack: JsonObject) -> Literal["json", "msgpack"]:
    if mqtt.codec != "auto":
        return mqtt.codec
    protocol = stack.get("protocol", "json")
    if protocol not in {"json", "msgpack"}:
        raise StackConfigError("core export protocol must be 'json' or 'msgpack'.")
    return cast("Literal['json', 'msgpack']", protocol)


def _apply_mqtt_settings(
    stack: JsonObject,
    mqtt: MqttSettings,
    protocol: Literal["json", "msgpack"],
    device_names: list[str],
) -> None:
    stack["protocol"] = protocol
    stack["lshBasePath"] = mqtt.lsh_base_path
    stack["homieBasePath"] = mqtt.homie_base_path
    stack["serviceTopic"] = mqtt.service_topic

    bridge = _object(stack.get("bridge"), "bridge")
    bridge_devices = _object(bridge.get("devices"), "bridge.devices")
    for device_key, raw_device in bridge_devices.items():
        device = _object(raw_device, f"bridge.devices.{device_key}")
        device_name = _string(device.get("deviceName"), f"bridge.devices.{device_key}.deviceName")
        device["topics"] = _bridge_topics(mqtt, device_name)
        flags = _string_list(
            device.get("platformioBuildFlags"),
            f"bridge.devices.{device_key}.platformioBuildFlags",
        )
        device["platformioBuildFlags"] = _rewrite_bridge_flags(flags, mqtt, protocol)

    coordinator = _object(stack.get("coordinator"), "coordinator")
    options = _object(coordinator.get("options"), "coordinator.options")
    options.update(
        {
            "lshBasePath": mqtt.lsh_base_path,
            "homieBasePath": mqtt.homie_base_path,
            "serviceTopic": mqtt.service_topic,
            "protocol": protocol,
        }
    )
    coordinator["subscriptions"] = _subscriptions(
        mqtt,
        device_names,
        _object(options.get("subscriptionQos"), "coordinator.options.subscriptionQos"),
    )


def _apply_coordinator_settings(
    stack: JsonObject,
    coordinator_settings: CoordinatorSettings,
    system_config: JsonObject,
) -> None:
    coordinator = _object(stack.get("coordinator"), "coordinator")
    options = _object(coordinator.get("options"), "coordinator.options")
    options.update(
        {
            "otherDevicesPrefix": coordinator_settings.other_devices_prefix,
            "clickTimeout": coordinator_settings.click_timeout,
            "clickCleanupInterval": coordinator_settings.click_cleanup_interval,
            "watchdogInterval": coordinator_settings.watchdog_interval,
            "interrogateThreshold": coordinator_settings.interrogate_threshold,
            "pingTimeout": coordinator_settings.ping_timeout,
            "initialStateTimeout": coordinator_settings.initial_state_timeout,
        }
    )
    if coordinator_settings.other_actors_topic is not None:
        options["otherActorsTopic"] = coordinator_settings.other_actors_topic
    coordinator["systemConfig"] = system_config


def _apply_node_red_settings(
    stack: JsonObject,
    node_red: NodeRedSettings,
    coordinator: CoordinatorSettings,
    system_config: JsonObject,
) -> None:
    root = _object(stack.get("nodeRed"), "nodeRed")
    lsh_logic = _object(root.get("lshLogic"), "nodeRed.lshLogic")
    coordinator_options = _object(
        _object(stack.get("coordinator"), "coordinator").get("options"), "coordinator.options"
    )
    lsh_logic.update(
        {
            "homieBasePath": coordinator_options["homieBasePath"],
            "lshBasePath": coordinator_options["lshBasePath"],
            "serviceTopic": coordinator_options["serviceTopic"],
            "protocol": coordinator_options["protocol"],
            "otherDevicesPrefix": coordinator.other_devices_prefix,
            "systemConfigJson": json.dumps(system_config, indent=2),
            "exposeStateContext": node_red.expose_state_context,
            "exposeStateKey": node_red.expose_state_key,
            "exportTopics": node_red.export_topics,
            "exportTopicsKey": node_red.export_topics_key,
            "exposeConfigContext": node_red.expose_config_context,
            "exposeConfigKey": node_red.expose_config_key,
            "otherActorsContext": node_red.other_actors_context,
            "clickTimeout": coordinator.click_timeout,
            "clickCleanupInterval": coordinator.click_cleanup_interval,
            "watchdogInterval": coordinator.watchdog_interval,
            "interrogateThreshold": coordinator.interrogate_threshold,
            "pingTimeout": coordinator.ping_timeout,
            "initialStateTimeout": coordinator.initial_state_timeout,
        }
    )


def _build_system_config(
    network_clicks: tuple[NetworkClick, ...],
    stack: JsonObject,
    device_names: list[str],
) -> JsonObject:
    # The controller contract is authoritative for ids and network-click eligibility;
    # lsh_stack.toml only supplies the orchestration targets attached to those clicks.
    click_index = _network_click_index(stack)
    actuator_index = _actuator_index(stack)
    devices: dict[str, JsonObject] = {name: {"name": name} for name in device_names}
    used_actions: set[tuple[str, str, int]] = set()

    for click in network_clicks:
        click_key = (click.source_device, click.source_button, _core_click_type(click.click_type))
        if click_key not in click_index:
            expected = f"{click.source_device}.{click.source_button} {click.click_type}"
            raise StackConfigError(
                f"{expected} is not declared as network=true in lsh_devices.toml."
            )
        core_click = click_index[click_key]
        action_list = (
            "longClickButtons" if core_click.click_type == "long" else "superLongClickButtons"
        )
        unique_key = (core_click.device, action_list, core_click.button_id)
        if unique_key in used_actions:
            raise StackConfigError(
                f"duplicate action for {core_click.device}.{core_click.button} {click.click_type}."
            )
        used_actions.add(unique_key)

        device_entry = devices[core_click.device]
        actions = cast("list[JsonObject]", device_entry.setdefault(action_list, []))
        action = _button_action(click, core_click, actuator_index)
        actions.append(action)

    return {"devices": list(devices.values())}


def _button_action(
    click: NetworkClick,
    core_click: _Click,
    actuator_index: dict[str, dict[str, _Actuator]],
) -> JsonObject:
    action: JsonObject = {"id": core_click.button_id}
    actors = [_actor_target(target, actuator_index) for target in click.actors]
    if actors:
        action["actors"] = actors
    if click.other_actors:
        action["otherActors"] = list(click.other_actors)
    return action


def _actor_target(
    target: ActorTarget, actuator_index: dict[str, dict[str, _Actuator]]
) -> JsonObject:
    if target.device not in actuator_index:
        raise StackConfigError(f"unknown LSH actor device: {target.device}")

    if target.actuators == "all":
        return {"name": target.device, "allActuators": True, "actuators": []}

    device_actuators = actuator_index[target.device]
    resolved_ids: list[int] = []
    for ref in target.actuators:
        actuator_id = _resolve_actuator_ref(ref, target.device, device_actuators)
        if actuator_id in resolved_ids:
            raise StackConfigError(
                f"duplicate actuator target {actuator_id} on device {target.device}."
            )
        resolved_ids.append(actuator_id)
    return {"name": target.device, "allActuators": False, "actuators": resolved_ids}


def _resolve_actuator_ref(ref: str | int, device: str, actuators: dict[str, _Actuator]) -> int:
    if isinstance(ref, int):
        known_ids = {actuator.actuator_id for actuator in actuators.values()}
        if ref not in known_ids:
            raise StackConfigError(f"unknown actuator id {ref} on device {device}.")
        return ref
    if ref not in actuators:
        raise StackConfigError(f"unknown actuator '{ref}' on device {device}.")
    return actuators[ref].actuator_id


def _network_click_index(
    stack: JsonObject,
) -> dict[tuple[str, str, Literal["long", "superLong"]], _Click]:
    coordinator = _object(stack.get("coordinator"), "coordinator")
    raw_clicks = _list(
        coordinator.get("unmappedNetworkClicks"), "coordinator.unmappedNetworkClicks"
    )
    index: dict[tuple[str, str, Literal["long", "superLong"]], _Click] = {}
    for raw_click in raw_clicks:
        click = _object(raw_click, "coordinator.unmappedNetworkClicks[]")
        click_type = _core_click_type(_string(click.get("clickType"), "clickType"))
        item = _Click(
            device=_string(click.get("device"), "device"),
            button=_string(click.get("button"), "button"),
            button_id=_int(click.get("buttonId"), "buttonId"),
            click_type=click_type,
        )
        index[(item.device, item.button, item.click_type)] = item
    return index


def _actuator_index(stack: JsonObject) -> dict[str, dict[str, _Actuator]]:
    controllers = _object(stack.get("controllers"), "controllers")
    result: dict[str, dict[str, _Actuator]] = {}
    for controller_key, raw_controller in controllers.items():
        controller = _object(raw_controller, f"controllers.{controller_key}")
        device_name = _string(
            controller.get("deviceName"), f"controllers.{controller_key}.deviceName"
        )
        actuators = _list(controller.get("actuators"), f"controllers.{controller_key}.actuators")
        result[device_name] = {}
        for raw_actuator in actuators:
            actuator = _object(raw_actuator, f"controllers.{controller_key}.actuators[]")
            item = _Actuator(
                name=_string(actuator.get("name"), "actuator.name"),
                actuator_id=_int(actuator.get("id"), "actuator.id"),
            )
            result[device_name][item.name] = item
    return result


def _device_names(stack: JsonObject) -> list[str]:
    coordinator = _object(stack.get("coordinator"), "coordinator")
    system_config = _object(coordinator.get("systemConfig"), "coordinator.systemConfig")
    devices = _list(system_config.get("devices"), "coordinator.systemConfig.devices")
    return [
        _string(_object(device, "devices[]").get("name"), "devices[].name") for device in devices
    ]


def _core_click_type(raw: str) -> Literal["long", "superLong"]:
    normalized = "superLong" if raw in {"super_long", "superLong"} else raw
    if normalized not in {"long", "superLong"}:
        raise StackConfigError(f"unsupported click type: {raw}")
    return cast("Literal['long', 'superLong']", normalized)


def _bridge_topics(mqtt: MqttSettings, device_name: str) -> JsonObject:
    prefix = f"{mqtt.lsh_base_path}{device_name}"
    return {
        "input": f"{prefix}/{_TOPIC_SUFFIXES['input']}",
        "conf": f"{prefix}/{_TOPIC_SUFFIXES['conf']}",
        "state": f"{prefix}/{_TOPIC_SUFFIXES['state']}",
        "events": f"{prefix}/{_TOPIC_SUFFIXES['events']}",
        "bridge": f"{prefix}/{_TOPIC_SUFFIXES['bridge']}",
        "service": mqtt.service_topic,
    }


def _subscriptions(mqtt: MqttSettings, device_names: list[str], qos: JsonObject) -> JsonObject:
    subscriptions: JsonObject = {}
    for device_name in device_names:
        prefix = f"{mqtt.lsh_base_path}{device_name}"
        subscriptions[f"{prefix}/conf"] = {"qos": _int(qos.get("conf"), "qos.conf")}
        subscriptions[f"{prefix}/state"] = {"qos": _int(qos.get("state"), "qos.state")}
        subscriptions[f"{prefix}/events"] = {"qos": _int(qos.get("events"), "qos.events")}
        subscriptions[f"{prefix}/bridge"] = {"qos": _int(qos.get("bridge"), "qos.bridge")}
        subscriptions[f"{mqtt.homie_base_path}{device_name}/$state"] = {
            "qos": _int(qos.get("homieState"), "qos.homieState")
        }
    return subscriptions


def _rewrite_bridge_flags(
    flags: list[str],
    mqtt: MqttSettings,
    protocol: Literal["json", "msgpack"],
) -> list[str]:
    # The core export can mirror a reference stack, but the deployment composer owns
    # MQTT-facing choices.  Rewriting these flags prevents serial MsgPack from forcing
    # MQTT MsgPack when the stack intentionally stays on JSON.
    replaced = [
        flag
        for flag in flags
        if not (
            flag.startswith(("-DCONFIG_MQTT_TOPIC_BASE=", "-DCONFIG_MQTT_TOPIC_SERVICE="))
            or flag == "-DCONFIG_MSG_PACK_MQTT"
        )
    ]
    replaced.append(_string_define("CONFIG_MQTT_TOPIC_BASE", mqtt.lsh_base_path.rstrip("/")))
    replaced.append(_string_define("CONFIG_MQTT_TOPIC_SERVICE", mqtt.service_topic))
    if protocol == "msgpack":
        replaced.append("-DCONFIG_MSG_PACK_MQTT")
    return replaced


def _mapped_click_summary(network_clicks: tuple[NetworkClick, ...]) -> list[JsonObject]:
    return [
        {
            "source": f"{click.source_device}.{click.source_button}",
            "type": click.click_type,
            "actors": [
                {
                    "device": actor.device,
                    "actuators": actor.actuators
                    if actor.actuators == "all"
                    else list(actor.actuators),
                }
                for actor in click.actors
            ],
            "otherActors": list(click.other_actors),
        }
        for click in network_clicks
    ]


def _string_define(name: str, value: str) -> str:
    return f'-D{name}=\\"{value}\\"'


def _object(raw: object, path: str) -> JsonObject:
    if not isinstance(raw, dict):
        raise StackConfigError(f"{path} must be a JSON object.")
    return cast("JsonObject", raw)


def _list(raw: object, path: str) -> list[Any]:
    if not isinstance(raw, list):
        raise StackConfigError(f"{path} must be a JSON array.")
    return raw


def _string(raw: object, path: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise StackConfigError(f"{path} must be a non-empty string.")
    return raw


def _string_list(raw: object, path: str) -> list[str]:
    return [_string(item, path) for item in _list(raw, path)]


def _int(raw: object, path: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise StackConfigError(f"{path} must be an integer.")
    return raw
