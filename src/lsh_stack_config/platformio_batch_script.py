"""Renderer for the generated PlatformIO bridge helper script."""

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


def _format_ota_command(template: str, device: str) -> str:
    firmware = shlex.quote(_firmware_path())
    return template.format(
        firmware=firmware,
        device=shlex.quote(device),
        env=env.subst(\"$PIOENV\"),
        profile=_option(\"custom_lsh_stack_profile\"),
        python=shlex.quote(env.subst(\"$PYTHONEXE\")),
    )


def _run_ota(devices: list[str]) -> None:
    template = _option(\"custom_lsh_stack_ota_template\")
    if not template:
        raise RuntimeError(\"custom_lsh_stack_ota_template is required for LSH OTA targets\")
    _run_platformio([env.subst(\"$PIOENV\")])
    for device in devices:
        _execute(_format_ota_command(template, device))


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
