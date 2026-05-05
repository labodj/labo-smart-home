"""Render stack composer outputs for humans and files."""

from __future__ import annotations

import json
from pathlib import Path

from .models import JsonObject, StackConfig


def stack_json(stack: JsonObject) -> str:
    """Return stable JSON for generated stack artifacts."""
    return json.dumps(stack, indent=2, sort_keys=True) + "\n"


def render_report(config: StackConfig, stack: JsonObject) -> str:
    """Render a concise bring-up report for the generated stack config."""
    coordinator = _object(stack["coordinator"])
    system_config = _object(coordinator["systemConfig"])
    devices = _list(system_config["devices"])
    bridge = _object(stack["bridge"])
    bridge_devices = _object(bridge["devices"])
    mapped_clicks = _list(stack.get("mappedNetworkClicks", []))
    unmapped_clicks = _list(coordinator.get("unmappedNetworkClicks", []))

    lines = [
        "LSH stack composer",
        f"- stack config: {config.path}",
        f"- core config: {config.core.devices}",
        f"- transport: {_object(stack['transport'])['mode']}",
        f"- MQTT protocol: {stack['protocol']}",
        f"- devices: {len(devices)}",
        f"- mapped network clicks: {len(mapped_clicks)}",
        f"- core network-click declarations: {len(unmapped_clicks)}",
        "- bridge environments:",
    ]
    for device_key, raw_device in bridge_devices.items():
        device = _object(raw_device)
        flags = _list(device["platformioBuildFlags"])
        lines.append(f"  - {device_key}: {len(flags)} build flags")

    return "\n".join(lines) + "\n"


def write_output_tree(output_dir: Path, stack: JsonObject) -> list[Path]:
    """Write the generated files consumed by bridge, coordinator and Node-RED."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    stack_path = output_dir / "lsh-stack-config.json"
    stack_path.write_text(stack_json(stack), encoding="utf-8")
    written.append(stack_path)

    coordinator = _object(stack["coordinator"])
    system_config_path = output_dir / "system-config.json"
    system_config_path.write_text(
        stack_json(_object(coordinator["systemConfig"])), encoding="utf-8"
    )
    written.append(system_config_path)

    node_red = _object(_object(stack["nodeRed"])["lshLogic"])
    node_red_path = output_dir / "node-red-lsh-logic.json"
    node_red_path.write_text(stack_json(node_red), encoding="utf-8")
    written.append(node_red_path)

    bridge_dir = output_dir / "bridge-platformio-flags"
    bridge_dir.mkdir(exist_ok=True)
    bridge_devices = _object(_object(stack["bridge"])["devices"])
    for device_key, raw_device in bridge_devices.items():
        flags = _list(_object(raw_device)["platformioBuildFlags"])
        flag_path = bridge_dir / f"{device_key}.txt"
        flag_path.write_text("\n".join(str(flag) for flag in flags) + "\n", encoding="utf-8")
        written.append(flag_path)

    return written


def _object(raw: object) -> JsonObject:
    if not isinstance(raw, dict):
        raise TypeError("expected JSON object")
    return raw


def _list(raw: object) -> list[object]:
    if not isinstance(raw, list):
        raise TypeError("expected JSON array")
    return raw
