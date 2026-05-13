"""Path presentation helpers for CLI output and generated docs."""

from __future__ import annotations

import os
from pathlib import Path


def display_path(path: Path, *, base_dir: Path | None = None) -> str:
    """Return a readable path, relative to ``base_dir`` when possible."""
    root = Path.cwd() if base_dir is None else base_dir
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    return "." if str(relative) == "." else str(relative)


def path_from(base_dir: Path, path: Path) -> str:
    """Return ``path`` relative to ``base_dir`` for shell commands and docs."""
    return os.path.relpath(path, base_dir)
