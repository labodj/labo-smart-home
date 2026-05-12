"""Create starter LSH installation projects."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from .errors import StackConfigError
from .launcher import lsh_stack_command, source_checkout_root
from .models import StackConfig
from .platformio_utils import path_for_platformio
from .render_common import env_name
from .scaffold_templates import (
    BOOTSTRAP_BRIDGE_INI,
    BOOTSTRAP_CORE_INI,
    BRIDGE_MAIN_TEMPLATE,
    BRIDGE_PLATFORMIO_TEMPLATE,
    CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
    CORE_MAIN_TEMPLATE,
    CORE_PLATFORMIO_TEMPLATE,
    CORE_PROJECT_README_TEMPLATE,
    DEVICES_TEMPLATE,
    ETL_PROFILE_OVERRIDE_TEMPLATE,
    OVERRIDES_README,
    PROJECT_README_TEMPLATE,
    STACK_TEMPLATE,
)

GENERATED_DIR_NAME = "generated"


def write_starter(path: Path, *, force: bool) -> int:
    """Write a complete starter project."""
    _validate_project_dir(path, command="lsh-stack new")
    command = lsh_stack_command()
    files = _starter_files(path, command)
    conflicts = [target for target in files if target.exists() and not force]
    if conflicts:
        raise StackConfigError(_conflict_message("starter files", conflicts))

    path.mkdir(parents=True, exist_ok=True)
    (path / "generated").mkdir(exist_ok=True)
    for target, content in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _print_next_steps(path, command)
    return 0


def write_core_starter(path: Path, *, force: bool) -> int:
    """Write a standalone lsh-core PlatformIO project."""
    _validate_project_dir(path, command="lsh-stack new-core")
    files = _core_starter_files(path)
    conflicts = [target for target in files if target.exists() and not force]
    if conflicts:
        raise StackConfigError(_conflict_message("core starter files", conflicts))

    path.mkdir(parents=True, exist_ok=True)
    for target, content in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    sys.stdout.write(f"created standalone LSH core project at {path}\n")
    sys.stdout.write("next commands:\n")
    sys.stdout.write(f"- cd {path}\n")
    sys.stdout.write("- platformio run -e core_panel\n")
    return 0


def _validate_project_dir(path: Path, *, command: str) -> None:
    if path.suffix == ".toml":
        raise StackConfigError(
            f"{command} creates a project directory; pass a directory path, not a TOML file."
        )
    if path.exists() and not path.is_dir():
        raise StackConfigError(f"{command} target exists but is not a directory: {path}")


def _starter_files(path: Path, command: str) -> dict[Path, str]:
    return {
        path / "README.md": PROJECT_README_TEMPLATE.format(lsh_stack_command=command),
        path / "lsh_stack.toml": STACK_TEMPLATE,
        path / "core" / "lsh_devices.toml": DEVICES_TEMPLATE,
        path / "core" / "platformio.ini": CORE_PLATFORMIO_TEMPLATE,
        path / "bridge" / "platformio.ini": BRIDGE_PLATFORMIO_TEMPLATE,
        path / "generated" / "platformio-core.ini": BOOTSTRAP_CORE_INI,
        path / "generated" / "platformio-bridge.ini": BOOTSTRAP_BRIDGE_INI,
        path / "core" / "scripts" / "lsh_core_bootstrap.py": CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
        path / "core" / "src" / "main.cpp": CORE_MAIN_TEMPLATE,
        path / "bridge" / "src" / "main.cpp": BRIDGE_MAIN_TEMPLATE,
        path / "overrides" / "README.md": OVERRIDES_README,
    }


def _core_starter_files(path: Path) -> dict[Path, str]:
    platformio_ini = CORE_PLATFORMIO_TEMPLATE.replace(
        "extra_configs = ../generated/platformio-core.ini",
        "extra_configs = generated/platformio-core.ini",
    )
    platformio_ini = platformio_ini.replace("Optional stack overlay", "Optional generated overlay")
    return {
        path / "README.md": CORE_PROJECT_README_TEMPLATE,
        path / "lsh_devices.toml": DEVICES_TEMPLATE,
        path / "platformio.ini": platformio_ini,
        path / "generated" / "platformio-core.ini": BOOTSTRAP_CORE_INI,
        path / "scripts" / "lsh_core_bootstrap.py": CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
        path / "src" / "main.cpp": CORE_MAIN_TEMPLATE,
    }


def ensure_project_scaffolds(config: StackConfig) -> list[Path]:
    """Create missing core/bridge PlatformIO shells referenced by an existing stack."""
    project_dir = config.path.parent
    generated_dir = project_dir / GENERATED_DIR_NAME
    core_project = config.platformio.core_project or config.core.devices.parent
    bridge_project = config.platformio.bridge_project or project_dir / "bridge"
    first_device = config.core.selected_devices[0] if config.core.selected_devices else "panel"
    core_env = env_name(config.platformio.core_env_prefix, first_device)

    files: dict[Path, str] = {}
    if not (core_project / "platformio.ini").exists():
        files.update(
            _core_project_files(
                core_project=core_project,
                generated_dir=generated_dir,
                devices_path=config.core.devices,
                core_env=core_env,
                device=first_device,
            )
        )
    if not (bridge_project / "platformio.ini").exists():
        files.update(
            _bridge_project_files(
                bridge_project=bridge_project,
                generated_dir=generated_dir,
            )
        )
    if not (project_dir / "overrides").exists():
        files[project_dir / "overrides" / "README.md"] = OVERRIDES_README

    written: list[Path] = []
    for target, content in files.items():
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def _core_project_files(
    *,
    core_project: Path,
    generated_dir: Path,
    devices_path: Path,
    core_env: str,
    device: str,
) -> dict[Path, str]:
    core_fragment = path_for_platformio(generated_dir / "platformio-core.ini", core_project)
    devices = path_for_platformio(devices_path, core_project)
    platformio_ini = CORE_PLATFORMIO_TEMPLATE.replace(
        "extra_configs = ../generated/platformio-core.ini",
        f"extra_configs = {core_fragment}",
    )
    platformio_ini = platformio_ini.replace(
        "default_envs = core_panel",
        f"default_envs = {core_env}",
    )
    platformio_ini = platformio_ini.replace("[env:core_panel]", f"[env:{core_env}]")
    platformio_ini = platformio_ini.replace(
        "custom_lsh_config = lsh_devices.toml",
        f"custom_lsh_config = {devices}",
    )
    platformio_ini = platformio_ini.replace(
        "custom_lsh_device = panel",
        f"custom_lsh_device = {device}",
    )
    return {
        core_project / "platformio.ini": platformio_ini,
        core_project / "scripts" / "lsh_core_bootstrap.py": CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
        core_project / "src" / "main.cpp": CORE_MAIN_TEMPLATE,
        **_core_optional_files(core_project=core_project, devices_path=devices_path),
    }


def _core_optional_files(*, core_project: Path, devices_path: Path) -> dict[Path, str]:
    header = _etl_profile_override_header(devices_path)
    if header is None:
        return {}
    return {core_project / "include" / header: ETL_PROFILE_OVERRIDE_TEMPLATE}


def _etl_profile_override_header(devices_path: Path) -> str | None:
    try:
        raw = tomllib.loads(devices_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    features = raw.get("features")
    if not isinstance(features, dict):
        return None
    header = features.get("etl_profile_override_header")
    return header if isinstance(header, str) and header else None


def _bridge_project_files(*, bridge_project: Path, generated_dir: Path) -> dict[Path, str]:
    bridge_fragment = path_for_platformio(
        generated_dir / "platformio-bridge.ini",
        bridge_project,
    )
    platformio_ini = BRIDGE_PLATFORMIO_TEMPLATE.replace(
        "extra_configs = ../generated/platformio-bridge.ini",
        f"extra_configs = {bridge_fragment}",
    )
    return {
        bridge_project / "platformio.ini": platformio_ini,
        bridge_project / "src" / "main.cpp": BRIDGE_MAIN_TEMPLATE,
    }


def _print_next_steps(path: Path, lsh_stack_command: str) -> None:
    sys.stdout.write(f"created starter LSH project at {path}\n")
    sys.stdout.write("next commands:\n")
    sys.stdout.write(f"- cd {path}\n")
    sys.stdout.write(f"- {lsh_stack_command} setup\n")
    sys.stdout.write(
        "If PlatformIO is only available inside VSCode, open core/ and build "
        "core_panel once from Project Tasks, then run setup again.\n"
    )


def _source_checkout_root() -> Path | None:
    return source_checkout_root()


def _conflict_message(label: str, conflicts: list[Path]) -> str:
    lines = [f"{label} already exist:"]
    lines.extend(f"- {target}" for target in conflicts)
    lines.append("Pass --force to overwrite them.")
    return "\n".join(lines)
