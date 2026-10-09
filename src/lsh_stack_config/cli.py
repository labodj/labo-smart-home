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
from .deploy import pio_command, stack_build_plan
from .development import development_status, switch_dependencies
from .doctor import doctor_fix, project_warnings
from .errors import StackConfigError
from .launcher import lsh_stack_command
from .models import JsonObject, StackConfig
from .operations import bridge_operation, select_bridge_profile, selected_devices
from .parser import load_stack_config
from .paths import absolute_path, display_path, stack_config_path
from .render import generated_file_problems, render_report, stack_json, write_output_tree
from .render_common import (
    bridge_build_env,
    bridge_devices,
    core_build_env,
    json_list,
    json_object,
)
from .scaffold import ensure_project_scaffolds, write_core_starter, write_starter
from .status import inspect_stack_status, render_stack_status
from .template_updates import update_templates

if TYPE_CHECKING:
    from collections.abc import Sequence

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
        "core": _core,
        "bridge": _bridge,
        "templates": _templates,
        "dev": _dev,
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
        for field in ("config", "config_path"):
            if hasattr(args, field):
                setattr(args, field, stack_config_path(getattr(args, field)))
        return handler(args)
    except StackConfigError as exc:
        sys.stderr.write(f"lsh-stack error: {exc}\n")
        return 2
    except (OSError, EOFError, UnicodeError) as exc:
        sys.stderr.write(f"lsh-stack error: {exc}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("\nCancelled; no further operations will run.\n")
        return 130


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
  {launcher} core list

Build controllers or switch dependencies (never uploads):
  {launcher} core build --all
  {launcher} dev local
  {launcher} dev release

After the first USB bridge flash and Homie setup:
  {launcher} ota --all --dry-run
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
    new.add_argument(
        "--interactive", action="store_true", help="ask for device names and MQTT settings"
    )

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
        help="bootstrap, generate, check and build an installation project",
        description=(
            "Create missing project shells, generate outputs and build the default firmware."
        ),
        formatter_class=formatter,
        epilog=f"""\
Run from the stack project directory:
  {launcher} setup

PlatformIO CLI is required because setup verifies every selected controller and
the default bridge firmware before reporting success.
""",
    )
    _add_config_option(setup)

    ota = subparsers.add_parser(
        "ota",
        help="build and OTA-upload bridge firmware",
        description="Build a bridge firmware profile and OTA-upload it.",
        formatter_class=formatter,
        epilog=f"""\
Examples:
  {launcher} ota --all --dry-run
  {launcher} ota panel
  {launcher} ota panel lights
""",
    )
    ota.add_argument(
        "device_args",
        nargs="*",
        metavar="DEVICE",
        help="bridge device ids to update (or explicitly use --all)",
    )
    ota.add_argument(
        "--config",
        dest="config_path",
        type=Path,
        default=None,
        help="explicit config path (otherwise search this directory and its parents)",
    )
    ota.add_argument("--dry-run", action="store_true", help="print commands without running them")
    ota.add_argument("--list-devices", action="store_true", help="print bridge device ids and exit")
    ota.add_argument("--profile", help="bridge profile name (default: configured default)")
    ota.add_argument("--all", action="store_true", dest="all_devices", help="update all bridges")
    ota.add_argument("--debug", action="store_true", help="debug variant of the selected family")

    core = subparsers.add_parser(
        "core",
        help="list, build, clean or USB-upload controllers",
        description="Use configured controller names and profiles, without remembering env names.",
        formatter_class=formatter,
        epilog=f"""\
Examples:
  {launcher} core list
  {launcher} core build --all
  {launcher} core build panel --profile debug
  {launcher} core clean --all
  {launcher} core upload panel --port /dev/ttyACM0

USB upload accepts exactly one device. Build and clean require DEVICE or --all.
""",
    )
    core.add_argument("action", choices=("list", "build", "clean", "upload"))
    core.add_argument("devices", nargs="*", metavar="DEVICE")
    core.add_argument("--all", action="store_true", dest="all_devices", help="all controllers")
    core.add_argument("--profile", help="core profile name (default: configured default)")
    core.add_argument("--debug", action="store_true", help="use the configured debug profile")
    core.add_argument("--port", help="USB port for a single upload")
    core.add_argument("--dry-run", action="store_true", help="print commands without changes")
    _add_config_option(core)

    _add_bridge_and_template_commands(subparsers)

    dev = subparsers.add_parser(
        "dev",
        help="show or switch release/local dependencies, then regenerate and build",
        description="Switch local libraries on/off without editing release dependency pins.",
    )
    dev.add_argument("mode", choices=("status", "local", "release"))
    dev.add_argument(
        "--repositories-root",
        type=Path,
        help="directory containing lsh-core, lsh-bridge and homie-esp8266 (default: parent)",
    )
    dev.add_argument(
        "--no-build",
        action="store_true",
        help="only switch dependency files; run setup afterwards to regenerate and verify",
    )
    _add_config_option(dev)

    command_help = {
        "generate": "generate stack artifacts",
        "check": "validate the stack configuration",
        "status": "show setup progress and the next action",
    }
    for command, help_text in command_help.items():
        child = subparsers.add_parser(command, help=help_text, formatter_class=formatter)
        _add_config_option(child)
    doctor = subparsers.add_parser(
        "doctor",
        help="diagnose stack configuration problems",
        formatter_class=formatter,
    )
    _add_config_option(doctor)
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when non-fatal warnings are found",
    )
    explain = subparsers.add_parser(
        "explain",
        help="explain generated config for one device",
        formatter_class=formatter,
    )
    explain.add_argument("device", metavar="DEVICE", help="controller device name to explain")
    _add_config_option(explain)
    return parser


