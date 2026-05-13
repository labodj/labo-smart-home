"""Command-line interface for the end-to-end LSH stack composer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from . import __version__
from .cli_runtime import (
    bootstrap_core_project,
    required_platformio_invocation,
    run_or_print,
    subprocess_env_with_ota_password,
)
from .commands import stack_command
from .composer import compose_stack
from .core_export import installed_lsh_core_tools, load_core_export
from .doctor import doctor_fix, project_warnings
from .errors import StackConfigError
from .launcher import lsh_stack_command
from .models import JsonObject, StackConfig
from .parser import load_stack_config
from .paths import display_path
from .render import render_report, stack_json, write_output_tree
from .render_common import (
    bridge_build_env,
    bridge_devices,
    bridge_profiles,
    default_bridge_profile,
    device_names,
    env_name,
    json_list,
    json_object,
)
from .scaffold import ensure_project_scaffolds, write_core_starter, write_starter
from .status import inspect_stack_status, render_stack_status

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_CONFIG = Path("lsh_stack.toml")
DEFAULT_OUTPUT_DIR = Path("generated")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``lsh-stack`` command."""
    parser = _parser()
    args = parser.parse_args(argv)
    handlers = {
        "new": _new,
        "new-core": _new_core,
        "setup": _setup,
        "ota": _ota,
        "generate": _generate,
        "check": _check,
        "status": _status,
        "doctor": _doctor,
        "explain": _explain,
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


def entrypoint() -> NoReturn:
    """Run the CLI as a Python executable entrypoint."""
    raise SystemExit(main())


def _parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    launcher = lsh_stack_command()
    parser = argparse.ArgumentParser(
        prog="lsh-stack",
        description="Compose bridge, coordinator and Node-RED config from LSH TOML files.",
        formatter_class=formatter,
        epilog=f"""\
Typical flow:
  {launcher} new my-home
  cd my-home
  {launcher} setup
  {launcher} doctor

Need orientation:
  {launcher} status

After the first USB bridge flash and Homie setup:
  {launcher} ota --dry-run
  {launcher} ota panel
""",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    new = subparsers.add_parser(
        "new",
        help="create a starter installation project",
        description="Create a complete editable LSH stack project directory.",
        formatter_class=formatter,
        epilog=f"""\
Example:
  {launcher} new my-home
  cd my-home
  {launcher} setup
""",
    )
    new.add_argument("path", metavar="PROJECT_DIR", type=Path, help="project directory to create")
    new.add_argument("--force", action="store_true", help="overwrite existing starter files")

    new_core = subparsers.add_parser(
        "new-core",
        help="create a standalone lsh-core PlatformIO project",
        description="Create only the controller PlatformIO project, without bridge or stack files.",
        formatter_class=formatter,
        epilog=f"""\
Example:
  {launcher} new-core my-controller
  cd my-controller
  platformio run -e core_panel
""",
    )
    new_core.add_argument(
        "path",
        metavar="PROJECT_DIR",
        type=Path,
        help="core project directory to create",
    )
    new_core.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing core starter files",
    )

    setup = subparsers.add_parser(
        "setup",
        help="bootstrap, generate and check an installation project",
        description="Create missing project shells, generate outputs and print the next commands.",
        formatter_class=formatter,
        epilog=f"""\
Run from the stack project directory:
  {launcher} setup

If PlatformIO CLI is not installed, build the core environment once from VSCode
PlatformIO Project Tasks, then run the same setup command again.
""",
    )
    _add_config_option(setup)

    ota = subparsers.add_parser(
        "ota",
        help="build and OTA-upload bridge firmware",
        description="Build the default bridge firmware profile and OTA-upload it.",
        formatter_class=formatter,
        epilog=f"""\
Examples:
  {launcher} ota --dry-run
  {launcher} ota panel
  {launcher} ota panel lights
""",
    )
    ota.add_argument(
        "device_args",
        nargs="*",
        metavar="DEVICE",
        help="bridge device ids to update; omitted means all",
    )
    ota.add_argument(
        "--config",
        dest="config_path",
        type=Path,
        default=DEFAULT_CONFIG,
        help="path to lsh_stack.toml (default: lsh_stack.toml)",
    )
    ota.add_argument("--dry-run", action="store_true", help="print commands without running them")
    ota.add_argument("--list-devices", action="store_true", help="print bridge device ids and exit")

    command_help = {
        "generate": "generate stack artifacts",
        "check": "validate the stack configuration",
        "status": "show setup progress and the next action",
        "doctor": "diagnose stack configuration problems",
    }
    for command, help_text in command_help.items():
        child = subparsers.add_parser(command, help=help_text, formatter_class=formatter)
        _add_config_option(child)
    explain = subparsers.add_parser(
        "explain",
        help="explain generated config for one device",
        formatter_class=formatter,
    )
    explain.add_argument("device", metavar="DEVICE", help="controller device name to explain")
    _add_config_option(explain)
    return parser


def _add_config_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="path to lsh_stack.toml (default: lsh_stack.toml)",
    )


