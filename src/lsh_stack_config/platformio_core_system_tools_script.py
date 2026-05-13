"""Renderer for the optional core PlatformIO system-toolchain helper."""

from __future__ import annotations


def render_platformio_core_system_tools_script() -> str:
    """Render a small cross-platform PATH-prepend PlatformIO script."""
    return """\
\"\"\"Generated helper that lets core builds prefer system compiler tools.

Set LSH_PLATFORMIO_SYSTEM_TOOL_DIRS to an os.pathsep-separated directory list when
your system toolchain is not in one of the default Unix paths.
\"\"\"

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

Import(\"env\")

TOOL_DIRS_ENV = \"LSH_PLATFORMIO_SYSTEM_TOOL_DIRS\"


def _configured_dirs() -> list[Path]:
    raw = os.environ.get(TOOL_DIRS_ENV)
    if raw:
        return [Path(item).expanduser() for item in raw.split(os.pathsep) if item]
    if sys.platform == \"darwin\":
        return [Path(\"/opt/homebrew/bin\"), Path(\"/usr/local/bin\"), Path(\"/usr/bin\")]
    if os.name == \"posix\":
        return [Path(\"/usr/local/bin\"), Path(\"/usr/bin\"), Path(\"/bin\")]
    return []


def _existing_dirs(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if path.is_dir()]


preferred_dirs = _existing_dirs(_configured_dirs())
if preferred_dirs:
    env.PrependENVPath(\"PATH\", preferred_dirs)
    probe_path = os.pathsep.join(preferred_dirs)
    compiler = shutil.which(\"avr-g++\", path=probe_path) or shutil.which(
        \"avr-gcc\", path=probe_path
    )
    detail = f\" ({compiler})\" if compiler else \"\"
    joined_dirs = os.pathsep.join(preferred_dirs)
    print(f\"lsh-stack: preferring system tool directories: {joined_dirs}{detail}\")
else:
    print(
        f\"lsh-stack: {TOOL_DIRS_ENV} is not set and no default system tool directories exist "
        "on this platform.\"
    )
"""
