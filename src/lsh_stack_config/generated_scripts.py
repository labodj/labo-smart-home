"""Generated helper scripts emitted by lsh-stack."""

from __future__ import annotations


def render_platformio_bridge_batch_script() -> str:
    """Render a tiny PlatformIO extra script that adds IDE-visible stack targets."""
    return """\
\"\"\"Generated PlatformIO targets for LSH bridge environments.\"\"\"

from __future__ import annotations

import shlex
import sys

Import(\"env\")


def _items(option_name: str) -> list[str]:
    raw = env.GetProjectOption(option_name, \"\")
    return [
        item.strip()
        for line in str(raw).splitlines()
        for item in line.split(\",\")
        if item.strip()
    ]


def _option(option_name: str) -> str:
    return str(env.GetProjectOption(option_name, \"\")).strip()


def _slug(value: str) -> str:
    return \"\".join(
        char if char.isalnum() or char == \"_\" else \"_\" for char in value
    ).strip(\"_\")


def _platformio_command(envs: list[str], target: str | None = None) -> str:
    args = [
        env.subst(\"$PYTHONEXE\"),
        \"-m\",
        \"platformio\",
        \"run\",
        \"-d\",
        env.subst(\"$PROJECT_DIR\"),
    ]
    for env_name in envs:
        args.extend([\"-e\", env_name])
    if target is not None:
        args.extend([\"-t\", target])
    return \" \".join(shlex.quote(arg) for arg in args)


def _run_platformio(envs: list[str], target: str | None = None) -> None:
    _execute(_platformio_command(envs, target))


def _execute(command: str) -> None:
    exit_code = env.Execute(command)
    if exit_code:
        sys.exit(exit_code)


def _firmware_path() -> str:
    return env.subst(\"$BUILD_DIR/${PROGNAME}.bin\")


def _format_ota_command(template: str, devices: list[str]) -> str:
    firmware = shlex.quote(_firmware_path())
    quoted_devices = [shlex.quote(device) for device in devices]
    return template.format(
        firmware=firmware,
        device=quoted_devices[0],
        devices=\" \".join(quoted_devices),
        env=env.subst(\"$PIOENV\"),
        profile=_option(\"custom_lsh_stack_profile\"),
    )


def _ota_commands(template: str, devices: list[str]) -> list[str]:
    specific_commands = [
        _option(f\"custom_lsh_stack_ota_command_{_slug(device)}\") for device in devices
    ]
    if any(specific_commands):
        return [
            _format_ota_command(command or template, [device])
            for device, command in zip(devices, specific_commands, strict=True)
        ]
    if \"{devices}\" in template or len(devices) == 1:
        return [_format_ota_command(template, devices)]
    return [_format_ota_command(template, [device]) for device in devices]


def _run_ota(devices: list[str]) -> None:
    template = _option(\"custom_lsh_stack_ota_template\")
    if not template:
        raise RuntimeError(\"custom_lsh_stack_ota_template is required for LSH OTA targets\")
    _run_platformio([env.subst(\"$PIOENV\")])
    for command in _ota_commands(template, devices):
        _execute(command)


build_envs = _items(\"custom_lsh_stack_batch_build_envs\")
ota_devices = _items(\"custom_lsh_stack_ota_devices\")
ota_envs = _items(\"custom_lsh_stack_batch_ota_envs\")

if build_envs:
    env.AddCustomTarget(
        \"lsh_build_all\",
        None,
        lambda *_args, **_kwargs: _run_platformio(build_envs),
        title=\"LSH Build All\",
        description=\"Build all generated LSH bridge environments in this batch.\",
    )

if ota_devices:
    for device_id in ota_devices:
        env.AddCustomTarget(
            f\"lsh_ota_{device_id}\",
            None,
            lambda *_args, device_id=device_id, **_kwargs: _run_ota([device_id]),
            title=f\"LSH OTA {device_id}\",
            description=f\"Build this bridge firmware and OTA-upload it to {device_id}.\",
        )

    env.AddCustomTarget(
        \"lsh_ota_all\",
        None,
        lambda *_args, **_kwargs: _run_ota(ota_devices),
        title=\"LSH OTA All\",
        description=\"Build this bridge firmware and OTA-upload it to all configured devices.\",
    )
elif ota_envs:
    env.AddCustomTarget(
        \"lsh_ota_all\",
        None,
        lambda *_args, **_kwargs: _run_platformio(ota_envs, \"upload\"),
        title=\"LSH OTA All\",
        description=\"Build and OTA-upload all generated LSH bridge environments in this batch.\",
    )
"""


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

import os
import subprocess
import sys
from pathlib import Path


UPDATER_ENV = "LSH_HOMIE_OTA_UPDATER"
UPDATER_RELATIVE_PATHS = (
    Path("scripts") / "homie_ota.py",
    Path("scripts") / "ota_updater" / "ota_updater.py",
)


def _extract_wrapper_args(argv: list[str]) -> tuple[Path | None, list[str]]:
    updater: Path | None = None
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
        else:
            passthrough.append(arg)
    return updater, passthrough


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
        for relative_path in UPDATER_RELATIVE_PATHS:
            candidates.append(root / "homie-esp8266" / relative_path)
            candidates.append(root / relative_path)
        libdeps = root / ".pio" / "libdeps"
        if libdeps.is_dir():
            candidates.extend(sorted(libdeps.glob("*/homie-v5/scripts/homie_ota.py")))
            candidates.extend(sorted(libdeps.glob("*/homie-esp8266/scripts/homie_ota.py")))
            candidates.extend(sorted(libdeps.glob("*/homie-v5/scripts/ota_updater/ota_updater.py")))
            candidates.extend(sorted(libdeps.glob("*/homie-esp8266/scripts/ota_updater/ota_updater.py")))
    return _unique(candidates)


def _find_updater(explicit: Path | None) -> Path:
    candidates = [explicit] if explicit is not None else _candidate_updaters()
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    searched = "\\n".join(f"- {candidate}" for candidate in candidates if candidate is not None)
    print(
        "Could not find the homie-esp8266 OTA updater.\\n"
        f"Set {UPDATER_ENV}=/path/to/homie-esp8266/scripts/homie_ota.py "
        "or pass --updater /path/to/homie_ota.py.\\n"
        "Searched:\\n"
        f"{searched}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    explicit, passthrough = _extract_wrapper_args(sys.argv[1:] if argv is None else argv)
    updater = _find_updater(explicit)
    return subprocess.run(
        [sys.executable, str(updater), *passthrough],
        check=False,
    ).returncode


raise SystemExit(main())
"""
