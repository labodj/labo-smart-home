"""Typed configuration models for the LSH stack composer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

JsonObject: TypeAlias = dict[str, object]
ContextTarget: TypeAlias = Literal["none", "flow", "global"]
MqttCodec: TypeAlias = Literal["auto", "json", "msgpack"]
TransportMode: TypeAlias = Literal["serial_bridge", "onboard_ethernet"]
ClickType: TypeAlias = Literal["long", "super_long"]
ActuatorRef: TypeAlias = str | int


@dataclass(frozen=True)
class CoreSettings:
    """How the composer obtains the controller contract from ``lsh-core``."""

    devices: Path
    tool: Path | None = None
    selected_devices: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransportSettings:
    """Deployment transport between the controller and MQTT-facing runtime."""

    mode: TransportMode = "serial_bridge"


@dataclass(frozen=True)
class MqttSettings:
    """MQTT-facing settings shared by bridge, coordinator and Node-RED."""

    codec: MqttCodec = "auto"
    lsh_base_path: str = "LSH/"
    homie_base_path: str = "homie/5/"
    service_topic: str = "LSH/Node-RED/SRV"


@dataclass(frozen=True)
class CoordinatorSettings:
    """Runtime options consumed by the standalone coordinator and Node-RED wrapper."""

    other_devices_prefix: str = "other_devices"
    click_timeout: float = 2.0
    click_cleanup_interval: float = 30.0
    watchdog_interval: float = 60.0
    interrogate_threshold: float = 120.0
    ping_timeout: float = 3.0
    initial_state_timeout: float = 2.0
    other_actors_topic: str | None = None


@dataclass(frozen=True)
class NodeRedSettings:
    """Node-RED editor fields that are not part of the coordinator core model."""

    expose_state_context: ContextTarget = "none"
    expose_state_key: str = "lsh_state"
    export_topics: ContextTarget = "flow"
    export_topics_key: str = "lsh_topics"
    expose_config_context: ContextTarget = "none"
    expose_config_key: str = "lsh_config"
    other_actors_context: Literal["flow", "global"] = "global"


@dataclass(frozen=True)
class ExternalActor:
    """Optional documentation and validation metadata for a non-LSH target."""

    name: str
    state_key: str | None = None


@dataclass(frozen=True)
class ActorTarget:
    """One LSH target controlled by a distributed click."""

    device: str
    actuators: Literal["all"] | tuple[ActuatorRef, ...]


@dataclass(frozen=True)
class NetworkClick:
    """Stack-level action attached to a controller network click declaration."""

    source_device: str
    source_button: str
    click_type: ClickType
    actors: tuple[ActorTarget, ...] = ()
    other_actors: tuple[str, ...] = ()


@dataclass(frozen=True)
class StackConfig:
    """Complete normalized stack TOML configuration."""

    path: Path
    schema_version: int
    core: CoreSettings
    transport: TransportSettings = field(default_factory=TransportSettings)
    mqtt: MqttSettings = field(default_factory=MqttSettings)
    coordinator: CoordinatorSettings = field(default_factory=CoordinatorSettings)
    node_red: NodeRedSettings = field(default_factory=NodeRedSettings)
    external_actors: tuple[ExternalActor, ...] = ()
    network_clicks: tuple[NetworkClick, ...] = ()
