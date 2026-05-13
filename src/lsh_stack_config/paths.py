"""Path presentation helpers for CLI output and generated docs."""

from __future__ import annotations

import os
from pathlib import Path


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
