"""Adapter that asks ``lsh-core`` for its controller-derived stack contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .errors import StackConfigError
from .models import CoreSettings, JsonObject

_TOOL_RELATIVE_PATH = Path("tools/generate_lsh_static_config.py")


def load_core_export(core: CoreSettings, *, override_tool: Path | None = None) -> JsonObject:
    """Run the lsh-core generator and return its machine-readable export."""
    tool = _resolve_core_tool(core, override_tool=override_tool)
    args = [
        sys.executable,
        str(tool),
        str(core.devices),
        "--print-stack-config",
    ]
    for device in core.selected_devices:
        args.extend(("--device", device))

    try:
        completed = subprocess.run(  # noqa: S603 - the explicit tool path is validated first.
            args,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise StackConfigError(f"cannot run lsh-core generator at {tool}: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise StackConfigError(f"lsh-core generator failed: {detail}")

    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise StackConfigError(f"lsh-core generator did not return valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise StackConfigError("lsh-core generator returned a non-object JSON value.")
    return parsed


def _resolve_core_tool(core: CoreSettings, *, override_tool: Path | None) -> Path:
    if override_tool is not None:
        return _existing_tool(override_tool)
    if core.tool is not None:
        return _existing_tool(core.tool)

    env_tool = os.environ.get("LSH_CORE_TOOL")
    if env_tool:
        return _existing_tool(Path(env_tool).expanduser())

    # The common public and personal setup keeps lsh-core next to the project
    # that owns lsh_stack.toml.  Try a small, deterministic set of locations
    # before asking the user for an explicit path.
    candidates = (
        core.devices.parent.parent / "lsh-core" / _TOOL_RELATIVE_PATH,
        Path.cwd() / "lsh-core" / _TOOL_RELATIVE_PATH,
        Path.cwd().parent / "lsh-core" / _TOOL_RELATIVE_PATH,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise StackConfigError(
        "cannot find lsh-core generator. Set core.tool in lsh_stack.toml or LSH_CORE_TOOL."
    )


def _existing_tool(path: Path) -> Path:
    candidate = path.resolve()
    if not candidate.is_file():
        raise StackConfigError(f"lsh-core generator not found: {candidate}")
    return candidate
