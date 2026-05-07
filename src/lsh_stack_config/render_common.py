"""Shared stack-view helpers used by CLI, render and deploy modules."""

from __future__ import annotations

import re
from typing import cast

from .errors import StackConfigError
from .models import BridgeProfileSettings, JsonObject, StackConfig

_SLUG_RE = re.compile(r"[^A-Za-z0-9_]+")


def json_object(raw: object, path: str = "value") -> JsonObject:
    """Validate and return a JSON object value."""
    if not isinstance(raw, dict):
        raise StackConfigError(f"{path} must be a JSON object.")
    return cast("JsonObject", raw)


def json_list(raw: object, path: str = "value") -> list[object]:
    """Validate and return a JSON array value."""
    if not isinstance(raw, list):
        raise StackConfigError(f"{path} must be a JSON array.")
    return cast("list[object]", raw)


def device_names(stack: JsonObject) -> list[str]:
    """Return coordinator device names from the composed stack."""
    coordinator = json_object(stack["coordinator"])
    system_config = json_object(coordinator["systemConfig"])
    return [str(json_object(device)["name"]) for device in json_list(system_config["devices"])]


def bridge_devices(stack: JsonObject) -> JsonObject:
    """Return bridge devices keyed by generated bridge identifier."""
    return json_object(json_object(stack["bridge"])["devices"])


def bridge_profiles(config: StackConfig) -> tuple[BridgeProfileSettings, ...]:
    """Return explicit bridge profiles or the implicit default profile."""
    if config.platformio.bridge_profiles:
        profiles = config.platformio.bridge_profiles
        if any(profile.default for profile in profiles):
            return profiles
        first, *rest = profiles
        return (
            BridgeProfileSettings(
                name=first.name,
                base_env=first.base_env,
                default=True,
                ota=first.ota,
            ),
            *rest,
        )
    return (
        BridgeProfileSettings(
            name="",
            base_env=config.platformio.bridge_base_env,
            default=True,
            ota=True,
        ),
    )


def default_bridge_profile(
    profiles: tuple[BridgeProfileSettings, ...],
) -> BridgeProfileSettings:
    """Return the profile marked as default, falling back to the first profile."""
    return next((profile for profile in profiles if profile.default), profiles[0])


def profile_key(profile: BridgeProfileSettings) -> str:
    """Return the stable deploy-plan key for a bridge profile."""
    return profile.name or "default"


def bridge_build_env(config: StackConfig, profile: BridgeProfileSettings) -> str:
    """Return the PlatformIO build environment name for a bridge profile."""
    pieces = [slug(config.platformio.bridge_env_prefix)]
    if profile.name:
        pieces.append(slug(profile.name))
    return "_".join(pieces)


def bridge_usb_upload_env(
    config: StackConfig,
    profile: BridgeProfileSettings,
    device: str,
) -> str:
    """Return the per-device USB upload environment for a bridge profile."""
    return env_name(bridge_build_env(config, profile), "usb", device)


def bridge_flag_section(device: str) -> str:
    """Return the generated PlatformIO section holding bridge build flags."""
    return f"lsh_stack_bridge_{slug(device)}"


def env_name(prefix: str, device: str | None = None, suffix: str | None = None) -> str:
    """Return a stable PlatformIO environment name from user-facing labels."""
    pieces = [slug(prefix)]
    if device is not None:
        pieces.append(slug(device))
    if suffix is not None:
        pieces.append(slug(suffix))
    return "_".join(piece for piece in pieces if piece)


def slug(value: str) -> str:
    """Return an ASCII-ish identifier segment suitable for PlatformIO names."""
    normalized = _SLUG_RE.sub("_", value.strip()).strip("_")
    return normalized or "device"
