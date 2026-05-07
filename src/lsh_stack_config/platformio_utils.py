"""Small PlatformIO parsing and path helpers shared by renderers and doctor."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

PLATFORMIO_CONFIG_ERRORS = (configparser.Error, OSError, UnicodeDecodeError)


def load_platformio_config(path: Path) -> configparser.ConfigParser:
    """Parse one PlatformIO INI file without interpolation."""
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    with path.open(encoding="utf-8") as handle:
        parser.read_file(handle)
    return parser


def read_platformio_config(project_dir: Path | None) -> configparser.ConfigParser | None:
    """Best-effort PlatformIO config read for optional introspection."""
    if project_dir is None:
        return None
    try:
        return load_platformio_config(project_dir / "platformio.ini")
    except PLATFORMIO_CONFIG_ERRORS:
        return None


def inherited_option_values(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
) -> list[str]:
    """Return option values from a section or its PlatformIO `extends` chain."""
    return _inherited_option_values(parser, section, option, visited=set())


def option_values(raw: str) -> list[str]:
    """Parse a multiline PlatformIO option into trimmed entries."""
    return [line.strip() for line in raw.splitlines() if line.strip()]


def section_refs(raw: str) -> list[str]:
    """Parse PlatformIO `extends` references from comma or newline lists."""
    return [item.strip() for line in raw.splitlines() for item in line.split(",") if item.strip()]


def script_entry_present(script_entry: str, entries: list[str]) -> bool:
    """Compare PlatformIO script entries while ignoring `pre:` and `post:` prefixes."""
    return script_path(script_entry) in {script_path(entry) for entry in entries}


def script_path(entry: str) -> str:
    """Return the path part of a PlatformIO extra script entry."""
    normalized = entry.strip()
    for prefix in ("pre:", "post:"):
        if normalized.startswith(prefix):
            return normalized.removeprefix(prefix)
    return normalized


def path_for_platformio(path: Path, project_dir: Path | None) -> str:
    """Return a path as it should be written inside a PlatformIO project."""
    if project_dir is None:
        return str(path)
    return os.path.relpath(path, project_dir)


def project_command_path(path: Path | None) -> str:
    """Return a PlatformIO project path suitable for generated CLI commands."""
    return str(path) if path is not None else "<platformio-project>"


def extra_configs_include(project: Path, fragment: Path, extra_configs: list[str]) -> bool:
    """Check whether `[platformio].extra_configs` already references a generated file."""
    expected = fragment.resolve()
    expected_text = path_for_platformio(fragment, project)
    for raw_entry in extra_configs:
        entry = raw_entry.strip()
        if not entry:
            continue
        if entry == expected_text:
            return True
        candidate = Path(entry)
        if not candidate.is_absolute():
            candidate = project / candidate
        if candidate.resolve() == expected:
            return True
    return False


def _inherited_option_values(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    *,
    visited: set[str],
) -> list[str]:
    if section in visited:
        return []
    visited.add(section)

    if not parser.has_section(section):
        return []
    if parser.has_option(section, option):
        return option_values(parser.get(section, option, fallback=""))

    values: list[str] = []
    for parent in section_refs(parser.get(section, "extends", fallback="")):
        values.extend(_inherited_option_values(parser, parent, option, visited=visited))
    return values