def _new(args: argparse.Namespace) -> int:
    return write_starter(args.path.resolve(), force=args.force)


def _new_core(args: argparse.Namespace) -> int:
    return write_core_starter(args.path.resolve(), force=args.force)


def _setup(args: argparse.Namespace) -> int:
    config_path = args.config.resolve()
    output_dir = _output_dir(config_path)
    scaffold_config = load_stack_config(config_path)
    scaffolded = ensure_project_scaffolds(scaffold_config)
    bootstrap_result = _bootstrap_core_if_needed(scaffold_config)
    if bootstrap_result != 0:
        return bootstrap_result
    try:
        config, stack = _compose(config_path)
    except StackConfigError as exc:
        if not _missing_core_tool_error(exc):
            raise
        config = load_stack_config(config_path)
        bootstrap_result = bootstrap_core_project(config)
        if bootstrap_result != 0:
            return bootstrap_result
        config, stack = _compose(config_path)

    written = write_output_tree(output_dir, config, stack)
    sys.stdout.write(render_report(config, stack))
    sys.stdout.write("setup complete\n")
    sys.stdout.write("written files:\n")
    for path in written:
        sys.stdout.write(f"- {display_path(path)}\n")

    warnings = project_warnings(config, output_dir)
    if warnings:
        sys.stdout.write("warnings:\n")
        for warning in warnings:
            sys.stdout.write(f"- {warning}\n")

    if scaffolded:
        sys.stdout.write("created project files:\n")
        for path in scaffolded:
            sys.stdout.write(f"- {display_path(path)}\n")

    _print_setup_next_steps(config, stack, output_dir)
    return 0


def _ota(args: argparse.Namespace) -> int:
    config_path = args.config_path.resolve()
    output_dir = _output_dir(config_path)
    config, stack = _compose(config_path)
    available_devices = list(bridge_devices(stack))
    if args.list_devices:
        sys.stdout.write("\n".join(available_devices) + ("\n" if available_devices else ""))
        return 0

    _validate_stack_ota_support(config)
    selected_devices = _selected_bridge_devices(available_devices, list(args.device_args))
    profile = default_bridge_profile(bridge_profiles(config))
    if not profile.ota:
        raise StackConfigError("the default bridge profile has ota = false.")

    write_output_tree(output_dir, config, stack)
    bridge_project = _bridge_project(config)
    build_env = bridge_build_env(config, profile)
    firmware = bridge_project / ".pio" / "build" / build_env / "firmware.bin"
    ota_script = output_dir / "bridge-ota.py"
    ota_config = output_dir / "bridge-ota.json"
    if not ota_script.is_file() or not ota_config.is_file():
        raise StackConfigError("generated bridge OTA files are missing; run setup first.")

    env = subprocess_env_with_ota_password(ota_config, dry_run=args.dry_run)

    build_result = run_or_print(
        [
            *required_platformio_invocation(
                dry_run=args.dry_run,
            ),
            "run",
            "-d",
            str(bridge_project),
            "-e",
            build_env,
        ],
        dry_run=args.dry_run,
    )
    if build_result != 0:
        return build_result

    if not args.dry_run and not firmware.is_file():
        raise StackConfigError(f"firmware not found: {firmware}")

    failures = 0
    for device in selected_devices:
        command = _bridge_ota_command_args(
            ota_script=ota_script,
            ota_config=ota_config,
            device=device,
            firmware=firmware,
        )
        result = run_or_print(command, dry_run=args.dry_run, env=env)
        if result != 0:
            failures += 1

    return 1 if failures else 0


