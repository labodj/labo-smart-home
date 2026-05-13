"""Human-readable setup status for an LSH stack project."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import cli_runtime
from .commands import stack_command
from .core_export import installed_lsh_core_tools
from .doctor import project_warnings
from .models import StackConfig
from .paths import display_path

_EXPECTED_GENERATED_FILES = (
    "lsh-stack-config.json",
    "platformio-core.ini",
    "platformio-bridge.ini",
    "system-config.json",
    "node-red-lsh-logic.json",
    "node-red-setup.md",
    "bridge-platformio-flags/bridge.txt",
    "deploy-plan.json",
    "README.generated.md",
)
_MAX_MISSING_GENERATED_FILES_TO_LIST = 3


@dataclass(frozen=True)
class StackStatus:
    """Setup progress that can be computed without running lsh-core."""

    config: StackConfig
    output_dir: Path
    core_project: Path
    bridge_project: Path
    platformio: list[str] | None
    core_tool: str
    core_tool_ready: bool
    generated_missing: tuple[Path, ...]
    warnings: tuple[str, ...]


def inspect_stack_status(config: StackConfig, output_dir: Path) -> StackStatus:
    """Inspect local setup state without generating files or building firmware."""
    core_project = config.platformio.core_project or config.core.devices.parent
    bridge_project = config.platformio.bridge_project or config.path.parent
    core_tool, core_tool_ready = _core_tool_status(config, core_project)
    generated_missing = tuple(
        output_dir / name for name in _EXPECTED_GENERATED_FILES if not (output_dir / name).exists()
    )
    return StackStatus(
        config=config,
        output_dir=output_dir,
        core_project=core_project,
        bridge_project=bridge_project,
        platformio=cli_runtime.platformio_invocation(),
        core_tool=core_tool,
        core_tool_ready=core_tool_ready,
        generated_missing=generated_missing,
        warnings=tuple(project_warnings(config, output_dir)),
    )


def render_stack_status(status: StackStatus) -> str:
    """Render a concise setup status report."""
    config = status.config
    lines = [
        "LSH stack status",
        f"- stack config: {display_path(config.path)}",
        f"- core config: {_file_status(config.core.devices)}",
        f"- core project: {display_path(status.core_project)}",
        f"- bridge project: {display_path(status.bridge_project)}",
        f"- PlatformIO CLI: {_platformio_status(status.platformio)}",
        f"- lsh-core generator: {status.core_tool}",
        f"- generated files: {_generated_status(status.generated_missing)}",
        f"- OTA: {_ota_status(config)}",
    ]
    if status.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in status.warnings)
    lines.append("next action:")
    lines.append(f"- {_next_action(status)}")
    return "\n".join(lines) + "\n"


def _core_tool_status(config: StackConfig, core_project: Path) -> tuple[str, bool]:
    if config.core.tool is not None:
        return _configured_tool_status(config.core.tool, "configured")

    env_tool = os.environ.get("LSH_CORE_TOOL")
    if env_tool:
        return _configured_tool_status(Path(env_tool).expanduser(), "LSH_CORE_TOOL")

    tools = installed_lsh_core_tools(core_project)
    if tools:
        suffix = f" (+{len(tools) - 1} more)" if len(tools) > 1 else ""
        return f"installed at {display_path(tools[0])}{suffix}", True
    return "not installed yet", False


def _configured_tool_status(path: Path, label: str) -> tuple[str, bool]:
    if path.is_file():
        return f"{label}: {display_path(path)}", True
    return f"{label} missing: {display_path(path)}", False


def _file_status(path: Path) -> str:
    state = "present" if path.is_file() else "missing"
    return f"{display_path(path)} ({state})"


def _platformio_status(platformio: list[str] | None) -> str:
    if platformio is None:
        return "not available in this shell"
    return " ".join(platformio)


def _generated_status(missing: tuple[Path, ...]) -> str:
    if not missing:
        return "key files present"
    if len(missing) > _MAX_MISSING_GENERATED_FILES_TO_LIST:
        return f"incomplete ({len(missing)} missing; first: {display_path(missing[0])})"
    return "missing " + ", ".join(display_path(path) for path in missing)


def _ota_status(config: StackConfig) -> str:
    if config.deploy.bridge.ota is None:
        return "not configured"
    return "configured"


def _next_action(status: StackStatus) -> str:
    config = status.config
    if not config.core.devices.is_file():
        return f"create or point [core].devices at {display_path(config.core.devices)}"
    if not status.core_tool_ready:
        return f"run {stack_command('setup', config)}"
    if status.generated_missing:
        return f"run {stack_command('setup', config)}"
    if status.warnings:
        return f"run {stack_command('doctor', config)}"
    if config.deploy.bridge.ota is not None:
        return f"run {stack_command('ota', config, '--dry-run')}"
    return f"build firmware, or run {stack_command('doctor', config)} after edits"
