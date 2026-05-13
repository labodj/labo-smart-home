"""Render bridge build, USB upload and MQTT OTA deployment commands."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from .errors import StackConfigError
from .models import (
    BridgeDeployTarget,
    BridgeProfileSettings,
    JsonObject,
    StackConfig,
)
from .platformio_utils import path_for_platformio, project_command_path
from .render_common import (
    bridge_build_env,
    bridge_devices,
    bridge_profiles,
    bridge_usb_upload_env,
    core_build_env,
    core_profiles,
    default_bridge_profile,
    default_core_profile,
    device_names,
    json_object,
    profile_key,
)


@dataclass(frozen=True)
class BridgeOtaArtifacts:
    """Generated helper files used by the standard Homie bridge OTA flow."""

    script: Path | None = None
    config: Path | None = None


def render_deploy_plan(
    config: StackConfig,
    stack: JsonObject,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> JsonObject:
    """Return exact PlatformIO environment names and commands for build/upload tools."""
    bridge_device_names = list(bridge_devices(stack))
    profiles = bridge_profiles(config)
    default_profile = default_bridge_profile(profiles)
    controller_profiles = core_profiles(config)
    default_controller_profile = default_core_profile(controller_profiles)
    core_devices = device_names(stack)
    core_project = project_command_path(config.platformio.core_project)
    bridge_project = project_command_path(config.platformio.bridge_project)

    core_plan: JsonObject = {}
    for device in core_devices:
        env_name = core_build_env(config, device, default_controller_profile)
        core_plan[device] = {
            "env": env_name,
            "buildCommand": pio_command(core_project, [env_name], target=None),
            "uploadCommand": pio_command(core_project, [env_name], target="upload"),
            "profiles": {
                profile_key(profile): {
                    "env": (profile_env := core_build_env(config, device, profile)),
                    "baseEnv": profile.base_env,
                    "default": profile.default,
                    "buildCommand": pio_command(core_project, [profile_env], target=None),
                    "uploadCommand": pio_command(core_project, [profile_env], target="upload"),
                }
                for profile in controller_profiles
            },
        }

    profile_plan: JsonObject = {}
    for profile in profiles:
        profile_plan[profile_key(profile)] = _bridge_profile_plan(
            config=config,
            bridge_project=bridge_project,
            devices=bridge_device_names,
            profile=profile,
            bridge_ota=bridge_ota,
        )

    default_profile_key = profile_key(default_profile)
    bridge_firmware = {
        **json_object(profile_plan[default_profile_key]),
        "defaultProfile": default_profile_key,
        "profiles": profile_plan,
    }

    bridge_plan: JsonObject = {}
    for device in bridge_device_names:
        usb_target = bridge_usb_target(config, bridge_project, device, default_profile)
        ota_command = bridge_ota_command(
            config,
            device,
            "$SOURCE",
            bridge_ota,
        )
        bridge_plan[device] = {
            "defaultMethod": config.deploy.bridge.default_method,
            "defaultUploadCommand": (
                ota_command
                if config.deploy.bridge.default_method == "ota" and ota_command is not None
                else usb_target["command"]
            ),
            "usbUploadEnv": usb_target["env"],
            "usbUploadCommand": usb_target["command"],
            "usbPort": usb_target["uploadPort"],
            "otaTarget": f"lsh_ota_{device}",
            "otaCommand": ota_command,
        }

    all_bridge_profile_build_envs = [bridge_build_env(config, profile) for profile in profiles]
    all_core_profile_build_envs = [
        core_build_env(config, device, profile)
        for device in core_devices
        for profile in controller_profiles
    ]
    return {
        "schema": "lsh-stack-deploy-plan/v1",
        "coreProject": core_project,
        "bridgeProject": bridge_project,
        "coreProfiles": [
            {
                "name": profile_key(profile),
                "baseEnv": profile.base_env,
                "default": profile.default,
            }
            for profile in controller_profiles
        ],
        "bridgeProfiles": [
            {
                "name": profile_key(profile),
                "baseEnv": profile.base_env,
                "default": profile.default,
                "ota": profile.ota,
            }
            for profile in profiles
        ],
        "core": core_plan,
        "bridgeFirmware": bridge_firmware,
        "bridge": bridge_plan,
        "batch": {
            "buildAllCoreProfiles": pio_command(
                core_project,
                all_core_profile_build_envs,
                target=None,
            ),
            "buildAllBridgeProfiles": pio_command(
                bridge_project,
                all_bridge_profile_build_envs,
                target=None,
            ),
        },
    }


def bridge_usb_target(
    config: StackConfig,
    bridge_project: str,
    device: str,
    profile: BridgeProfileSettings,
) -> JsonObject:
    """Return the PlatformIO target data for one bridge USB upload."""
    usb_port = bridge_usb_port(config, device)
    env_name = (
        bridge_usb_upload_env(config, profile, device)
        if usb_port is not None
        else bridge_build_env(config, profile)
    )
    return {
        "env": env_name,
        "uploadPort": usb_port,
        "command": pio_command(bridge_project, [env_name], target="upload"),
    }


def bridge_usb_port(config: StackConfig, device: str) -> str | None:
    """Return the configured USB port for a bridge device, if any."""
    target = _bridge_deploy_target(config, device)
    if target is not None and target.usb_port is not None:
        return target.usb_port
    template = config.deploy.bridge.usb_port_template
    return _format_deploy_template(template, device=device) if template is not None else None


def bridge_ota_command(
    config: StackConfig,
    device: str,
    firmware: str,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> str | None:
    """Return the shell command used to OTA-upload one bridge firmware."""
    if config.deploy.bridge.ota is None:
        return None
    return _bridge_mqtt_ota_command(
        config,
        device,
        firmware,
        bridge_ota,
    )


def bridge_ota_template(
    config: StackConfig,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> str | None:
    """Return the PlatformIO OTA template command for generated custom targets."""
    if config.deploy.bridge.ota is None:
        return None
    return _bridge_mqtt_ota_command(
        config,
        "{device}",
        "{firmware}",
        bridge_ota,
        python_command="{python}",
    )


def bridge_ota_commands(
    config: StackConfig,
    devices: list[str],
    firmware: str,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> list[str]:
    """Return the command list needed to OTA-upload a device set."""
    if not devices:
        return []
    commands: list[str] = []
    for device in devices:
        device_command = bridge_ota_command(
            config,
            device,
            firmware,
            bridge_ota,
        )
        if device_command is not None:
            commands.append(device_command)
    return commands


def uses_generated_bridge_ota_script(config: StackConfig) -> bool:
    """Return whether generation should emit the Homie OTA wrapper script."""
    return config.deploy.bridge.ota is not None


def render_bridge_ota_config(config: StackConfig) -> JsonObject:
    """Return file-based defaults for the standard Homie OTA updater."""
    ota = config.deploy.bridge.ota
    if ota is None:
        return {}

    broker: JsonObject = {}
    _set_if_not_none(broker, "host", ota.broker_host)
    _set_if_not_none(broker, "port", ota.broker_port)
    _set_if_not_none(broker, "username", ota.broker_username)
    _set_if_not_none(broker, "username_env", ota.broker_username_env)
    _set_if_not_none(broker, "password", ota.broker_password)
    _set_if_not_none(broker, "password_env", ota.broker_password_env)
    _set_if_not_none(broker, "tls_cacert", ota.broker_tls_cacert)
    _set_if_not_none(broker, "tls_certfile", ota.broker_tls_certfile)
    _set_if_not_none(broker, "tls_keyfile", ota.broker_tls_keyfile)
    if ota.broker_tls_insecure:
        broker["tls_insecure"] = True

    ota_defaults: JsonObject = {}
    _set_if_not_none(ota_defaults, "timeout", ota.timeout)

    return {
        "schema": "homie-ota-config/v1",
        "broker": broker,
        "homie": {
            "base_topic": ota.base_topic or config.mqtt.homie_base_path,
            "version": ota.homie_version,
        },
        "ota": ota_defaults,
    }


def pio_command(project: str, envs: list[str], target: str | None) -> list[str]:
    """Return a PlatformIO CLI command as argv data."""
    command = ["platformio", "run", "-d", project]
    for platformio_env in envs:
        command.extend(["-e", platformio_env])
    if target is not None:
        command.extend(["-t", target])
    return command


def _bridge_profile_plan(
    *,
    config: StackConfig,
    bridge_project: str,
    devices: list[str],
    profile: BridgeProfileSettings,
    bridge_ota: BridgeOtaArtifacts | None,
) -> JsonObject:
    build_env = bridge_build_env(config, profile)
    ota_targets = {
        device: {
            "target": f"lsh_ota_{device}",
            "command": command,
        }
        for device in devices
        if (
            command := bridge_ota_command(
                config,
                device,
                "$SOURCE",
                bridge_ota,
            )
        )
        is not None
    }
    ota_all_commands = bridge_ota_commands(
        config,
        devices,
        "$SOURCE",
        bridge_ota,
    )
    return {
        "buildEnv": build_env,
        "baseEnv": profile.base_env,
        "default": profile.default,
        "otaEnabled": profile.ota,
        "buildCommand": pio_command(bridge_project, [build_env], target=None),
        "usbUploadCommand": pio_command(bridge_project, [build_env], target="upload"),
        "usbTargets": {
            device: bridge_usb_target(config, bridge_project, device, profile) for device in devices
        },
        "otaTargets": ota_targets if profile.ota else {},
        "otaAllTarget": "lsh_ota_all" if profile.ota and ota_all_commands else None,
        "otaAllCommand": " && ".join(ota_all_commands)
        if profile.ota and ota_all_commands
        else None,
        "otaAllCommands": ota_all_commands if profile.ota else [],
    }


def _bridge_mqtt_ota_command(
    config: StackConfig,
    device: str,
    firmware: str,
    bridge_ota: BridgeOtaArtifacts | None,
    *,
    python_command: str | None = None,
) -> str:
    bridge_ota = bridge_ota or BridgeOtaArtifacts()
    if bridge_ota.script is None:
        raise StackConfigError("generated bridge OTA script path is required.")
    script = path_for_platformio(bridge_ota.script, config.platformio.bridge_project)
    args = [_quote_command_arg(python_command or "python"), _quote_command_arg(script)]
    if bridge_ota.config is not None:
        # The generated wrapper is deliberately thin: the command itself names the
        # generated config file, so users can see exactly which broker/topic defaults
        # are used by PlatformIO and deploy-plan entries.
        _extend_option(args, "--config", _bridge_ota_config_command_path(config, bridge_ota.config))
    _extend_raw_option(args, "--device-id", device)
    args.append(firmware)
    return " ".join(args)


def _bridge_ota_config_command_path(config: StackConfig, bridge_ota_config_path: Path) -> str:
    return path_for_platformio(bridge_ota_config_path, config.platformio.bridge_project)


def _extend_option(args: list[str], option: str, value: str | None) -> None:
    if value is None:
        return
    args.extend([option, _quote_command_arg(value)])


def _extend_raw_option(args: list[str], option: str, value: str) -> None:
    args.extend([option, value])


def _quote_command_arg(value: str) -> str:
    if value in {"{device}", "{firmware}", "{python}", "$SOURCE"}:
        return value
    return shlex.quote(value)


def _bridge_deploy_target(config: StackConfig, device: str) -> BridgeDeployTarget | None:
    return next(
        (target for target in config.deploy.bridge.devices if target.device == device), None
    )


def _format_deploy_template(template: str, **values: str) -> str:
    try:
        return template.format(**values)
    except (KeyError, ValueError) as exc:
        raise StackConfigError(
            "deploy bridge templates can only use the {device} placeholder."
        ) from exc


def _set_if_not_none(target: JsonObject, key: str, value: object | None) -> None:
    if value is not None:
        target[key] = value
