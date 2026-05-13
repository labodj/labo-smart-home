"""Runtime helpers for the lsh-stack CLI."""

from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .commands import stack_command
from .errors import StackConfigError
from .models import StackConfig
from .paths import display_path
from .platformio_utils import read_platformio_config, section_refs


def bootstrap_core_project(config: StackConfig) -> int:
    """Build the core project once so PlatformIO installs lsh-core tools."""
    project = config.platformio.core_project or config.core.devices.parent
    platformio = platformio_invocation()
    if platformio is None:
        setup_command = _setup_command(config)
        envs = default_platformio_envs(project)
        env_text = ", ".join(envs) if envs else "the default core environment"
        sys.stderr.write(
            "lsh-stack setup cannot install lsh-core because the PlatformIO CLI "
            "is not available in this shell.\n"
            "Choose one path:\n"
            f"- Install the PlatformIO CLI, then run: {setup_command}\n"
            f"- Or open {project} in VSCode with the PlatformIO extension, build "
            f"{env_text}, then run: {setup_command}\n"
            "Why: the first core build downloads lsh-core and exposes the stack "
            "config generator used by lsh-stack.\n"
        )
        return 1

    command = [*platformio, "run", "-d", str(project)]
    for env in default_platformio_envs(project):
        command.extend(["-e", env])

    sys.stdout.write("lsh-core generator not found; building the core project once.\n")
    sys.stdout.write("running: " + format_command(command) + "\n")
    sys.stdout.flush()
    completed = subprocess.run(  # noqa: S603 - PlatformIO path is resolved.
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        env_text = ", ".join(default_platformio_envs(project)) or "the default core environment"
        sys.stderr.write(
            "lsh-core bootstrap build failed. Fix the PlatformIO error above, "
            f"or build {env_text} from VSCode PlatformIO Project Tasks, then "
            f"rerun: {_setup_command(config)}\n"
        )
    else:
        sys.stdout.write("lsh-core bootstrap build succeeded.\n")
    return int(completed.returncode)


def platformio_invocation() -> list[str] | None:
    """Return the user's PlatformIO invocation, if available."""
    executable = shutil.which("platformio")
    if executable is not None:
        return [executable]

    probe = subprocess.run(
        [sys.executable, "-m", "platformio", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "platformio"]
    return None


def required_platformio_invocation(*, dry_run: bool) -> list[str]:
    """Return PlatformIO or a dry-run placeholder; otherwise raise a clear error."""
    invocation = platformio_invocation()
    if invocation is not None:
        return invocation
    if dry_run:
        return ["platformio"]
    raise StackConfigError(
        "PlatformIO CLI is required because lsh-stack ota builds the bridge firmware first. "
        "Use --dry-run to inspect commands, install the PlatformIO CLI, or build/upload "
        "from VSCode PlatformIO Project Tasks."
    )


def run_or_print(
    command: list[str],
    *,
    dry_run: bool,
    env: dict[str, str] | None = None,
) -> int:
    """Run a subprocess command, or print it in dry-run mode."""
    sys.stdout.write("running: " + format_command(command) + "\n")
    sys.stdout.flush()
    if dry_run:
        return 0
    completed = subprocess.run(command, check=False, env=env)  # noqa: S603 - argv is explicit.
    return int(completed.returncode)


def subprocess_env_with_ota_password(
    ota_config: Path,
    *,
    dry_run: bool,
) -> dict[str, str] | None:
    """Return a subprocess env containing the OTA password when prompting is needed."""
    password_env = bridge_ota_password_env(ota_config)
    if password_env is None or password_env in os.environ or dry_run:
        return None
    if not sys.stdin.isatty():
        raise StackConfigError(
            f"{password_env} is not set and this terminal cannot prompt for it. "
            "Run from an interactive terminal so lsh-stack can ask for the password, "
            f"or provide {password_env} in the process environment for automation. "
            "Use --dry-run to inspect commands without a password."
        )
    env = os.environ.copy()
    env[password_env] = getpass.getpass(f"MQTT/OTA password ({password_env}): ")
    return env


def bridge_ota_password_env(ota_config: Path) -> str | None:
    """Read the broker password env var name from a generated OTA config."""
    try:
        raw = json.loads(ota_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    broker = raw.get("broker") if isinstance(raw, dict) else None
    if not isinstance(broker, dict):
        return None
    value = broker.get("password_env")
    return value if isinstance(value, str) and value else None


def default_platformio_envs(project: Path) -> list[str]:
    """Read the project's PlatformIO default environments."""
    parser = read_platformio_config(project)
    if parser is None:
        return []
    return section_refs(parser.get("platformio", "default_envs", fallback=""))


def format_command(command: list[str]) -> str:
    """Return a readable command line for status and dry-run output."""
    return " ".join(_format_command_arg(index, arg) for index, arg in enumerate(command))


def _setup_command(config: StackConfig) -> str:
    return stack_command("setup", config)


def _format_command_arg(index: int, arg: str) -> str:
    path = Path(arg)
    if index == 0 and path.name == "platformio":
        return "platformio"
    if path.is_absolute():
        return display_path(path)
    return arg
