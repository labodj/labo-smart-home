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
    ContextTarget,
    CoordinatorSettings,
    CoreSettings,
    ExternalActor,
    MqttCodec,
    MqttSettings,
    NetworkClick,
    NodeRedSettings,
    StackConfig,
    TransportMode,
    TransportSettings,
)

TomlTable = dict[str, object]

_DURATION_RE = re.compile(r"^(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<unit>ms|s|m|h)$")
_CONTEXT_VALUES = {"none", "flow", "global"}
_NODE_RED_ACTOR_CONTEXT_VALUES = {"flow", "global"}
_MQTT_CODECS = {"auto", "json", "msgpack"}
_TRANSPORT_MODES = {"serial_bridge", "onboard_ethernet"}
_CLICK_TYPES = {"long", "super_long"}
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
            table.get("expose_state_context", "none"),
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
            table.get("expose_config_context", "none"),
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


def _required_string(raw: object, path: str) -> str:
    if not isinstance(raw, str):
        _fail(f"{path} must be a string.")
    value = raw.strip()
    if not value:
        _fail(f"{path} must not be empty.")
    return value


def _reject_unknown(table: TomlTable, allowed: set[str], path: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        keys = ", ".join(unknown)
        _fail(f"{path} contains unknown keys: {keys}.")


def _fail(message: str) -> NoReturn:
    raise StackConfigError(message)
