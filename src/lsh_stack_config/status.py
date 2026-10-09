"""Human-readable setup status for an LSH stack project."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import __version__, cli_runtime
from .commands import stack_command
from .composer import compose_stack
from .core_export import installed_lsh_core_tools, load_core_export
from .development import dependency_modes
from .doctor import project_warnings
from .errors import StackConfigError
from .launcher import lsh_stack_command
from .models import StackConfig
from .paths import display_path
from .render import generated_file_problems

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
    "platformio-core-targets.py",
)
_MAX_MISSING_GENERATED_FILES_TO_LIST = 3


@dataclass(frozen=True)
class StackStatus:
    """Read-only setup progress, with full validation when lsh-core is available."""

    config: StackConfig
    output_dir: Path
    core_project: Path
    bridge_project: Path
    platformio: list[str] | None
    core_tool: str
    core_tool_ready: bool
    generated_missing: tuple[Path, ...]
    warnings: tuple[str, ...]
    validation: str = "not verified (run setup)"
    generated_problems: tuple[str, ...] = ()
    local_dependencies: tuple[bool, bool] | None = None
    dependency_problem: str | None = None


def inspect_stack_status(config: StackConfig, output_dir: Path) -> StackStatus:
    """Inspect local setup state without generating files or building firmware."""
    core_project = config.platformio.core_project or config.core.devices.parent
    bridge_project = config.platformio.bridge_project or config.path.parent / "bridge"
    core_tool, core_tool_ready = _core_tool_status(config, core_project)
    expected_generated_files = list(_EXPECTED_GENERATED_FILES)
    if config.platformio.core_prefer_system_tools:
        expected_generated_files.append("platformio-core-system-tools.py")
    if config.deploy.bridge.ota is not None:
        expected_generated_files.extend(
            ("bridge-ota.py", "bridge-ota.json", "platformio-bridge-targets.py")
        )
    generated_missing = tuple(
        output_dir / name for name in expected_generated_files if not (output_dir / name).exists()
    )
    validation = "not verified (run setup)"
    problems: list[str] = []
    modes = None
    dependency_problem = None
    try:
        modes = dependency_modes(config)
    except StackConfigError as exc:
        dependency_problem = str(exc)
    if core_tool_ready:
        try:
            stack = compose_stack(config, load_core_export(config.core))
            validation = "valid"
            problems = generated_file_problems(output_dir, config, stack)
        except StackConfigError as exc:
            validation = f"invalid: {exc}"
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
        validation=validation,
        generated_problems=tuple(problems),
        local_dependencies=modes,
        dependency_problem=dependency_problem,
    )


def render_stack_status(status: StackStatus) -> str:
    """Render a concise setup status report."""
    config = status.config
    lines = [
        "LSH stack status",
        f"- generator: lsh-stack {__version__}",
        f"- generator path: {Path(__file__).parent}",
        f"- launcher: {lsh_stack_command()}",
        f"- stack config: {display_path(config.path)}",
        f"- core config: {_file_status(config.core.devices)}",
        f"- core project: {display_path(status.core_project)}",
        f"- bridge project: {display_path(status.bridge_project)}",
        "- dependencies: "
        + (
            f"core {'local' if status.local_dependencies[0] else 'release'}, "
            f"bridge {'local' if status.local_dependencies[1] else 'release'}"
            if status.local_dependencies is not None
            else f"not verified: {status.dependency_problem}"
        ),
        f"- PlatformIO CLI: {_platformio_status(status.platformio)}",
        f"- lsh-core generator: {status.core_tool}",
        f"- configuration: {status.validation}",
        f"- generated files: {_generated_status(status.generated_missing)} (presence only)",
        "- generated content: "
        + (
            "outdated/incomplete"
            if status.generated_problems
            else "current"
            if status.validation == "valid"
            else "not verified"
        ),
        "- firmware: not verified by status; setup/build verifies compilation, not real devices",
        f"- OTA: {_ota_status(config)}",
    ]
    if status.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in status.warnings)
    lines.extend(f"- {problem}" for problem in status.generated_problems)
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
    if status.local_dependencies is not None and len(set(status.local_dependencies)) > 1:
        return (
            f"complete the dependency switch: choose {stack_command('dev', config, 'local')} "
            f"or {stack_command('dev', config, 'release')}"
        )
    if (
        status.validation.startswith("invalid")
        or not status.core_tool_ready
        or status.generated_missing
    ):
        command = "doctor" if status.validation.startswith("invalid") else "setup"
        return f"run {stack_command(command, config)}"
    if status.dependency_problem or status.warnings:
        return (
            f"resolve dependency overrides: {status.dependency_problem}; "
            f"then run {stack_command('dev', config, 'status')}"
            if status.dependency_problem
            else f"run {stack_command('doctor', config)}"
        )
    if status.generated_problems:
        return f"run {stack_command('generate', config)}"
    return (
        f"run {stack_command('ota', config, '--all', '--dry-run')}"
        if config.deploy.bridge.ota is not None
        else f"build firmware with {stack_command('core', config, 'build', '--all')}"
    )
