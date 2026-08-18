"""Helpers for rendering the current lsh-stack launcher command."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def lsh_stack_command() -> str:
    """Return the command users should run for this lsh-stack invocation."""
    zipapp = _zipapp_command()
    if zipapp is not None:
        return zipapp
    project = source_checkout_root()
    if project is None:
        return "lsh-stack"
    launcher = project / "lsh-stack.py"
    if launcher.is_file():
        return f"python {command_arg(launcher)}"
    return "python -m lsh_stack_config"


def source_checkout_root() -> Path | None:
    """Return the source checkout root when running from an editable checkout."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "lsh_stack_config").is_dir():
            return parent
    return None


def _zipapp_command() -> str | None:
    archive = Path(sys.argv[0])
    if archive.suffix != ".pyz" or not archive.is_file():
        return None
    return f"{command_arg(Path(sys.executable))} {command_arg(archive.resolve())}"


def command_arg(value: str | Path) -> str:
    """Quote one command argument for the current platform."""
    text = str(value)
    return subprocess.list2cmdline([text]) if os.name == "nt" else shlex.quote(text)