def _bridge_ota_command_args(
    *,
    ota_script: Path,
    ota_config: Path,
    device: str,
    firmware: Path,
) -> list[str]:
    command = [sys.executable, str(ota_script)]
    command.extend(["--config", str(ota_config), "--device-id", device, str(firmware)])
    return command


def _generate(args: argparse.Namespace) -> int:
    config_path = args.config.resolve()
    config, stack = _compose(config_path)
    written = write_output_tree(_output_dir(config_path), config, stack)
    sys.stdout.write(render_report(config, stack))
    sys.stdout.write("written files:\n")
    for path in written:
        sys.stdout.write(f"- {display_path(path)}\n")
    return 0


def _check(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config)
    sys.stdout.write(render_report(config, stack))
    return 0


def _status(args: argparse.Namespace) -> int:
    config_path = args.config.resolve()
    config = load_stack_config(config_path)
    status = inspect_stack_status(config, _output_dir(config_path))
    sys.stdout.write(render_stack_status(status))
    return 0


def _doctor(args: argparse.Namespace) -> int:
    sys.stdout.write("LSH stack doctor\n")
    try:
        config, _stack = _compose(args.config)
    except StackConfigError as exc:
        sys.stdout.write(f"problem: {exc}\n")
        sys.stdout.write(f"fix: {doctor_fix(str(exc))}\n")
        return 1

    warnings = project_warnings(config, _output_dir(args.config))
    if warnings:
        sys.stdout.write("warnings:\n")
        for warning in warnings:
            sys.stdout.write(f"- {warning}\n")
    else:
        sys.stdout.write("No stack configuration problems found.\n")
    return 0


def _explain(args: argparse.Namespace) -> int:
    config, stack = _compose(args.config)
    system_config = json_object(json_object(stack["coordinator"])["systemConfig"])
    system_devices = json_list(system_config["devices"], "coordinator.systemConfig.devices")
    system_entry = next(
        (
            json_object(raw_device)
            for raw_device in system_devices
            if json_object(raw_device).get("name") == args.device
        ),
        None,
    )
    bridge_key, bridge_entry = _bridge_entry(stack, args.device)
    if system_entry is None and bridge_entry is None:
        raise StackConfigError(f"unknown device: {args.device}")

    core_env = env_name(config.platformio.core_env_prefix, args.device)
    default_profile = default_bridge_profile(bridge_profiles(config))
    bridge_env = bridge_build_env(config, default_profile)

    sys.stdout.write(f"LSH stack explain: {args.device}\n")
    sys.stdout.write(f"- controller TOML: {display_path(config.core.devices)}\n")
    sys.stdout.write(f"- controller environment: {core_env}\n")
    if bridge_entry is not None:
        topics = json_object(bridge_entry.get("topics", {}))
        bridge = json_object(stack["bridge"])
        flags = [str(flag) for flag in json_list(bridge["platformioBuildFlags"])]
        sys.stdout.write(f"- bridge firmware environment: {bridge_env}\n")
        sys.stdout.write(f"- bridge USB upload: PlatformIO Upload on {bridge_env}\n")
        if config.deploy.bridge.ota is not None and default_profile.ota:
            sys.stdout.write(f"- bridge OTA target: LSH OTA {bridge_key or args.device}\n")
        else:
            sys.stdout.write("- bridge OTA target: not configured\n")
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


