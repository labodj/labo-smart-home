"""Typed configuration models for the LSH stack composer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

JsonObject: TypeAlias = dict[str, object]
ContextTarget: TypeAlias = Literal["none", "flow", "global"]
MqttCodec: TypeAlias = Literal["auto", "json", "msgpack"]
HomieVersion: TypeAlias = Literal["3", "4", "5"]
TransportMode: TypeAlias = Literal["serial_bridge", "onboard_ethernet"]
ClickType: TypeAlias = Literal["long", "super_long"]
ActuatorRef: TypeAlias = str | int
UploadMethod: TypeAlias = Literal["usb", "ota"]
DefineValue: TypeAlias = bool | int | str


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

    expose_state_context: ContextTarget = "global"
    expose_state_key: str = "lsh_state"
    export_topics: ContextTarget = "flow"
    export_topics_key: str = "lsh_topics"
    expose_config_context: ContextTarget = "global"
    expose_config_key: str = "lsh_config"
    other_actors_context: Literal["flow", "global"] = "global"


@dataclass(frozen=True)
class BridgeProfileSettings:
    """One stack-wide bridge firmware flavor exposed as a PlatformIO environment."""

    name: str
    base_env: str
    default: bool = False
    ota: bool = True


@dataclass(frozen=True)
class PlatformioSettings:
    """How generated PlatformIO fragments plug into consumer firmware projects."""

    core_project: Path | None = None
    bridge_project: Path | None = None
    core_extra_script: Path | None = None
    core_base_env: str = "env:release"
    bridge_base_env: str = "env:release"
    core_env_prefix: str = "core"
    bridge_env_prefix: str = "bridge"
    bridge_profiles: tuple[BridgeProfileSettings, ...] = ()


@dataclass(frozen=True)
class BridgeDeployTarget:
    """Optional per-bridge upload endpoints for USB and OTA workflows."""

    device: str
    usb_port: str | None = None
    ota_command: str | None = None


@dataclass(frozen=True)
class BridgeOtaSettings:
    """Arguments for the standard Homie/MQTT OTA helper."""

    script: str | None = None
    python: str = "python"
    broker_host: str | None = None
    broker_port: int | None = None
    broker_username: str | None = None
    broker_username_env: str | None = None
    broker_password: str | None = None
    broker_password_env: str | None = None
    base_topic: str | None = None
    homie_version: HomieVersion = "5"
    timeout: int | None = None
    broker_tls_cacert: str | None = None
    broker_tls_certfile: str | None = None
    broker_tls_keyfile: str | None = None
    broker_tls_insecure: bool = False
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgeDeploySettings:
    """Bridge upload policy used to generate PlatformIO upload environments."""

    default_method: UploadMethod = "usb"
    usb_port_template: str | None = None
    ota_command_template: str | None = None
    ota: BridgeOtaSettings | None = None
    devices: tuple[BridgeDeployTarget, ...] = ()


@dataclass(frozen=True)
class DeploySettings:
    """Deployment helpers generated beside the stack configuration."""

    bridge: BridgeDeploySettings = field(default_factory=BridgeDeploySettings)


@dataclass(frozen=True)
class DefineOverride:
    """One typed ``-D`` override for generated bridge firmware build flags."""

    name: str
    value: DefineValue


@dataclass(frozen=True)
class BridgeBuildFlagOverrides:
    """Raw bridge build flags appended after generated and typed flags."""

    append: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgeEnvironmentOverrides:
    """Bridge firmware overrides that survive generated PlatformIO regeneration."""

    defines: tuple[DefineOverride, ...] = ()
    build_flags: BridgeBuildFlagOverrides = field(default_factory=BridgeBuildFlagOverrides)


@dataclass(frozen=True)
class BridgeSettings:
    """User-facing bridge firmware override layers owned by the stack file."""

    defaults: BridgeEnvironmentOverrides = field(default_factory=BridgeEnvironmentOverrides)


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
    platformio: PlatformioSettings = field(default_factory=PlatformioSettings)
    deploy: DeploySettings = field(default_factory=DeploySettings)
    bridge: BridgeSettings = field(default_factory=BridgeSettings)
    external_actors: tuple[ExternalActor, ...] = ()
    network_clicks: tuple[NetworkClick, ...] = ()
