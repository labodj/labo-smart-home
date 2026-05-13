"""Helpers for rendering lsh-stack commands in user-facing output."""

from __future__ import annotations

from pathlib import Path

from .launcher import lsh_stack_command
from .models import StackConfig
from .paths import display_path, path_from


def stack_command(
    command: str,
    config: StackConfig | None = None,
    *args: str,
    config_base_dir: Path | None = None,
) -> str:
    """Return a command line for the current lsh-stack launcher."""
    parts = [lsh_stack_command(), command]
    if config is not None and config.path.name != "lsh_stack.toml":
        if config_base_dir is None:
            config_path = display_path(config.path)
        else:
            config_path = path_from(config_base_dir, config.path)
        parts.extend(["--config", config_path])
    parts.extend(args)
    return " ".join(parts)
