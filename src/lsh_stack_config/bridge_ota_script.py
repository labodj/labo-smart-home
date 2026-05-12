"""Renderer for the generated bridge OTA wrapper script."""

from __future__ import annotations


def render_bridge_ota_script() -> str:
    """Render the generated wrapper around the upstream Homie OTA updater."""
    return """\
#!/usr/bin/env python3
\"\"\"Generated LSH bridge OTA wrapper. Do not edit by hand.

This wrapper only locates the Homie OTA updater and forwards arguments to it.
OTA settings are not discovered here; generated commands pass them explicitly,
usually with ``--config generated/bridge-ota.json``.
\"\"\"

from __future__ import annotations

import getpass
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


UPDATER_ENV = "LSH_HOMIE_OTA_UPDATER"
UPDATER_RELATIVE_PATH = Path("scripts") / "homie_ota.py"


def _extract_wrapper_args(argv: list[str]) -> tuple[Path | None, Path | None, list[str]]:
    updater: Path | None = None
    config: Path | None = None
    passthrough: list[str] = []
    iterator = iter(argv)
    for arg in iterator:
        if arg == "--updater":
            try:
                updater = Path(next(iterator))
            except StopIteration:
                print("--updater requires a path", file=sys.stderr)
                raise SystemExit(2)
        elif arg.startswith("--updater="):
            updater = Path(arg.split("=", 1)[1])
        elif arg == "--config":
            try:
                raw_config = next(iterator)
            except StopIteration:
                print("--config requires a path", file=sys.stderr)
                raise SystemExit(2)
            config = Path(raw_config)
            passthrough.extend([arg, raw_config])
        elif arg.startswith("--config="):
            config = Path(arg.split("=", 1)[1])
            passthrough.append(arg)
        else:
            passthrough.append(arg)
    return updater, config, passthrough


def _option_value(argv: list[str], names: tuple[str, ...]) -> str | None:
    for index, arg in enumerate(argv):
        if arg in names and index + 1 < len(argv):
            return argv[index + 1]
        for name in names:
            prefix = f"{name}="
            if arg.startswith(prefix):
                return arg[len(prefix):]
    return None


def _option_present(argv: list[str], names: tuple[str, ...]) -> bool:
    return _option_value(argv, names) is not None


def _config_password_env(config: Path | None) -> str | None:
    if config is None or config.suffix.lower() != ".json":
        return None
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    broker = data.get("broker") if isinstance(data, dict) else None
    if not isinstance(broker, dict):
        return None
    password_env = broker.get("password_env")
    return password_env if isinstance(password_env, str) and password_env else None


def _prompt_for_password_env(config: Path | None, passthrough: list[str]) -> None:
    if _help_requested(passthrough):
        return
    if _option_present(passthrough, ("--broker-password", "-d")):
        return
    password_env = _option_value(passthrough, ("--broker-password-env",))
    if password_env is None:
        password_env = _config_password_env(config)
    if password_env is None or password_env in os.environ:
        return
    if not sys.stdin.isatty():
        print(
            f"{password_env} is not set and this terminal cannot prompt for it. "
            "Run from an interactive terminal, pass --broker-password, "
            f"or provide {password_env} in the process environment for automation.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    os.environ[password_env] = getpass.getpass(f"MQTT/OTA password ({password_env}): ")


def _unique(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)
    return unique_paths


def _candidate_roots() -> list[Path]:
    script_dir = Path(__file__).resolve().parent
    roots = [Path.cwd(), script_dir]
    roots.extend(script_dir.parents)
    roots.extend(Path.cwd().resolve().parents)
    return _unique(roots)


def _candidate_updaters() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get(UPDATER_ENV)
    if env_path:
        candidates.append(Path(env_path))
    # Search order is deterministic and reported in the error message. The wrapper
    # checks the local checkout first, then normal PlatformIO libdeps package names.
    for root in _candidate_roots():
        candidates.append(root / "homie-esp8266" / UPDATER_RELATIVE_PATH)
        candidates.append(root / UPDATER_RELATIVE_PATH)
        for libdeps in (root / ".pio" / "libdeps", root / "bridge" / ".pio" / "libdeps"):
            if libdeps.is_dir():
                candidates.extend(sorted(libdeps.glob("*/homie-v5/scripts/homie_ota.py")))
                candidates.extend(sorted(libdeps.glob("*/homie-esp8266/scripts/homie_ota.py")))
    return _unique(candidates)


def _help_requested(passthrough: list[str]) -> bool:
    return "-h" in passthrough or "--help" in passthrough


def _find_updater_or_none(explicit: Path | None) -> Path | None:
    candidates = [explicit] if explicit is not None else _candidate_updaters()
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    return None


def _find_updater(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit is not None else _candidate_updaters()
    updater = _find_updater_or_none(explicit)
    if updater is not None:
        return updater
    searched = "\\n".join(f"- {candidate}" for candidate in candidates if candidate is not None)
    print(
        "Could not find the homie-esp8266 OTA updater.\\n"
        "Pass --updater /path/to/homie_ota.py. For automation, you may also "
        f"provide {UPDATER_ENV} in the process environment.\\n"
        "Searched:\\n"
        f"{searched}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _print_wrapper_help() -> None:
    print(
        "usage: bridge-ota.py [--updater PATH] --config bridge-ota.json "
        "--device-id DEVICE firmware\\n\\n"
        "Generated LSH bridge OTA wrapper.\\n\\n"
        "Normal use:\\n"
        "  lsh-stack ota [device...]\\n\\n"
        "The upstream Homie OTA updater is loaded from the bridge project's "
        "PlatformIO libdeps after the bridge project has been built once. "
        f"You can also pass --updater PATH or set {UPDATER_ENV}."
    )


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _check_python_ota_dependencies(passthrough: list[str]) -> None:
    if _help_requested(passthrough):
        return
    if _module_available("paho.mqtt"):
        return
    requirement = "paho-mqtt>=1.6,<3"
    print(
        "Missing Python dependency `paho-mqtt` for the Homie OTA updater. "
        f"Install it with `{sys.executable} -m pip install '{requirement}'`.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    explicit, config, passthrough = _extract_wrapper_args(sys.argv[1:] if argv is None else argv)
    if _help_requested(passthrough):
        updater = _find_updater_or_none(explicit)
        if updater is None:
            _print_wrapper_help()
            return 0
        return subprocess.run(
            [sys.executable, str(updater), *passthrough],
            check=False,
        ).returncode
    _prompt_for_password_env(config, passthrough)
    updater = _find_updater(explicit)
    _check_python_ota_dependencies(passthrough)
    return subprocess.run(
        [sys.executable, str(updater), *passthrough],
        check=False,
    ).returncode


raise SystemExit(main())
"""
