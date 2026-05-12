"""Runtime helpers for the lsh-stack CLI."""

from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import StackConfigError
from .models import StackConfig
from .platformio_utils import read_platformio_config, section_refs


def bootstrap_core_project(config: StackConfig) -> int:
    """Build the core project once so PlatformIO installs lsh-core tools."""
    project = config.platformio.core_project or config.core.devices.parent
    platformio = platformio_invocation()
    if platformio is None:
        sys.stderr.write(
            "lsh-stack setup needs PlatformIO once to install lsh-core for this project.\n"
            f"Open {project} in VSCode with the PlatformIO extension and build the default "
            "core environment once, then rerun `lsh-stack setup`.\n"
            "Alternatively install the PlatformIO CLI and rerun this command.\n"
        )
        return 1

    command = [*platformio, "run", "-d", str(project)]
    for env in default_platformio_envs(project):
        command.extend(["-e", env])

    sys.stdout.write("lsh-core generator not found; building the core project once.\n")
    sys.stdout.write("running: " + " ".join(command) + "\n")
    sys.stdout.flush()
    completed = subprocess.run(  # noqa: S603 - PlatformIO path is resolved.
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
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
        "PlatformIO is required to build bridge firmware. Install the PlatformIO CLI, "
        "or build/upload from VSCode PlatformIO Project Tasks."
    )


def run_or_print(
    command: list[str],
    *,
    dry_run: bool,
    env: dict[str, str] | None = None,
) -> int:
    """Run a subprocess command, or print it in dry-run mode."""
    sys.stdout.write("running: " + " ".join(command) + "\n")
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
