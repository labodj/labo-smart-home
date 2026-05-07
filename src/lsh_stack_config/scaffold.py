"""Create starter LSH installation projects."""

from __future__ import annotations

import sys
from pathlib import Path

from .errors import StackConfigError
from .scaffold_templates import (
    BOOTSTRAP_BRIDGE_INI,
    BOOTSTRAP_CORE_INI,
    BRIDGE_MAIN_TEMPLATE,
    BRIDGE_PLATFORMIO_TEMPLATE,
    CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
    CORE_MAIN_TEMPLATE,
    CORE_PLATFORMIO_TEMPLATE,
    DEVICES_TEMPLATE,
    OVERRIDES_README,
    PROJECT_README_TEMPLATE,
    STACK_TEMPLATE,
)


def write_starter(path: Path, *, force: bool) -> int:
    """Write a complete starter project, or a single TOML template path."""
    if path.suffix == ".toml":
        return write_single_stack_template(path, force=force)

    lsh_stack_command = _lsh_stack_command()
    files = _starter_files(path, lsh_stack_command)
    conflicts = [target for target in files if target.exists() and not force]
    if conflicts:
        names = ", ".join(str(target) for target in conflicts)
        raise StackConfigError(f"starter files already exist: {names}; pass --force to overwrite.")

    path.mkdir(parents=True, exist_ok=True)
    (path / "generated").mkdir(exist_ok=True)
    for target, content in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _print_next_steps(path, lsh_stack_command)
    return 0


def write_single_stack_template(path: Path, *, force: bool) -> int:
    """Write only the stack TOML starter file."""
    if path.exists() and not force:
        raise StackConfigError(f"{path} already exists; pass --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STACK_TEMPLATE, encoding="utf-8")
    sys.stdout.write(f"wrote {path}\n")
    return 0


def _starter_files(path: Path, lsh_stack_command: str) -> dict[Path, str]:
    return {
        path / "README.md": PROJECT_README_TEMPLATE.format(lsh_stack_command=lsh_stack_command),
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


def _print_next_steps(path: Path, lsh_stack_command: str) -> None:
    sys.stdout.write(f"created starter LSH project at {path}\n")
    sys.stdout.write("next commands:\n")
    sys.stdout.write(f"- cd {path}\n")
    sys.stdout.write(
        "- build core_panel once from PlatformIO IDE, or run: "
        "platformio run -d core -e core_panel\n"
    )
    sys.stdout.write(f"- {lsh_stack_command} generate lsh_stack.toml --output-dir generated\n")
    sys.stdout.write(f"- {lsh_stack_command} check lsh_stack.toml\n")


def _lsh_stack_command() -> str:
    project = _source_checkout_root()
    if project is None:
        return "lsh-stack"
    launcher = project / "lsh-stack.py"
    if launcher.is_file():
        return f"python {_command_arg(launcher)}"
    return "python -m lsh_stack_config"


def _command_arg(path: Path) -> str:
    text = str(path)
    if not text or any(char.isspace() for char in text):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _source_checkout_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "lsh_stack_config").is_dir():
            return parent
    return None