def _add_bridge_and_template_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    bridge = subparsers.add_parser("bridge", help="build, USB upload, monitor or diagnose bridges")
    bridge.add_argument(
        "action", choices=("list", "build", "clean", "upload", "monitor", "diagnose")
    )
    bridge.add_argument("devices", nargs="*", metavar="DEVICE")
    bridge.add_argument("--all", action="store_true", dest="all_devices")
    bridge.add_argument("--profile", help="configured firmware profile")
    bridge.add_argument("--debug", action="store_true", help="debug variant of the selected family")
    bridge.add_argument("--port", help="explicit serial port for upload or monitor")
    bridge.add_argument(
        "--duration", type=int, default=None, help="passive diagnostic duration (default 30s)"
    )
    bridge.add_argument("--dry-run", action="store_true", help="show commands without running them")
    _add_config_option(bridge)
    templates = subparsers.add_parser("templates", help="check/diff/apply safe template updates")
    templates.add_argument("action", choices=("check", "diff", "apply"))
    _add_config_option(templates)


def _add_config_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="explicit config path (otherwise search this directory and its parents)",
    )


def _new(args: argparse.Namespace) -> int:
    return write_starter(absolute_path(args.path), force=args.force, interactive=args.interactive)


def _templates(args: argparse.Namespace) -> int:
    return update_templates(load_stack_config(args.config), action=args.action)


def _new_core(args: argparse.Namespace) -> int:
    return write_core_starter(absolute_path(args.path), force=args.force)


