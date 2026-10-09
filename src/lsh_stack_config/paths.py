"""Path presentation helpers for CLI output and generated docs."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import StackConfigError


def stack_config_path(explicit: Path | None) -> Path:
    """Prefer an explicit config; otherwise find the nearest installation root."""
    if explicit is not None:
        return absolute_path(explicit)
    current = Path.cwd()
    for directory in (current, *current.parents):
        candidate = directory / "lsh_stack.toml"
        if candidate.is_file():
            return candidate
    raise StackConfigError(
        "cannot find lsh_stack.toml here or in a parent directory; "
        "enter your stack directory or pass --config PATH. Start with new PROJECT_DIR."
    )


def absolute_path(path: Path) -> Path:
    """Return an absolute path without resolving symlinks."""
    return Path(os.path.abspath(path.expanduser()))  # noqa: PTH100


def display_path(path: Path, *, base_dir: Path | None = None) -> str:
    """Return a readable path, relative to ``base_dir`` when possible."""
    root = absolute_path(Path.cwd() if base_dir is None else base_dir)
    candidate = absolute_path(path)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return str(path)
    return "." if str(relative) == "." else str(relative)


def path_from(base_dir: Path, path: Path) -> str:
    """Return ``path`` relative to ``base_dir`` for shell commands and docs."""
    return os.path.relpath(path, base_dir)
