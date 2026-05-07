"""Command-line interface for the end-to-end LSH stack composer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .composer import compose_stack
from .core_export import load_core_export
from .doctor import doctor_fix, project_warnings
from .errors import StackConfigError
from .models import JsonObject, StackConfig
from .parser import load_stack_config
from .render import render_report, stack_json, write_output_tree
from .render_common import env_name, json_list, json_object
from .scaffold import write_starter

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``lsh-stack`` command."""
    parser = _parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": _init,
        "new": _new,
        "generate": _generate,
        "check": _check,
        "doctor": _doctor,
        "explain": _explain,
        "report": _report,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        return handler(args)
    except StackConfigError as exc:
        sys.stderr.write(f"lsh-stack error: {exc}\n")
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lsh-stack",
        description="Compose bridge, coordinator and Node-RED config from LSH TOML files.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init", help="create a starter installation project")
    init.add_argument("path", nargs="?", type=Path, default=Path())
    init.add_argument("--force", action="store_true", help="overwrite an existing file")

    new = subparsers.add_parser("new", help="create a starter installation project")
    new.add_argument("path", type=Path)
    new.add_argument("--force", action="store_true", help="overwrite existing starter files")

    for command in ("generate", "check", "doctor", "report"):
        child = subparsers.add_parser(command, help=f"{command} an lsh_stack.toml file")
        child.add_argument("config", type=Path, help="path to lsh_stack.toml")
        child.add_argument("--core-tool", type=Path, help="override lsh-core generator path")
        if command == "generate":
            child.add_argument(
                "--output-dir",
                type=Path,
                help="write generated files instead of printing one JSON document",
            )
        if command == "doctor":
            child.add_argument(
                "--output-dir",
                type=Path,
                default=Path("generated"),
                help="generated output directory to check against",
            )
    explain = subparsers.add_parser("explain", help="explain generated config for one device")
    explain.add_argument("config", type=Path, help="path to lsh_stack.toml")
    explain.add_argument("device", help="controller device name to explain")
    explain.add_argument("--core-tool", type=Path, help="override lsh-core generator path")
    return parser


def _init(args: argparse.Namespace) -> int:
    return write_starter(args.path.resolve(), force=args.force)


def _new(args: argparse.Namespace) -> int:
    return write_starter(args.path.resolve(), force=args.force)


def _generate(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    if args.output_dir is None:
        sys.stdout.write(stack_json(stack))
        return 0

    written = write_output_tree(args.output_dir.resolve(), config, stack)
    sys.stdout.write(render_report(config, stack))
    sys.stdout.write("written files:\n")
    for path in written:
        sys.stdout.write(f"- {path}\n")
    return 0


def _check(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    sys.stdout.write(render_report(config, stack))
    return 0


def _doctor(args: argparse.Namespace) -> int:
    sys.stdout.write("LSH stack doctor\n")
    try:
        config, stack = _compose(args.config, args.core_tool)
    except StackConfigError as exc:
        sys.stdout.write(f"problem: {exc}\n")
        sys.stdout.write(f"fix: {doctor_fix(str(exc))}\n")
        return 1

    sys.stdout.write(render_report(config, stack))
    warnings = project_warnings(config, args.output_dir)
    if warnings:
        sys.stdout.write("warnings:\n")
        for warning in warnings:
            sys.stdout.write(f"- {warning}\n")
    else:
        sys.stdout.write("No stack configuration problems found.\n")
    return 0


def _explain(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    device = args.device
    system_config = json_object(json_object(stack["coordinator"])["systemConfig"])
    system_devices = json_list(system_config["devices"], "coordinator.systemConfig.devices")
    system_entry = next(
        (
            json_object(raw_device)
            for raw_device in system_devices
            if json_object(raw_device).get("name") == device
        ),
        None,
    )
    bridge_key, bridge_entry = _bridge_entry(stack, device)
    if system_entry is None and bridge_entry is None:
        raise StackConfigError(f"unknown device: {device}")

    core_env = env_name(config.platformio.core_env_prefix, device)
    bridge_env = env_name(config.platformio.bridge_env_prefix)

    sys.stdout.write(f"LSH stack explain: {device}\n")
    sys.stdout.write(f"- controller TOML: {config.core.devices}\n")
    sys.stdout.write(f"- controller environment: {core_env}\n")
    if bridge_entry is not None:
        topics = json_object(bridge_entry.get("topics", {}))
        bridge = json_object(stack["bridge"])
        flags = [str(flag) for flag in json_list(bridge["platformioBuildFlags"])]
        sys.stdout.write(f"- bridge firmware environment: {bridge_env}\n")
        sys.stdout.write(f"- bridge USB upload: PlatformIO Upload on {bridge_env}\n")
        sys.stdout.write(f"- bridge OTA target: LSH OTA {bridge_key or device}\n")
        if topics:
            sys.stdout.write("- MQTT topics:\n")
            for name, topic in sorted(topics.items()):
                sys.stdout.write(f"  - {name}: {topic}\n")
        sys.stdout.write(f"- bridge build flags ({len(flags)}):\n")
        for flag in flags:
            sys.stdout.write(f"  - {flag}\n")
    if system_entry is not None:
        sys.stdout.write("- coordinator systemConfig entry:\n")
        sys.stdout.write(stack_json(system_entry))
    return 0


def _report(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config, args.core_tool)
    sys.stdout.write(render_report(config, stack))
    return 0


def _compose(config_path: Path, core_tool: Path | None) -> tuple[StackConfig, JsonObject]:
    config = load_stack_config(config_path)
    core_export = load_core_export(config.core, override_tool=core_tool)
    stack = compose_stack(config, core_export)
    return config, stack


def _bridge_entry(stack: JsonObject, device: str) -> tuple[str | None, JsonObject | None]:
    bridge_devices = json_object(json_object(stack["bridge"])["devices"])
    for key, raw_device in bridge_devices.items():
        bridge_device = json_object(raw_device)
        if key == device or bridge_device.get("deviceName") == device:
            return key, bridge_device
    return None, None