def _core(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    config, stack = _compose(config_path)
    plan = stack_build_plan(config, stack)
    if args.action == "list":
        if args.devices or args.all_devices or args.port or args.debug or args.profile:
            raise StackConfigError("core list does not accept target/profile options.")
        for listed_profile in plan.core_profiles:
            suffix = " (default)" if listed_profile.default else ""
            sys.stdout.write(f"{listed_profile.name}{suffix}:\n")
            for device in plan.core_devices:
                sys.stdout.write(f"  {device}: {core_build_env(config, device, listed_profile)}\n")
        return 0
    devices = _selected_core_devices(args, plan.core_devices)
    if args.debug:
        if args.profile not in (None, "release", "debug"):
            raise StackConfigError("select a custom debug profile explicitly without --debug.")
        args.profile = "debug"
    profile = next(
        (profile for profile in plan.core_profiles if profile.name == args.profile),
        plan.default_core_profile if args.profile is None else None,
    )
    if profile is None:
        raise StackConfigError(
            f"unknown core profile: {args.profile}. "
            f"Available profiles: {', '.join(p.name for p in plan.core_profiles)}. "
            f"Run `{stack_command('core', config, 'list')}` to see their environments."
        )
    platformio = required_platformio_invocation(dry_run=args.dry_run)
    project = config.platformio.core_project or config.core.devices.parent
    command = pio_command(
        str(project),
        [core_build_env(config, device, profile) for device in devices],
        target=None if args.action == "build" else args.action,
    )
    command = [*platformio, *command[1:]]
    if args.port:
        command.extend(["--upload-port", args.port])
    if not args.dry_run:
        write_output_tree(_output_dir(config_path), config, stack)
    return run_or_print(command, dry_run=args.dry_run)


def _bridge(args: argparse.Namespace) -> int:
    if args.duration is not None and args.duration <= 0:
        raise StackConfigError("--duration must be positive.")
    config, stack = _compose(args.config)
    return bridge_operation(args, config, stack)


def _selected_core_devices(args: argparse.Namespace, available: tuple[str, ...]) -> list[str]:
    if args.all_devices and args.devices:
        raise StackConfigError("choose DEVICE or --all, not both.")
    devices = list(dict.fromkeys(available if args.all_devices else args.devices))
    if not devices:
        raise StackConfigError("select at least one DEVICE or use --all; see core list.")
    unknown = set(devices) - set(available)
    if unknown:
        raise StackConfigError(
            "unknown core device(s): "
            + ", ".join(sorted(unknown))
            + ". Known devices: "
            + ", ".join(available)
            + "."
        )
    if args.action == "upload" and (args.all_devices or len(devices) != 1):
        raise StackConfigError("USB upload requires exactly one explicit DEVICE, never --all.")
    if args.port and args.action != "upload":
        raise StackConfigError("--port is only supported by core upload.")
    return devices


def _dev(args: argparse.Namespace) -> int:
    config = load_stack_config(absolute_path(args.config))
    if args.mode == "status":
        return development_status(config)
    root = absolute_path(args.repositories_root or config.path.parent.parent)
    # Reject an explicit tool pin: otherwise "release" could still execute a local tool.
    if config.core.tool is not None:
        raise StackConfigError("remove [core].tool before using dev; tool selection is automatic.")
    tool = switch_dependencies(config, root, local=args.mode == "local")
    if args.no_build:
        sys.stdout.write("Dependencies changed; run setup to regenerate and verify firmware.\n")
        return 0
    previous = os.environ.pop("LSH_CORE_TOOL", None)
    if tool is not None:
        os.environ["LSH_CORE_TOOL"] = str(tool)
    try:
        return _setup(args)
    finally:
        os.environ.pop("LSH_CORE_TOOL", None)
        if previous is not None:
            os.environ["LSH_CORE_TOOL"] = previous


def _setup(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    output_dir = _output_dir(config_path)
    scaffold_config = load_stack_config(config_path)
    sys.stdout.write("[1/4] Checking prerequisites\n")
    try:
        required_platformio_invocation(dry_run=False)
    except StackConfigError as exc:
        sys.stderr.write(f"{exc}\nThen rerun: {stack_command('setup', scaffold_config)}\n")
        return 1
    if not scaffold_config.core.devices.is_file():
        raise StackConfigError(f"core configuration not found: {scaffold_config.core.devices}")
    sys.stdout.write("[2/4] Preparing projects and installing generator\n")
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

    sys.stdout.write("[3/4] Validating configuration and generating files\n")
    written = write_output_tree(output_dir, config, stack)
    _print_setup_report(config, stack, output_dir, written, scaffolded)

    sys.stdout.write("[4/4] Building every selected controller and the default bridge\n")
    build_result = _build_stack_firmware(config, stack)
    if build_result != 0:
        return build_result

    sys.stdout.write("setup complete\n")
    _print_setup_next_steps(config, stack, output_dir)
    return 0


def _print_setup_report(
    config: StackConfig,
    stack: JsonObject,
    output_dir: Path,
    written: list[Path],
    scaffolded: list[Path],
) -> None:
    """Print generated files, diagnostics and newly scaffolded project files."""
    sys.stdout.write(render_report(config, stack))
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


def _validate_ota_selection(args: argparse.Namespace) -> None:
    """Reject ambiguous selectors before invoking the generator or any subprocess."""
    if args.list_devices and (args.device_args or args.all_devices or args.debug or args.profile):
        raise StackConfigError("ota --list-devices does not accept target/profile options.")
    if not args.list_devices and (bool(args.device_args) == args.all_devices):
        raise StackConfigError("choose DEVICE or --all, not both; see ota --list-devices.")


def _ota(args: argparse.Namespace) -> int:
    _validate_ota_selection(args)
    config_path = absolute_path(args.config_path)
    output_dir = _output_dir(config_path)
    config, stack = _compose(config_path)
    available_devices = list(bridge_devices(stack))
    if args.list_devices:
        sys.stdout.write("\n".join(available_devices) + ("\n" if available_devices else ""))
        return 0

    _validate_stack_ota_support(config)
    targets = selected_devices(
        tuple(available_devices), args.device_args, all_devices=args.all_devices
    )
    profile = select_bridge_profile(config, args.profile, debug=args.debug)
    if not profile.ota:
        raise StackConfigError(f"bridge profile {profile.name} has ota = false.")

    bridge_project = _bridge_project(config)
    build_env = bridge_build_env(config, profile)
    sys.stdout.write(f"OTA targets: {', '.join(targets)}; profile: {profile.name} ({build_env})\n")
    firmware = bridge_project / ".pio" / "build" / build_env / "firmware.bin"
    ota_script = output_dir / "bridge-ota.py"
    ota_config = output_dir / "bridge-ota.json"
    env = None
    if not args.dry_run:
        write_output_tree(output_dir, config, stack)
        if not ota_script.is_file() or not ota_config.is_file():
            raise StackConfigError("generated bridge OTA files are missing; run setup first.")
        env = subprocess_env_with_ota_password(ota_config, dry_run=False)

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
    outcomes = []
    for device in targets:
        command = _bridge_ota_command_args(
            ota_script=ota_script,
            ota_config=ota_config,
            device=device,
            firmware=firmware,
        )
        result = run_or_print(command, dry_run=args.dry_run, env=env)
        if result != 0:
            failures += 1
        state = (
            "planned"
            if args.dry_run
            else "OK (updated or already current)"
            if result == 0
            else f"FAILED ({result})"
        )
        outcomes.append(f"- {device}: {state}")

    sys.stdout.write("OTA summary:\n" + "\n".join(outcomes) + "\n")

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
    config_path = absolute_path(args.config)
    config, stack = _compose(config_path)
    written = write_output_tree(_output_dir(config_path), config, stack)
    sys.stdout.write(render_report(config, stack))
    sys.stdout.write("written files:\n")
    for path in written:
        sys.stdout.write(f"- {display_path(path)}\n")
    return 0


def _check(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    config, stack = _compose(config_path)
    sys.stdout.write(render_report(config, stack))
    return 0


def _status(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    config = load_stack_config(config_path)
    status = inspect_stack_status(config, _output_dir(config_path))
    sys.stdout.write(render_stack_status(status))
    return 0


def _doctor(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    sys.stdout.write("LSH stack doctor\n")
    try:
        config, stack = _compose(config_path)
    except StackConfigError as exc:
        sys.stdout.write(f"problem: {exc}\n")
        sys.stdout.write(f"fix: {doctor_fix(str(exc))}\n")
        return 1

    problems = generated_file_problems(_output_dir(config_path), config, stack)
    if problems:
        sys.stdout.write("generated files need attention:\n" + "\n".join(problems) + "\n")
        sys.stdout.write(
            f"fix: run `{stack_command('generate', config)}`, "
            f"then `{stack_command('doctor', config)}`.\n"
        )
        return 1
    warnings = project_warnings(config, _output_dir(config_path))
    if warnings:
        sys.stdout.write("warnings:\n")
        for warning in warnings:
            sys.stdout.write(f"- {warning}\n")
        if getattr(args, "strict", False):
            return 1
    else:
        sys.stdout.write("No stack configuration problems found.\n")
    return 0


def _explain(args: argparse.Namespace) -> int:
    config_path = absolute_path(args.config)
    config, stack = _compose(config_path)
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
        names = sorted(
            {str(json_object(device)["name"]) for device in system_devices}
            | set(bridge_devices(stack))
        )
        raise StackConfigError(f"unknown device: {args.device}. Known devices: {', '.join(names)}.")

    plan = stack_build_plan(config, stack)
    core_env = core_build_env(config, args.device, plan.default_core_profile)
    default_profile = plan.default_bridge_profile
    bridge_env = plan.default_bridge_env

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
    # A generated fragment can contain paths from an older project location. The
    # standalone core environment is the portable bootstrap source and setup
    # recreates this disposable fragment immediately after dependency installation.
    generated_core_fragment = config.path.parent / DEFAULT_OUTPUT_DIR / "platformio-core.ini"
    generated_core_fragment.unlink(missing_ok=True)
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


def _bridge_project(config: StackConfig) -> Path:
    if config.platformio.bridge_project is None:
        raise StackConfigError(
            f"platformio.bridge_project is required for {lsh_stack_command()} ota."
        )
    return config.platformio.bridge_project


def _output_dir(config_path: Path) -> Path:
    return absolute_path(config_path).parent / DEFAULT_OUTPUT_DIR


def _build_stack_firmware(config: StackConfig, stack: JsonObject) -> int:
    """Build every selected core plus the default wide bridge firmware."""
    plan = stack_build_plan(config, stack)
    platformio = required_platformio_invocation(dry_run=False)
    core_project = config.platformio.core_project or config.core.devices.parent
    bridge_project = config.platformio.bridge_project or config.path.parent / "bridge"

    core_command = [*platformio, "run", "-d", str(core_project)]
    for device in plan.core_devices:
        core_command.extend(["-e", core_build_env(config, device, plan.default_core_profile)])

    sys.stdout.write("verifying firmware builds:\n")
    if plan.core_devices and run_or_print(core_command, dry_run=False) != 0:
        sys.stderr.write("lsh-stack setup stopped: controller firmware build failed.\n")
        return 1

    bridge_command = [
        *platformio,
        "run",
        "-d",
        str(bridge_project),
        "-e",
        plan.default_bridge_env,
    ]
    if run_or_print(bridge_command, dry_run=False) != 0:
        sys.stderr.write("lsh-stack setup stopped: bridge firmware build failed.\n")
        return 1

    sys.stdout.write("firmware builds succeeded\n")
    return 0


def _print_setup_next_steps(config: StackConfig, stack: JsonObject, output_dir: Path) -> None:
    plan = stack_build_plan(config, stack)
    first_device = plan.core_devices[0] if plan.core_devices else "device"
    sys.stdout.write("next steps (nothing has been flashed):\n")
    sys.stdout.write(f"- review one device: {stack_command('explain', config, first_device)}\n")
    sys.stdout.write(
        f"- USB upload, after checking wiring/port: "
        f"{stack_command('bridge', config, 'upload', first_device, '--port', '<PORT>')}\n"
    )
    sys.stdout.write(f"- Node-RED: import {display_path(output_dir / 'node-red-flow.json')}\n")
    if config.deploy.bridge.ota is not None:
        sys.stdout.write(f"- bridge OTA one: {_stack_ota_cli_command(config, first_device)}\n")
        sys.stdout.write(f"- bridge OTA all: {_stack_ota_cli_command(config)}\n")
    sys.stdout.write(f"- detailed guide: {display_path(output_dir / 'README.generated.md')}\n")
    sys.stdout.write(
        "- VSCode users can run the same environments from PlatformIO Project Tasks.\n"
    )


def _stack_ota_cli_command(config: StackConfig, device: str | None = None) -> str:
    args = ("--all",) if device is None else (device,)
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
