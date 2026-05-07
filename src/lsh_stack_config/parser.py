"""Strict TOML parser for ``lsh_stack.toml``."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Literal, NoReturn, cast

from .errors import StackConfigError
from .models import (
    ActorTarget,
    ActuatorRef,
    BridgeBuildFlagOverrides,
    BridgeDeploySettings,
    BridgeDeployTarget,
    BridgeEnvironmentOverrides,
    BridgeOtaSettings,
    BridgeProfileSettings,
    BridgeSettings,
    ContextTarget,
    CoordinatorSettings,
    CoreSettings,
    DefineOverride,
    DefineValue,
    DeploySettings,
    ExternalActor,
    HomieVersion,
    MqttCodec,
    MqttSettings,
    NetworkClick,
    NodeRedSettings,
    PlatformioSettings,
    StackConfig,
    TransportMode,
    TransportSettings,
    UploadMethod,
)

TomlTable = dict[str, object]

_DURATION_RE = re.compile(r"^(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<unit>ms|s|m|h)$")
_CONTEXT_VALUES = {"none", "flow", "global"}
_NODE_RED_ACTOR_CONTEXT_VALUES = {"flow", "global"}
_MQTT_CODECS = {"auto", "json", "msgpack"}
_HOMIE_VERSIONS = {"3", "4", "5"}
_TRANSPORT_MODES = {"serial_bridge", "onboard_ethernet"}
_CLICK_TYPES = {"long", "super_long"}
_UPLOAD_METHODS = {"usb", "ota"}
_DEFINE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOURCE_PART_COUNT = 2
_UINT8_MAX = 255


def load_stack_config(path: Path) -> StackConfig:
    """Load and normalize a stack TOML file."""
    source = path.resolve()
    try:
        with source.open("rb") as handle:
            raw = tomllib.load(handle)
    except OSError as exc:
        _fail(f"cannot read {source}: {exc}")
    except tomllib.TOMLDecodeError as exc:
        _fail(f"{source} is not valid TOML: {exc}")

    _reject_unknown(
        raw,
        {
            "schema_version",
            "core",
            "transport",
            "mqtt",
            "coordinator",
            "node_red",
            "platformio",
            "deploy",
            "bridge",
            "external_actors",
            "network_clicks",
        },
        "root",
    )
    schema_version = _int(raw.get("schema_version", 1), "schema_version", minimum=1)
    if schema_version != 1:
        _fail("schema_version must be 1.")

    return StackConfig(
        path=source,
        schema_version=schema_version,
        core=_parse_core(_table(raw.get("core", {}), "core"), source.parent),
        transport=_parse_transport(_table(raw.get("transport", {}), "transport")),
        mqtt=_parse_mqtt(_table(raw.get("mqtt", {}), "mqtt")),
        coordinator=_parse_coordinator(_table(raw.get("coordinator", {}), "coordinator")),
        node_red=_parse_node_red(_table(raw.get("node_red", {}), "node_red")),
        platformio=_parse_platformio(
            _table(raw.get("platformio", {}), "platformio"),
            source.parent,
        ),
        deploy=_parse_deploy(_table(raw.get("deploy", {}), "deploy")),
        bridge=_parse_bridge(_table(raw.get("bridge", {}), "bridge")),
        external_actors=_parse_external_actors(
            _table(raw.get("external_actors", {}), "external_actors")
        ),
        network_clicks=_parse_network_clicks(raw.get("network_clicks", [])),
    )


def _parse_core(table: TomlTable, base_dir: Path) -> CoreSettings:
    _reject_unknown(table, {"devices", "tool", "selected_devices"}, "core")
    devices = _path(table.get("devices", "lsh_devices.toml"), "core.devices", base_dir)
    tool = (
        _path(table["tool"], "core.tool", base_dir)
        if "tool" in table and table["tool"] is not None
        else None
    )
    selected_devices = tuple(
        _string_list(table.get("selected_devices", []), "core.selected_devices")
    )
    return CoreSettings(devices=devices, tool=tool, selected_devices=selected_devices)


def _parse_transport(table: TomlTable) -> TransportSettings:
    _reject_unknown(table, {"mode"}, "transport")
    mode = _choice(table.get("mode", "serial_bridge"), _TRANSPORT_MODES, "transport.mode")
    return TransportSettings(mode=cast("TransportMode", mode))


def _parse_mqtt(table: TomlTable) -> MqttSettings:
    _reject_unknown(table, {"codec", "lsh_base_path", "homie_base_path", "service_topic"}, "mqtt")
    codec = _choice(table.get("codec", "auto"), _MQTT_CODECS, "mqtt.codec")
    lsh_base_path = _topic_base(table.get("lsh_base_path", "LSH/"), "mqtt.lsh_base_path")
    homie_base_path = _topic_base(table.get("homie_base_path", "homie/5/"), "mqtt.homie_base_path")
    service_topic = _concrete_topic(
        table.get("service_topic", "LSH/Node-RED/SRV"), "mqtt.service_topic"
    )
    return MqttSettings(
        codec=cast("MqttCodec", codec),
        lsh_base_path=lsh_base_path,
        homie_base_path=homie_base_path,
        service_topic=service_topic,
    )


def _parse_coordinator(table: TomlTable) -> CoordinatorSettings:
    _reject_unknown(
        table,
        {
            "other_devices_prefix",
            "click_timeout",
            "click_cleanup_interval",
            "watchdog_interval",
            "interrogate_threshold",
            "ping_timeout",
            "initial_state_timeout",
            "other_actors_topic",
        },
        "coordinator",
    )
    other_actors_topic = (
        _concrete_topic(table["other_actors_topic"], "coordinator.other_actors_topic")
        if "other_actors_topic" in table and table["other_actors_topic"] is not None
        else None
    )
    return CoordinatorSettings(
        other_devices_prefix=_required_string(
            table.get("other_devices_prefix", "other_devices"),
            "coordinator.other_devices_prefix",
        ),
        click_timeout=_duration_seconds(table.get("click_timeout", 2), "coordinator.click_timeout"),
        click_cleanup_interval=_duration_seconds(
            table.get("click_cleanup_interval", 30),
            "coordinator.click_cleanup_interval",
        ),
        watchdog_interval=_duration_seconds(
            table.get("watchdog_interval", 60),
            "coordinator.watchdog_interval",
        ),
        interrogate_threshold=_duration_seconds(
            table.get("interrogate_threshold", 120),
            "coordinator.interrogate_threshold",
        ),
        ping_timeout=_duration_seconds(table.get("ping_timeout", 3), "coordinator.ping_timeout"),
        initial_state_timeout=_duration_seconds(
            table.get("initial_state_timeout", 2),
            "coordinator.initial_state_timeout",
        ),
        other_actors_topic=other_actors_topic,
    )


def _parse_node_red(table: TomlTable) -> NodeRedSettings:
    _reject_unknown(
        table,
        {
            "expose_state_context",
            "expose_state_key",
            "export_topics",
            "export_topics_key",
            "expose_config_context",
            "expose_config_key",
            "other_actors_context",
        },
        "node_red",
    )
    return NodeRedSettings(
        expose_state_context=_context(
            table.get("expose_state_context", "global"),
            "node_red.expose_state_context",
        ),
        expose_state_key=_required_string(
            table.get("expose_state_key", "lsh_state"),
            "node_red.expose_state_key",
        ),
        export_topics=_context(table.get("export_topics", "flow"), "node_red.export_topics"),
        export_topics_key=_required_string(
            table.get("export_topics_key", "lsh_topics"),
            "node_red.export_topics_key",
        ),
        expose_config_context=_context(
            table.get("expose_config_context", "global"),
            "node_red.expose_config_context",
        ),
        expose_config_key=_required_string(
            table.get("expose_config_key", "lsh_config"),
            "node_red.expose_config_key",
        ),
        other_actors_context=cast(
            "Literal['flow', 'global']",
            _choice(
                table.get("other_actors_context", "global"),
                _NODE_RED_ACTOR_CONTEXT_VALUES,
                "node_red.other_actors_context",
            ),
        ),
    )


def _parse_platformio(table: TomlTable, base_dir: Path) -> PlatformioSettings:
    _reject_unknown(
        table,
        {
            "core_project",
            "bridge_project",
            "core_extra_script",
            "core_base_env",
            "bridge_base_env",
            "core_env_prefix",
            "bridge_env_prefix",
            "bridge_profiles",
        },
        "platformio",
    )
    bridge_profiles = tuple(
        _parse_bridge_profile(raw_profile, index)
        for index, raw_profile in enumerate(
            _array(table.get("bridge_profiles", []), "platformio.bridge_profiles")
        )
    )
    default_profiles = [profile.name for profile in bridge_profiles if profile.default]
    if len(default_profiles) > 1:
        defaults = ", ".join(default_profiles)
        _fail(f"only one platformio.bridge_profiles entry can set default = true: {defaults}.")
    return PlatformioSettings(
        core_project=(
            _path(table["core_project"], "platformio.core_project", base_dir)
            if "core_project" in table and table["core_project"] is not None
            else None
        ),
        bridge_project=(
            _path(table["bridge_project"], "platformio.bridge_project", base_dir)
            if "bridge_project" in table and table["bridge_project"] is not None
            else None
        ),
        core_extra_script=(
            _path(table["core_extra_script"], "platformio.core_extra_script", base_dir)
            if "core_extra_script" in table and table["core_extra_script"] is not None
            else None
        ),
        core_base_env=_required_string(
            table.get("core_base_env", "env:release"),
            "platformio.core_base_env",
        ),
        bridge_base_env=_required_string(
            table.get("bridge_base_env", "env:release"),
            "platformio.bridge_base_env",
        ),
        core_env_prefix=_required_string(
            table.get("core_env_prefix", "core"), "platformio.core_env_prefix"
        ),
        bridge_env_prefix=_required_string(
            table.get("bridge_env_prefix", "bridge"), "platformio.bridge_env_prefix"
        ),
        bridge_profiles=bridge_profiles,
    )


def _parse_bridge_profile(raw: object, index: int) -> BridgeProfileSettings:
    path = f"platformio.bridge_profiles[{index}]"
    table = _table(raw, path)
    _reject_unknown(table, {"name", "extends", "default", "ota"}, path)
    name = _required_string(table.get("name"), f"{path}.name")
    if name in {"usb", "ota", "batch", "all"}:
        _fail(f"{path}.name is reserved.")
    return BridgeProfileSettings(
        name=name,
        base_env=_required_string(table.get("extends"), f"{path}.extends"),
        default=_bool(table.get("default", False), f"{path}.default"),
        ota=_bool(table.get("ota", True), f"{path}.ota"),
    )


def _parse_deploy(table: TomlTable) -> DeploySettings:
    _reject_unknown(table, {"bridge"}, "deploy")
    return DeploySettings(
        bridge=_parse_bridge_deploy(_table(table.get("bridge", {}), "deploy.bridge"))
    )


def _parse_bridge_deploy(table: TomlTable) -> BridgeDeploySettings:
    _reject_unknown(
        table,
        {
            "default_method",
            "usb_port_template",
            "ota_command_template",
            "ota",
            "devices",
        },
        "deploy.bridge",
    )
    raw_devices = _table(table.get("devices", {}), "deploy.bridge.devices")
    devices: list[BridgeDeployTarget] = []
    for device, raw_target in raw_devices.items():
        target = _table(raw_target, f"deploy.bridge.devices.{device}")
        _reject_unknown(
            target,
            {"usb_port", "ota_command"},
            f"deploy.bridge.devices.{device}",
        )
        devices.append(
            BridgeDeployTarget(
                device=_required_string(device, f"deploy.bridge.devices.{device}"),
                usb_port=(
                    _required_string(target["usb_port"], f"deploy.bridge.devices.{device}.usb_port")
                    if "usb_port" in target
                    else None
                ),
                ota_command=(
                    _required_string(
                        target["ota_command"],
                        f"deploy.bridge.devices.{device}.ota_command",
                    )
                    if "ota_command" in target
                    else None
                ),
            )
        )
    return BridgeDeploySettings(
        default_method=cast(
            "UploadMethod",
            _choice(
                table.get("default_method", "usb"),
                _UPLOAD_METHODS,
                "deploy.bridge.default_method",
            ),
        ),
        usb_port_template=(
            _required_string(table["usb_port_template"], "deploy.bridge.usb_port_template")
            if "usb_port_template" in table and table["usb_port_template"] is not None
            else None
        ),
        ota_command_template=(
            _required_string(table["ota_command_template"], "deploy.bridge.ota_command_template")
            if "ota_command_template" in table and table["ota_command_template"] is not None
            else None
        ),
        ota=(
            _parse_bridge_ota(_table(table["ota"], "deploy.bridge.ota"))
            if "ota" in table and table["ota"] is not None
            else None
        ),
        devices=tuple(devices),
    )


def _parse_bridge_ota(table: TomlTable) -> BridgeOtaSettings:
    _reject_unknown(
        table,
        {
            "script",
            "python",
            "broker_host",
            "broker_port",
            "broker_username",
            "broker_username_env",
            "broker_password",
            "broker_password_env",
            "base_topic",
            "homie_version",
            "timeout",
            "broker_tls_cacert",
            "broker_tls_certfile",
            "broker_tls_keyfile",
            "broker_tls_insecure",
            "extra_args",
        },
        "deploy.bridge.ota",
    )
    broker_username = _optional_string(table, "broker_username", "deploy.bridge.ota")
    broker_username_env = _optional_env_var(table, "broker_username_env", "deploy.bridge.ota")
    broker_password = _optional_string(table, "broker_password", "deploy.bridge.ota")
    broker_password_env = _optional_env_var(table, "broker_password_env", "deploy.bridge.ota")
    broker_tls_certfile = _optional_string(table, "broker_tls_certfile", "deploy.bridge.ota")
    broker_tls_keyfile = _optional_string(table, "broker_tls_keyfile", "deploy.bridge.ota")
    if broker_username is not None and broker_username_env is not None:
        _fail("deploy.bridge.ota cannot set both broker_username and broker_username_env.")
    if broker_password is not None and broker_password_env is not None:
        _fail("deploy.bridge.ota cannot set both broker_password and broker_password_env.")
    if (broker_password is not None or broker_password_env is not None) and (
        broker_username is None and broker_username_env is None
    ):
        _fail("deploy.bridge.ota broker_password requires broker_username or broker_username_env.")
    if broker_tls_keyfile is not None and broker_tls_certfile is None:
        _fail("deploy.bridge.ota broker_tls_keyfile requires broker_tls_certfile.")
    return BridgeOtaSettings(
        script=_optional_string(table, "script", "deploy.bridge.ota"),
        python=_optional_string(table, "python", "deploy.bridge.ota") or "python",
        broker_host=_optional_string(table, "broker_host", "deploy.bridge.ota"),
        broker_port=(
            _int(table["broker_port"], "deploy.bridge.ota.broker_port", minimum=1)
            if "broker_port" in table
            else None
        ),
        broker_username=broker_username,
        broker_username_env=broker_username_env,
        broker_password=broker_password,
        broker_password_env=broker_password_env,
        base_topic=(
            _topic_base(table["base_topic"], "deploy.bridge.ota.base_topic")
            if "base_topic" in table
            else None
        ),
        homie_version=cast(
            "HomieVersion",
            _choice(
                table.get("homie_version", "5"), _HOMIE_VERSIONS, "deploy.bridge.ota.homie_version"
            ),
        ),
        timeout=(
            _int(table["timeout"], "deploy.bridge.ota.timeout", minimum=1)
            if "timeout" in table
            else None
        ),
        broker_tls_cacert=_optional_string(table, "broker_tls_cacert", "deploy.bridge.ota"),
        broker_tls_certfile=broker_tls_certfile,
        broker_tls_keyfile=broker_tls_keyfile,
        broker_tls_insecure=_bool(
            table.get("broker_tls_insecure", False), "deploy.bridge.ota.broker_tls_insecure"
        ),
        extra_args=tuple(
            _required_string(item, "deploy.bridge.ota.extra_args[]")
            for item in _array(table.get("extra_args", []), "deploy.bridge.ota.extra_args")
        ),
    )


def _parse_bridge(table: TomlTable) -> BridgeSettings:
    _reject_unknown(table, {"defaults"}, "bridge")
    return BridgeSettings(
        defaults=_parse_bridge_environment_overrides(
            _table(table.get("defaults", {}), "bridge.defaults"),
            "bridge.defaults",
        ),
    )


def _parse_bridge_environment_overrides(
    table: TomlTable,
    path: str,
) -> BridgeEnvironmentOverrides:
    _reject_unknown(table, {"defines", "build_flags"}, path)
    return BridgeEnvironmentOverrides(
        defines=_parse_defines(_table(table.get("defines", {}), f"{path}.defines"), path),
        build_flags=_parse_bridge_build_flags(
            _table(table.get("build_flags", {}), f"{path}.build_flags"),
            f"{path}.build_flags",
        ),
    )


def _parse_defines(table: TomlTable, owner_path: str) -> tuple[DefineOverride, ...]:
    defines: list[DefineOverride] = []
    for name, raw_value in table.items():
        path = f"{owner_path}.defines.{name}"
        if _DEFINE_NAME_RE.fullmatch(name) is None:
            _fail(f"{path} must be a valid C/C++ preprocessor define name.")
        value = _define_value(raw_value, path)
        if name == "CONFIG_HOMIE_FIRMWARE_VERSION":
            _fail(f"{path} must not be set in lsh_stack.toml; it follows the bridge firmware.")
        if name == "HOMIE_CONVENTION_VERSION" and value not in {5, "5"}:
            _fail(f"{path} must stay 5 for Homie v5 compatibility.")
        defines.append(DefineOverride(name=name, value=value))
    return tuple(defines)


def _parse_bridge_build_flags(table: TomlTable, path: str) -> BridgeBuildFlagOverrides:
    _reject_unknown(table, {"append"}, path)
    return BridgeBuildFlagOverrides(
        append=tuple(_string_list(table.get("append", []), f"{path}.append"))
    )


def _define_value(raw: object, path: str) -> DefineValue:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            _fail(f"{path} must not be empty.")
        return value
    return _fail(f"{path} must be a string, integer or boolean.")


def _parse_external_actors(table: TomlTable) -> tuple[ExternalActor, ...]:
    actors: list[ExternalActor] = []
    for name, raw_actor in table.items():
        actor_table = _table(raw_actor, f"external_actors.{name}")
        _reject_unknown(actor_table, {"state_key"}, f"external_actors.{name}")
        actors.append(
            ExternalActor(
                name=_required_string(name, f"external_actors.{name}"),
                state_key=(
                    _required_string(actor_table["state_key"], f"external_actors.{name}.state_key")
                    if "state_key" in actor_table
                    else None
                ),
            )
        )
    return tuple(actors)


def _parse_network_clicks(raw: object) -> tuple[NetworkClick, ...]:
    if not isinstance(raw, list):
        _fail("network_clicks must be an array of tables.")

    clicks: list[NetworkClick] = []
    for index, item in enumerate(raw):
        path = f"network_clicks[{index}]"
        table = _table(item, path)
        _reject_unknown(table, {"source", "type", "actors", "other_actors"}, path)
        source = _required_string(table.get("source"), f"{path}.source")
        source_device, source_button = _split_source(source, f"{path}.source")
        click_type = _choice(table.get("type", "long"), _CLICK_TYPES, f"{path}.type")
        actors = tuple(
            _parse_actor(actor, f"{path}.actors")
            for actor in _array(table.get("actors", []), f"{path}.actors")
        )
        other_actors = tuple(_string_list(table.get("other_actors", []), f"{path}.other_actors"))
        if not actors and not other_actors:
            _fail(f"{path} must define at least one target in actors or other_actors.")
        clicks.append(
            NetworkClick(
                source_device=source_device,
                source_button=source_button,
                click_type=cast("Literal['long', 'super_long']", click_type),
                actors=actors,
                other_actors=other_actors,
            )
        )
    return tuple(clicks)


def _parse_actor(raw: object, path: str) -> ActorTarget:
    table = _table(raw, path)
    _reject_unknown(table, {"device", "actuators"}, path)
    device = _required_string(table.get("device"), f"{path}.device")
    actuators_raw = table.get("actuators", "all")
    if actuators_raw == "all":
        actuators: Literal["all"] | tuple[ActuatorRef, ...] = "all"
    else:
        actuators = tuple(
            _actuator_ref(value, f"{path}.actuators")
            for value in _array(actuators_raw, f"{path}.actuators")
        )
        if not actuators:
            _fail(f"{path}.actuators must not be empty.")
    return ActorTarget(device=device, actuators=actuators)


def _split_source(value: str, path: str) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) != _SOURCE_PART_COUNT or not all(parts):
        _fail(f"{path} must use the form '<device>.<button>'.")
    return parts[0], parts[1]


def _duration_seconds(raw: object, path: str) -> float:
    if isinstance(raw, bool):
        _fail(f"{path} must be a positive duration.")
    if isinstance(raw, int | float):
        value = float(raw)
    elif isinstance(raw, str):
        match = _DURATION_RE.fullmatch(raw.strip())
        if match is None:
            _fail(f"{path} must be seconds or a string like '250ms', '2s', '1m'.")
        value = float(match.group("value"))
        unit = match.group("unit")
        if unit == "ms":
            value /= 1000
        elif unit == "m":
            value *= 60
        elif unit == "h":
            value *= 3600
    else:
        _fail(f"{path} must be a positive duration.")
    if value <= 0:
        _fail(f"{path} must be greater than zero.")
    return value


def _topic_base(raw: object, path: str) -> str:
    value = _required_string(raw, path)
    if not value.endswith("/"):
        _fail(f"{path} must end with '/'.")
    _reject_mqtt_wildcards(value, path)
    if "//" in value:
        _fail(f"{path} must not contain empty topic segments.")
    return value


def _concrete_topic(raw: object, path: str) -> str:
    value = _required_string(raw, path)
    if value.endswith("/"):
        _fail(f"{path} must not end with '/'.")
    _reject_mqtt_wildcards(value, path)
    if "//" in value:
        _fail(f"{path} must not contain empty topic segments.")
    return value


def _reject_mqtt_wildcards(value: str, path: str) -> None:
    if "+" in value or "#" in value:
        _fail(f"{path} must not contain MQTT wildcards.")


def _path(raw: object, path: str, base_dir: Path) -> Path:
    value = _required_string(raw, path)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _context(raw: object, path: str) -> ContextTarget:
    return cast("ContextTarget", _choice(raw, _CONTEXT_VALUES, path))


def _choice(raw: object, allowed: set[str], path: str) -> str:
    value = _required_string(raw, path)
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        _fail(f"{path} must be one of: {choices}.")
    return value


def _actuator_ref(raw: object, path: str) -> ActuatorRef:
    if isinstance(raw, bool):
        _fail(f"{path} entries must be actuator names or numeric ids.")
    if isinstance(raw, int):
        if raw < 1 or raw > _UINT8_MAX:
            _fail(f"{path} numeric ids must be in range 1..{_UINT8_MAX}.")
        return raw
    return _required_string(raw, path)


def _string_list(raw: object, path: str) -> list[str]:
    return [_required_string(item, path) for item in _array(raw, path)]


def _array(raw: object, path: str) -> list[object]:
    if not isinstance(raw, list):
        _fail(f"{path} must be an array.")
    return raw


def _table(raw: object, path: str) -> TomlTable:
    if not isinstance(raw, dict):
        _fail(f"{path} must be a table.")
    return raw


def _int(raw: object, path: str, *, minimum: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        _fail(f"{path} must be an integer.")
    if raw < minimum:
        _fail(f"{path} must be at least {minimum}.")
    return raw


def _bool(raw: object, path: str) -> bool:
    if not isinstance(raw, bool):
        _fail(f"{path} must be a boolean.")
    return raw


def _required_string(raw: object, path: str) -> str:
    if not isinstance(raw, str):
        _fail(f"{path} must be a string.")
    value = raw.strip()
    if not value:
        _fail(f"{path} must not be empty.")
    return value


def _optional_string(table: TomlTable, key: str, path: str) -> str | None:
    return _required_string(table[key], f"{path}.{key}") if key in table else None


def _optional_env_var(table: TomlTable, key: str, path: str) -> str | None:
    value = _optional_string(table, key, path)
    if value is None:
        return None
    if _ENV_VAR_RE.fullmatch(value) is None:
        _fail(f"{path}.{key} must be a valid environment variable name.")
    return value


def _reject_unknown(table: TomlTable, allowed: set[str], path: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        keys = ", ".join(unknown)
        _fail(f"{path} contains unknown keys: {keys}.")


def _fail(message: str) -> NoReturn:
    raise StackConfigError(message)
