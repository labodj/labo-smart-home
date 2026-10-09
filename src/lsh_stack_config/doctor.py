"""Project diagnostics for generated LSH stack files."""

from __future__ import annotations

from pathlib import Path

from .launcher import lsh_stack_command
from .models import StackConfig
from .paths import display_path
from .platformio_utils import (
    PLATFORMIO_CONFIG_ERRORS,
    extra_configs_include,
    load_platformio_config,
    option_values,
    path_for_platformio,
)
from .scaffold_templates import TEMPLATE_VERSION


def doctor_fix(message: str) -> str:
    """Return a short remediation hint for a known validation error."""
    if "cannot find lsh-core generator" in message:
        return f"run `{lsh_stack_command()} setup` to install the generator and build your devices."
    if "not declared as network=true" in message:
        return "edit lsh_devices.toml and mark that long or super-long click as network=true."
    if "unknown actuator" in message or "unknown LSH actor device" in message:
        return "check the device and actuator names against lsh_devices.toml."
    if "contains unknown keys" in message:
        return "check the spelling of the reported TOML keys against the configuration reference."
    if "must end with '/'" in message or "must not end with '/'" in message:
        return "check MQTT base paths versus concrete publish topics."
    return "run the check command after editing the source TOML files."


def project_warnings(config: StackConfig, output_dir: Path) -> list[str]:
    """Return non-fatal warnings about missing generated files and stale includes."""
    warnings: list[str] = []
    project_dir = config.path.parent
    generated_dir = output_dir if output_dir.is_absolute() else project_dir / output_dir

    if not (generated_dir / "platformio-core.ini").exists():
        missing = generated_dir / "platformio-core.ini"
        warnings.append(f"run generate before opening PlatformIO: missing {display_path(missing)}.")
    if not (generated_dir / "platformio-bridge.ini").exists():
        missing = generated_dir / "platformio-bridge.ini"
        warnings.append(f"run generate before opening PlatformIO: missing {display_path(missing)}.")
    if (
        config.platformio.core_prefer_system_tools
        and not (generated_dir / "platformio-core-system-tools.py").exists()
    ):
        missing = generated_dir / "platformio-core-system-tools.py"
        warnings.append(f"run generate before core builds: missing {display_path(missing)}.")

    warnings.extend(
        _platformio_fragment_warnings(
            label="core",
            project=config.platformio.core_project or config.core.devices.parent,
            fragment=generated_dir / "platformio-core.ini",
            expected_template_kind="core-controllino-maxi",
        )
    )
    warnings.extend(
        _platformio_fragment_warnings(
            label="bridge",
            project=config.platformio.bridge_project or project_dir / "bridge",
            fragment=generated_dir / "platformio-bridge.ini",
            expected_template_kind="bridge-esp32-homie",
        )
    )
    return warnings


def _platformio_fragment_warnings(
    *,
    label: str,
    project: Path,
    fragment: Path,
    expected_template_kind: str,
) -> list[str]:
    platformio_ini = project / "platformio.ini"
    if not platformio_ini.exists():
        return [f"{label} PlatformIO project is missing {display_path(platformio_ini)}."]

    try:
        parser = load_platformio_config(platformio_ini)
    except PLATFORMIO_CONFIG_ERRORS as exc:
        return [f"{label} PlatformIO project has an unreadable platformio.ini: {exc}."]

    warnings: list[str] = []
    extra_configs = option_values(parser.get("platformio", "extra_configs", fallback=""))
    if not extra_configs_include(project, fragment, extra_configs):
        expected = path_for_platformio(fragment, project)
        warnings.append(
            f"{label} platformio.ini should include `{expected}` in [platformio].extra_configs."
        )

    if parser.has_section("lsh_stack_template"):
        kind = parser.get("lsh_stack_template", "kind", fallback="")
        try:
            version = parser.getint("lsh_stack_template", "version", fallback=0)
        except ValueError:
            return [f"{label} template version must be an integer; run templates diff."]
        if kind != expected_template_kind:
            message = f"{label} platformio.ini template kind is `{kind}`"
            warnings.append(f"{message}, expected `{expected_template_kind}`.")
        if version < TEMPLATE_VERSION:
            message = f"{label} platformio.ini template version is {version}"
            warnings.append(f"{message}; current is {TEMPLATE_VERSION}.")
    return warnings