def _compose(config_path: Path) -> tuple[StackConfig, JsonObject]:
    config = load_stack_config(config_path)
    core_export = load_core_export(config.core)
    stack = compose_stack(config, core_export)
    return config, stack


def _missing_core_tool_error(exc: StackConfigError) -> bool:
    return "cannot find lsh-core generator" in str(exc)


def _bootstrap_core_if_needed(config: StackConfig) -> int:
    if not _should_bootstrap_core_project(config):
        return 0
    return bootstrap_core_project(config)


def _should_bootstrap_core_project(config: StackConfig) -> bool:
    if config.core.tool is not None or os.environ.get("LSH_CORE_TOOL"):
        return False
    project = config.platformio.core_project or config.core.devices.parent
    return not installed_lsh_core_tools(project)


def _validate_stack_ota_support(config: StackConfig) -> None:
    if config.deploy.bridge.ota is None:
        raise StackConfigError(
            f"configure [deploy.bridge.ota] before using {lsh_stack_command()} ota."
        )


def _selected_bridge_devices(
    available_devices: list[str],
    positional: list[str],
) -> list[str]:
    selected = [device.strip() for device in positional if device.strip()]
    if not selected:
        return available_devices

    known = set(available_devices)
    unknown = [device for device in selected if device not in known]
    if unknown:
        raise StackConfigError(
            "unknown bridge device(s): "
            + ", ".join(unknown)
            + ". Known devices: "
            + ", ".join(available_devices)
            + "."
        )
    return _deduplicate(selected)


def _bridge_project(config: StackConfig) -> Path:
    if config.platformio.bridge_project is None:
        raise StackConfigError(
            f"platformio.bridge_project is required for {lsh_stack_command()} ota."
        )
    return config.platformio.bridge_project


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _output_dir(config_path: Path) -> Path:
    return config_path.resolve().parent / DEFAULT_OUTPUT_DIR


def _print_setup_next_steps(config: StackConfig, stack: JsonObject, output_dir: Path) -> None:
    devices = device_names(stack)
    first_device = devices[0] if devices else "device"
    core_project = config.platformio.core_project or config.core.devices.parent
    bridge_project = config.platformio.bridge_project or config.path.parent
    core_env = env_name(config.platformio.core_env_prefix, first_device)
    bridge_env = bridge_build_env(config, default_bridge_profile(bridge_profiles(config)))

    sys.stdout.write("next steps:\n")
    sys.stdout.write(
        f"- core build: platformio run -d {display_path(core_project)} -e {core_env}\n"
    )
    sys.stdout.write(
        f"- bridge build: platformio run -d {display_path(bridge_project)} -e {bridge_env}\n"
    )
    if config.deploy.bridge.ota is not None:
        sys.stdout.write(f"- bridge OTA one: {_stack_ota_cli_command(config, first_device)}\n")
        sys.stdout.write(f"- bridge OTA all: {_stack_ota_cli_command(config)}\n")
    sys.stdout.write(f"- detailed guide: {display_path(output_dir / 'README.generated.md')}\n")
    sys.stdout.write(
        "- VSCode users can run the same environments from PlatformIO Project Tasks.\n"
    )


def _stack_ota_cli_command(config: StackConfig, device: str | None = None) -> str:
    args = () if device is None else (device,)
    return stack_command("ota", config, *args)


def _bridge_entry(stack: JsonObject, device: str) -> tuple[str | None, JsonObject | None]:
    bridge_devices = json_object(json_object(stack["bridge"])["devices"])
    for key, raw_device in bridge_devices.items():
        bridge_device = json_object(raw_device)
        if key == device or bridge_device.get("deviceName") == device:
            return key, bridge_device
    return None, None


if __name__ == "__main__":
    entrypoint()
