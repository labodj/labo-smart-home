"""Bridge operations over the existing PlatformIO and diagnostic tools."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .cli_runtime import (
    required_platformio_invocation,
    run_or_print,
    subprocess_env_with_ota_password,
)
from .commands import stack_command
from .deploy import bridge_usb_port, stack_build_plan
from .errors import StackConfigError
from .models import BridgeProfileSettings, JsonObject, StackConfig
from .render import write_output_tree
from .render_common import bridge_build_env


def select_bridge_profile(
    config: StackConfig, name: str | None, *, debug: bool
) -> BridgeProfileSettings:
    """Select a configured profile; debug shorthand only uses known template pairs."""
    profiles = config.platformio.bridge_profiles
    selected = next((p for p in profiles if p.name == name or (name is None and p.default)), None)
    if selected is None:
        raise StackConfigError(
            f"unknown bridge profile: {name}. "
            f"Available profiles: {', '.join(p.name for p in profiles)}. "
            f"Run `{stack_command('bridge', config, 'list')}` to see their environments."
        )
    if not debug:
        return selected
    pairs = {
        "lsh_bridge_release": "lsh_bridge_debug",
        "lsh_bridge_littlefs": "lsh_bridge_littlefs_debug",
    }
    if selected.base_env in pairs.values():
        return selected
    target = pairs.get(selected.base_env)
    matches = [p for p in profiles if target is not None and p.base_env == target]
    if len(matches) != 1:
        raise StackConfigError(
            "cannot safely choose a debug profile for this family; select --profile explicitly "
            "without --debug. Migration profiles are always explicit."
        )
    return matches[0]


def selected_devices(
    available: tuple[str, ...], devices: list[str], *, all_devices: bool
) -> list[str]:
    """Require an explicit target set before any device operation."""
    if all_devices and devices:
        raise StackConfigError("choose DEVICE or --all, not both.")
    selected = list(dict.fromkeys(available if all_devices else devices))
    if not selected:
        raise StackConfigError("select at least one DEVICE or use --all; see bridge list.")
    unknown = set(selected) - set(available)
    if unknown:
        raise StackConfigError(
            "unknown bridge device(s): "
            + ", ".join(sorted(unknown))
            + ". Known devices: "
            + ", ".join(available)
            + "."
        )
    return selected


def bridge_operation(args: argparse.Namespace, config: StackConfig, stack: JsonObject) -> int:
    """Build once per firmware, but require an explicit target/port for USB operations."""
    plan = stack_build_plan(config, stack)
    project = config.platformio.bridge_project or config.path.parent / "bridge"
    if args.action == "list":
        if (
            args.devices
            or args.all_devices
            or args.port
            or args.debug
            or args.profile
            or args.duration is not None
        ):
            raise StackConfigError("bridge list does not accept target/profile options.")
        sys.stdout.write("devices: " + ", ".join(plan.bridge_devices) + "\n")
        sys.stdout.writelines(
            f"{p.name}{' (default)' if p.default else ''}: {bridge_build_env(config, p)}\n"
            for p in plan.bridge_profiles
        )
        return 0
    if args.action == "diagnose":
        if args.port or args.debug or args.profile:
            raise StackConfigError("bridge diagnose does not accept --port/--debug/--profile.")
        devices = selected_devices(plan.bridge_devices, args.devices, all_devices=args.all_devices)
        return _diagnose(args, config, stack, project, devices)
    if args.duration is not None:
        raise StackConfigError("--duration is only supported by bridge diagnose.")
    profile = select_bridge_profile(config, args.profile, debug=args.debug)
    environment = bridge_build_env(config, profile)
    port = _serial_port(args, config, plan.bridge_devices)
    sys.stdout.write(f"bridge {args.action}: profile {profile.name}, environment {environment}\n")
    pio = required_platformio_invocation(dry_run=args.dry_run)
    if args.action == "monitor":
        command = [
            *pio,
            "device",
            "monitor",
            "-d",
            str(project),
            "-e",
            environment,
            "--port",
            str(port),
        ]
    else:
        command = [*pio, "run", "-d", str(project), "-e", environment]
        if args.action != "build":
            command.extend(["-t", args.action])
        if port:
            command.extend(["--upload-port", port])
    if not args.dry_run:
        write_output_tree(config.path.parent / "generated", config, stack)
    return run_or_print(command, dry_run=args.dry_run)


def _serial_port(
    args: argparse.Namespace, config: StackConfig, available: tuple[str, ...]
) -> str | None:
    """Validate USB selection before regeneration or starting any PlatformIO process."""
    port = args.port
    if args.action in ("upload", "monitor"):
        devices = selected_devices(available, args.devices, all_devices=args.all_devices)
        if args.all_devices or len(devices) != 1:
            raise StackConfigError("USB upload/monitor requires exactly one explicit DEVICE.")
        port = port or bridge_usb_port(config, devices[0])
        if not port:
            raise StackConfigError("specify --port for this device, or configure its usb_port.")
    elif args.port:
        raise StackConfigError("--port is only supported by bridge upload/monitor.")
    elif args.devices or args.all_devices:
        selected_devices(available, args.devices, all_devices=args.all_devices)
    return str(port) if port else None


def _diagnostic_tool(project: Path) -> Path:
    libdeps = project / ".pio" / "libdeps"
    candidates = sorted(libdeps.glob("*/lsh-bridge/tools/mqtt_diagnostics.py"))
    for marker in sorted(libdeps.glob("*/lsh-bridge.pio-link")):
        try:
            link = json.loads(marker.read_text(encoding="utf-8"))
            uri, cwd = link["spec"]["uri"], link["cwd"]
            if isinstance(uri, str) and uri.startswith("symlink://"):
                root = Path(uri.removeprefix("symlink://"))
                candidates.append(Path(cwd) / root / "tools/mqtt_diagnostics.py")
        except (OSError, ValueError, KeyError, TypeError):
            continue
    tool = next((p for p in candidates if p.is_file()), None)
    if tool is None:
        raise StackConfigError(
            "installed lsh-bridge lacks tools/mqtt_diagnostics.py; run setup with a version "
            "containing the diagnostics, or enable dev local first."
        )
    return tool


def _diagnose(
    args: argparse.Namespace,
    config: StackConfig,
    stack: JsonObject,
    project: Path,
    devices: list[str],
) -> int:
    if config.deploy.bridge.ota is None:
        raise StackConfigError("configure [deploy.bridge.ota] for MQTT connection settings.")
    uv = shutil.which("uv")
    if uv is None and not args.dry_run:
        raise StackConfigError("MQTT diagnostics require uv to run the shared lsh-bridge script.")
    tool = _diagnostic_tool(project)
    settings = config.path.parent / "generated" / "bridge-ota.json"
    env = None
    if not args.dry_run:
        write_output_tree(settings.parent, config, stack)
        env = subprocess_env_with_ota_password(settings, dry_run=False)
    # No passthrough of active/burst flags: this command is deliberately passive.
    return run_or_print(
        [
            uv or "uv",
            "run",
            "--script",
            str(tool),
            *devices,
            "--config",
            str(settings),
            "--duration",
            str(args.duration if args.duration is not None else 30),
        ],
        dry_run=args.dry_run,
        env=env,
    )
