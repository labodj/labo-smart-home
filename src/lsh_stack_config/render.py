"""Render stack composer outputs for humans and files."""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .bridge_ota_script import render_bridge_ota_script
from .commands import stack_command
from .deploy import (
    BridgeOtaArtifacts,
    StackBuildPlan,
    bridge_ota_command,
    bridge_ota_template,
    bridge_usb_port,
    pio_command,
    render_bridge_ota_config,
    render_deploy_plan,
    stack_build_plan,
    uses_generated_bridge_ota_script,
)
from .models import BridgeProfileSettings, JsonObject, StackConfig
from .paths import display_path, path_from
from .platformio_bridge_targets_script import render_platformio_bridge_targets_script
from .platformio_core_system_tools_script import render_platformio_core_system_tools_script
from .platformio_utils import (
    inherited_option_values,
    path_for_platformio,
    project_command_path,
    read_platformio_config,
    script_entry_present,
)
from .render_common import (
    bridge_build_env,
    bridge_devices,
    bridge_flag_section,
    bridge_profiles,
    bridge_usb_upload_env,
    core_build_env,
    core_profiles,
    default_bridge_profile,
    device_names,
    json_list,
    json_object,
    profile_key,
)


def stack_json(stack: JsonObject) -> str:
    """Return stable JSON for generated stack artifacts."""
    return json.dumps(stack, indent=2, sort_keys=True) + "\n"


def render_report(config: StackConfig, stack: JsonObject) -> str:
    """Render a concise bring-up report for the generated stack config."""
    coordinator = json_object(stack["coordinator"])
    system_config = json_object(coordinator["systemConfig"])
    devices = json_list(system_config["devices"])
    bridge = json_object(stack["bridge"])
    bridge_devices = json_object(bridge["devices"])
    bridge_flags = json_list(bridge["platformioBuildFlags"])
    profiles = bridge_profiles(config)
    profile_word = "profile" if len(profiles) == 1 else "profiles"
    mapped_clicks = json_list(stack.get("mappedNetworkClicks", []))
    unmapped_clicks = json_list(coordinator.get("unmappedNetworkClicks", []))

    lines = [
        "LSH stack composer",
        f"- stack config: {display_path(config.path)}",
        f"- core config: {display_path(config.core.devices)}",
        f"- transport: {json_object(stack['transport'])['mode']}",
        f"- MQTT protocol: {stack['protocol']}",
        f"- devices: {len(devices)}",
        f"- mapped network clicks: {len(mapped_clicks)}",
        f"- core network-click declarations: {len(unmapped_clicks)}",
        f"- bridge firmware: wide firmware, {len(profiles)} {profile_word} "
        f"({len(bridge_flags)} build flags)",
        "- bridge upload targets:",
    ]
    lines.extend(f"  - {device_key}" for device_key in bridge_devices)

    return "\n".join(lines) + "\n"


def write_output_tree(output_dir: Path, config: StackConfig, stack: JsonObject) -> list[Path]:
    """Write the generated files consumed by bridge, coordinator and Node-RED."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    stack_path = output_dir / "lsh-stack-config.json"
    stack_path.write_text(stack_json(stack), encoding="utf-8")
    written.append(stack_path)

    coordinator = json_object(stack["coordinator"])
    system_config_path = output_dir / "system-config.json"
    system_config_path.write_text(
        stack_json(json_object(coordinator["systemConfig"])), encoding="utf-8"
    )
    written.append(system_config_path)

    node_red = json_object(json_object(stack["nodeRed"])["lshLogic"])
    node_red_path = output_dir / "node-red-lsh-logic.json"
    node_red_path.write_text(stack_json(node_red), encoding="utf-8")
    written.append(node_red_path)

    node_red_guide_path = output_dir / "node-red-setup.md"
    node_red_guide_path.write_text(render_node_red_setup_guide(stack), encoding="utf-8")
    written.append(node_red_guide_path)

    bridge_dir = output_dir / "bridge-platformio-flags"
    bridge_dir.mkdir(exist_ok=True)
    for stale_flag_file in bridge_dir.glob("*.txt"):
        stale_flag_file.unlink()
    bridge_flags = json_list(json_object(stack["bridge"])["platformioBuildFlags"])
    flag_path = bridge_dir / "bridge.txt"
    flag_path.write_text("\n".join(str(flag) for flag in bridge_flags) + "\n", encoding="utf-8")
    written.append(flag_path)

    core_system_tools_script_path = _write_core_system_tools_script(output_dir, config, written)

    core_ini_path = output_dir / "platformio-core.ini"
    core_ini_path.write_text(
        render_platformio_core_ini(
            config,
            stack,
            core_ini_path,
            core_system_tools_script_path,
        ),
        encoding="utf-8",
    )
    written.append(core_ini_path)

    bridge_ota = _write_bridge_ota_artifacts(output_dir, config, written)
    bridge_targets_script_path = _write_bridge_targets_script(output_dir, config, written)

    bridge_ini_path = output_dir / "platformio-bridge.ini"
    bridge_ini_path.write_text(
        render_platformio_bridge_ini(
            config,
            stack,
            bridge_ini_path,
            bridge_targets_script_path,
            bridge_ota,
        ),
        encoding="utf-8",
    )
    written.append(bridge_ini_path)

    deploy_plan_path = output_dir / "deploy-plan.json"
    deploy_plan_path.write_text(
        stack_json(
            render_deploy_plan(
                config,
                stack,
                bridge_ota,
            )
        ),
        encoding="utf-8",
    )
    written.append(deploy_plan_path)

    guide_path = output_dir / "README.generated.md"
    guide_path.write_text(render_generated_readme(config, stack, output_dir), encoding="utf-8")
    written.append(guide_path)

    return written


def _write_bridge_targets_script(
    output_dir: Path,
    config: StackConfig,
    written: list[Path],
) -> Path | None:
    targets_path = output_dir / "platformio-bridge-targets.py"
    stale_batch_path = output_dir / "platformio-bridge-batch.py"
    if uses_generated_bridge_ota_script(config):
        targets_path.write_text(render_platformio_bridge_targets_script(), encoding="utf-8")
        written.append(targets_path)
        if stale_batch_path.exists():
            stale_batch_path.unlink()
        return targets_path

    for path in (targets_path, stale_batch_path):
        if path.exists():
            path.unlink()
    return None


def _write_core_system_tools_script(
    output_dir: Path,
    config: StackConfig,
    written: list[Path],
) -> Path | None:
    script_path = output_dir / "platformio-core-system-tools.py"
    if config.platformio.core_prefer_system_tools:
        script_path.write_text(render_platformio_core_system_tools_script(), encoding="utf-8")
        written.append(script_path)
        return script_path
    if script_path.exists():
        script_path.unlink()
    return None


def _write_bridge_ota_artifacts(
    output_dir: Path,
    config: StackConfig,
    written: list[Path],
) -> BridgeOtaArtifacts:
    script_path = output_dir / "bridge-ota.py"
    config_path = output_dir / "bridge-ota.json"
    if uses_generated_bridge_ota_script(config):
        script_path.write_text(render_bridge_ota_script(), encoding="utf-8")
        written.append(script_path)
        config_path.write_text(stack_json(render_bridge_ota_config(config)), encoding="utf-8")
        written.append(config_path)
        return BridgeOtaArtifacts(script=script_path, config=config_path)

    if script_path.exists():
        script_path.unlink()
    if config_path.exists():
        config_path.unlink()
    return BridgeOtaArtifacts()


def render_platformio_core_ini(
    config: StackConfig,
    stack: JsonObject,
    ini_path: Path,
    system_tools_script_path: Path | None = None,
) -> str:
    """Render PlatformIO environments for controller firmware builds."""
    devices = device_names(stack)
    profiles = core_profiles(config)
    core_project = config.platformio.core_project
    config_path = path_for_platformio(config.core.devices, core_project)
    ini_ref = path_for_platformio(ini_path, core_project)
    lines = [
        "; Generated by lsh-stack. Do not edit by hand.",
        "; Include this file from the controller PlatformIO project:",
        "; [platformio]",
        f"; extra_configs = {ini_ref}",
        "",
        "[lsh_stack_core]",
        f"custom_lsh_config = {config_path}",
        "",
    ]

    for device in devices:
        for profile in profiles:
            env_name = core_build_env(config, device, profile)
            script_entries = _core_extra_script_entries(
                config,
                env_name,
                system_tools_script_path,
            )
            extra_scripts = _core_extra_script_lines(config, profile.base_env, script_entries)
            lines.extend(
                [
                    f"[env:{env_name}]",
                    f"extends = {profile.base_env}",
                    *extra_scripts,
                    "custom_lsh_config = ${lsh_stack_core.custom_lsh_config}",
                    f"custom_lsh_device = {device}",
                    "",
                ]
            )

    return "\n".join(lines)


def render_platformio_bridge_ini(
    config: StackConfig,
    stack: JsonObject,
    ini_path: Path,
    target_script_path: Path | None,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> str:
    """Render one wide bridge firmware per profile plus OTA targets per device."""
    bridge_device_names = list(bridge_devices(stack))
    profiles = bridge_profiles(config)
    default_profile = default_bridge_profile(profiles)
    target_script = (
        path_for_platformio(target_script_path, config.platformio.bridge_project)
        if target_script_path is not None
        else None
    )
    ini_ref = path_for_platformio(ini_path, config.platformio.bridge_project)
    default_build_env = bridge_build_env(config, default_profile)
    flags = [str(flag) for flag in json_list(json_object(stack["bridge"])["platformioBuildFlags"])]
    flag_section = bridge_flag_section("wide")
    lines = [
        "; Generated by lsh-stack. Do not edit by hand.",
        "; Include this file from the bridge PlatformIO project:",
        "; [platformio]",
        f"; extra_configs = {ini_ref}",
        "",
        "[platformio]",
        f"default_envs = {default_build_env}",
        "",
        f"[{flag_section}]",
        "build_flags =",
        *[f"    {flag}" for flag in flags],
        "",
    ]

    for profile in profiles:
        lines.extend(
            _render_bridge_profile_env(
                config=config,
                devices=bridge_device_names,
                flag_section=flag_section,
                profile=profile,
                target_script=target_script,
                bridge_ota=bridge_ota,
            )
        )

    lines.extend(_render_bridge_usb_upload_envs(config, bridge_device_names, profiles))
    return "\n".join(lines)


def render_node_red_setup_guide(stack: JsonObject) -> str:
    """Render GUI-oriented Node-RED setup steps from the stable node config."""
    node_red_config = json_object(json_object(stack["nodeRed"])["lshLogic"])

    lines = [
        "# Node-RED LSH Logic Setup",
        "",
        "This file is generated from `lsh_stack.toml`. Regenerate it after changing the",
        "stack TOML, then copy these values into the Node-RED editor.",
        "",
        "## Steps",
        "",
        "1. Install `node-red-contrib-lsh-logic` from the Node-RED palette.",
        "2. Restart Node-RED if the editor asks for it.",
        "3. Add one `lsh-logic` node to a flow.",
        "4. Add standard MQTT input and output nodes and wire them like the",
        "   `node-red-contrib-lsh-logic` example flow.",
        "5. Open the `lsh-logic` node and set the fields below.",
        "6. Configure the MQTT broker node manually for your broker host, credentials and TLS.",
        "7. Deploy the flow.",
        "",
        "## lsh-logic Fields",
        "",
        "| GUI field | Raw field | Value |",
        "| --- | --- | --- |",
        *_node_red_setting_rows(node_red_config),
        "",
        "## System Config JSON",
        "",
        "Paste this into the `System Config JSON` field:",
        "",
        "```json",
        _node_red_system_config_json(node_red_config),
        "```",
        "",
        "## Wiring Reference",
        "",
        "- MQTT input goes into `lsh-logic`.",
        "- `lsh-logic` command output goes to MQTT output.",
        "- `lsh-logic` configuration output updates the dynamic MQTT input subscription.",
        "- Other outputs can go to debug nodes or to your Home Assistant, Zigbee, Tasmota",
        "  or custom integration flow.",
        "",
        "Use `node-red-lsh-logic.json` next to this file as the raw machine-readable",
        "source of truth for scripts or for checking every generated value.",
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class _GeneratedReadmeContext:
    config: StackConfig
    stack: JsonObject
    output_dir: Path
    stack_root: Path
    plan: StackBuildPlan
    core_project: str
    bridge_project: str
    core_extra_config: str
    bridge_extra_config: str
    bridge_profile_names: str
    bridge_ota: BridgeOtaArtifacts
    sample_ota_device: str
    default_ota_command: str | None
    stack_cli_ota_available: bool


def render_generated_readme(config: StackConfig, stack: JsonObject, output_dir: Path) -> str:
    """Render a friendly guide beside generated deployment artifacts."""
    ctx = _generated_readme_context(config, stack, output_dir)
    lines: list[str] = []
    for section in (
        _readme_intro_section,
        _readme_platformio_include_section,
        _readme_platformio_cli_section,
        _readme_bridge_ota_section,
        _readme_platformio_ide_section,
        _readme_runtime_section,
        _readme_generated_outputs_section,
        _readme_overrides_section,
    ):
        lines.extend(section(ctx))
    return "\n".join(lines) + "\n"


def _generated_readme_context(
    config: StackConfig,
    stack: JsonObject,
    output_dir: Path,
) -> _GeneratedReadmeContext:
    stack_root = config.path.parent
    plan = stack_build_plan(config, stack)
    core_extra_config = path_for_platformio(
        output_dir / "platformio-core.ini", config.platformio.core_project
    )
    bridge_extra_config = path_for_platformio(
        output_dir / "platformio-bridge.ini",
        config.platformio.bridge_project,
    )
    bridge_ota_script_path = (
        output_dir / "bridge-ota.py" if uses_generated_bridge_ota_script(config) else None
    )
    bridge_ota_config_path = (
        output_dir / "bridge-ota.json" if uses_generated_bridge_ota_script(config) else None
    )
    bridge_ota = BridgeOtaArtifacts(script=bridge_ota_script_path, config=bridge_ota_config_path)
    sample_ota_device = plan.bridge_devices[0] if plan.bridge_devices else ""
    return _GeneratedReadmeContext(
        config=config,
        stack=stack,
        output_dir=output_dir,
        stack_root=stack_root,
        plan=plan,
        core_project=_project_command_path(config.platformio.core_project, stack_root),
        bridge_project=_project_command_path(config.platformio.bridge_project, stack_root),
        core_extra_config=core_extra_config,
        bridge_extra_config=bridge_extra_config,
        bridge_profile_names=", ".join(profile_key(profile) for profile in plan.bridge_profiles),
        bridge_ota=bridge_ota,
        sample_ota_device=sample_ota_device,
        default_ota_command=bridge_ota_command(
            config,
            sample_ota_device,
            f".pio/build/{plan.default_bridge_env}/firmware.bin",
            bridge_ota,
        ),
        stack_cli_ota_available=uses_generated_bridge_ota_script(config),
    )


def _readme_intro_section(ctx: _GeneratedReadmeContext) -> list[str]:
    return [
        "# Generated LSH Stack Files",
        "",
        "These files are generated from `lsh_stack.toml`. Edit the TOML files, then regenerate.",
        "Commands below are intended to be run from the stack project root.",
        "",
        "## Regenerate",
        "",
        "After editing `lsh_stack.toml` or `core/lsh_devices.toml`:",
        "",
        "```bash",
        stack_command("generate", ctx.config, config_base_dir=ctx.stack_root),
        stack_command("doctor", ctx.config, config_base_dir=ctx.stack_root),
        stack_command("status", ctx.config, config_base_dir=ctx.stack_root),
        "```",
        "",
    ]


def _readme_platformio_include_section(ctx: _GeneratedReadmeContext) -> list[str]:
    return [
        "## PlatformIO Includes",
        "",
        "Controller project:",
        "",
        "```ini",
        "[platformio]",
        f"extra_configs = {ctx.core_extra_config}",
        "```",
        "",
        "Bridge project:",
        "",
        "```ini",
        "[platformio]",
        f"extra_configs = {ctx.bridge_extra_config}",
        "```",
        "",
    ]


def _readme_platformio_cli_section(ctx: _GeneratedReadmeContext) -> list[str]:
    lines = [
        "## PlatformIO CLI",
        "",
        "If `platformio` is available in your shell, these commands are the direct CLI "
        "equivalent of the generated IDE tasks.",
        "",
        "Build one controller firmware:",
        "",
        "```bash",
        " ".join(pio_command(ctx.core_project, [ctx.plan.default_core_env], target=None)),
        "```",
        "",
        "Build every controller firmware profile:",
        "",
        "```bash",
        " ".join(pio_command(ctx.core_project, list(ctx.plan.all_core_envs), target=None)),
        "```",
        "",
        "Build the default wide bridge firmware:",
        "",
        "```bash",
        " ".join(pio_command(ctx.bridge_project, [ctx.plan.default_bridge_env], target=None)),
        "```",
        "",
    ]
    if len(ctx.plan.bridge_profiles) > 1:
        lines.extend(
            [
                "Build every bridge firmware profile:",
                "",
                "```bash",
                " ".join(pio_command(ctx.bridge_project, list(ctx.plan.all_bridge_envs), None)),
                "```",
                "",
            ]
        )
    if ctx.plan.usb_devices:
        lines.extend(
            [
                "USB-upload configured bridge ports with the default profile firmware:",
                "",
                "```bash",
                *[
                    " ".join(
                        pio_command(
                            ctx.bridge_project,
                            [
                                bridge_usb_upload_env(
                                    ctx.config,
                                    ctx.plan.default_bridge_profile,
                                    device,
                                )
                            ],
                            target="upload",
                        )
                    )
                    for device in ctx.plan.usb_devices
                ],
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "The bridge firmware is intentionally wide: every bridge device uses the same "
            "binary for a selected profile.",
            "",
        ]
    )
    return lines


def _readme_bridge_ota_section(ctx: _GeneratedReadmeContext) -> list[str]:
    if ctx.default_ota_command is None:
        return []

    lines: list[str] = []
    if ctx.stack_cli_ota_available:
        lines.extend(
            [
                "Build and OTA-upload bridge firmware from the stack CLI:",
                "",
                "```bash",
                stack_command(
                    "ota",
                    ctx.config,
                    ctx.sample_ota_device,
                    config_base_dir=ctx.stack_root,
                ),
                stack_command("ota", ctx.config, config_base_dir=ctx.stack_root),
                "```",
                "",
                "With no device argument, the stack OTA command targets every configured "
                "bridge. Pass multiple device ids for a subset.",
                "If a prerequisite is missing, the command exits with the install command to run.",
                "",
            ]
        )
    lines.extend(
        [
            "OTA a device subset with the default profile firmware from the bridge "
            "project directory:",
            "",
            "```bash",
            ctx.default_ota_command,
            "```",
            "",
            "The command names its OTA config file with `--config`; edit "
            "`lsh_stack.toml` and regenerate instead of editing that JSON by hand.",
            "The wrapper finds the Homie OTA updater in a sibling checkout or "
            "PlatformIO `libdeps`.",
            "Pass `--updater` or set `LSH_HOMIE_OTA_UPDATER` when you want to pin "
            "the updater path.",
            "",
        ]
    )
    return lines


def _readme_platformio_ide_section(ctx: _GeneratedReadmeContext) -> list[str]:
    lines = [
        "Use `deploy-plan.json` when another tool or script needs the same commands as data.",
        "",
        "## PlatformIO IDE",
        "",
        "Open the core or bridge project in VSCode with the PlatformIO extension. Refresh "
        "Project Tasks after regenerating this directory.",
        "",
        f"- Default bridge profile: `{profile_key(ctx.plan.default_bridge_profile)}`.",
        f"- Available bridge profiles: {ctx.bridge_profile_names}.",
        "- Build one default bridge firmware: Project Tasks -> "
        f"`{ctx.plan.default_bridge_env}` -> Build.",
        "- USB-upload one connected bridge: Project Tasks -> "
        f"`{ctx.plan.default_bridge_env}` -> Upload.",
        "- Build or USB-upload one explicit profile: use `bridge_<profile>`.",
    ]
    lines.extend(
        "- USB-upload configured device port: Project Tasks -> "
        f"`{bridge_usb_upload_env(ctx.config, ctx.plan.default_bridge_profile, device)}` -> Upload."
        for device in ctx.plan.usb_devices
    )
    if ctx.default_ota_command is not None:
        lines.extend(
            [
                "",
                "If newly generated custom targets do not appear, run `Developer: Reload "
                "Window`; VSCode can keep a stale PlatformIO task tree after files under "
                "`../generated` change.",
                "",
                "Generated OTA targets use the active PlatformIO Core through "
                "`$PYTHONEXE -m platformio`; inside VSCode this is the extension-managed "
                "PlatformIO, while CLI users can run the commands above directly.",
                "",
                "- OTA one device: Project Tasks -> `bridge_<profile>` -> Custom -> "
                "`LSH OTA <device>`.",
                "- OTA all devices with one firmware: Project Tasks -> `bridge_<profile>` -> "
                "Custom -> `LSH OTA All`.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "OTA custom targets are not generated until "
                "`[deploy.bridge.ota]` is set in `lsh_stack.toml`.",
            ]
        )
    return lines


def _readme_runtime_section(ctx: _GeneratedReadmeContext) -> list[str]:
    return [
        "",
        "## Coordinator CLI",
        "",
        "Run the standalone coordinator with the generated system config and the same "
        "runtime options used by Node-RED:",
        "",
        "```bash",
        _coordinator_cli_command(
            ctx.stack,
            path_from(ctx.stack_root, ctx.output_dir / "system-config.json"),
        ),
        "```",
        "",
        "## Node-RED",
        "",
        "Install `node-red-contrib-lsh-logic`, add the node to a flow and follow "
        "`node-red-setup.md`. The stack generates exact node settings, but the "
        "surrounding Node-RED flow stays in Node-RED where it is easier to inspect and "
        "change.",
        "",
    ]


def _readme_generated_outputs_section(ctx: _GeneratedReadmeContext) -> list[str]:
    return [
        "## Generated Outputs",
        "",
        "- `lsh-stack-config.json`: complete stack export, including external actor metadata.",
        "- `system-config.json`: coordinator `systemConfig`; use the Coordinator CLI "
        "command above for matching runtime options.",
        "- `node-red-setup.md`: Node-RED GUI setup steps and copy-paste values.",
        "- `node-red-lsh-logic.json`: raw Node-RED `lsh-logic` node fields for scripts.",
        "- `bridge-platformio-flags/bridge.txt`: bridge `build_flags` as a plain list.",
        "- `platformio-core.ini`: controller build environments.",
        *(
            [
                "- `platformio-core-system-tools.py`: optional PlatformIO PATH helper "
                "for controller builds."
            ]
            if ctx.config.platformio.core_prefer_system_tools
            else []
        ),
        "- `platformio-bridge.ini`: bridge build and upload environments.",
        *(
            ["- `platformio-bridge-targets.py`: PlatformIO IDE OTA helper targets."]
            if uses_generated_bridge_ota_script(ctx.config)
            else []
        ),
        *(
            [
                "- `bridge-ota.py`: wrapper around the `homie-esp8266` OTA updater.",
                "- `bridge-ota.json`: broker and Homie defaults passed explicitly "
                "to bridge MQTT OTA.",
            ]
            if uses_generated_bridge_ota_script(ctx.config)
            else []
        ),
        "- `deploy-plan.json`: build and upload commands as JSON.",
        "- `README.generated.md`: this guide.",
        "",
    ]


def _readme_overrides_section(_ctx: _GeneratedReadmeContext) -> list[str]:
    return [
        "## Persistent Overrides",
        "",
        "Keep hand-written PlatformIO extensions and local notes outside `generated/`, "
        "usually in `overrides/`, `core/platformio.ini` or `bridge/platformio.ini`.",
        "Deep compiler, linker, board, package and local toolchain choices stay in "
        "those PlatformIO files. Use `platformio.core_prefer_system_tools = true` "
        "only when generated core environments must prepend system compiler "
        "directories before PlatformIO packages.",
        "Bridge `defines` in `lsh_stack.toml` replace generated `-D` flags with the "
        "same name before raw appended flags are added.",
    ]


def _render_bridge_profile_env(  # noqa: PLR0913
    *,
    config: StackConfig,
    devices: list[str],
    flag_section: str,
    profile: BridgeProfileSettings,
    target_script: str | None,
    bridge_ota: BridgeOtaArtifacts | None,
) -> list[str]:
    build_env = bridge_build_env(config, profile)
    lines = [
        f"[env:{build_env}]",
        f"extends = {profile.base_env}",
        "build_flags =",
        f"    ${{{profile.base_env}.build_flags}}",
        f"    ${{{flag_section}.build_flags}}",
        f"custom_lsh_stack_profile = {profile_key(profile)}",
    ]

    if profile.ota:
        ota_template = bridge_ota_template(config, bridge_ota)
        if ota_template is not None and target_script is not None:
            lines.extend(
                [
                    f"extra_scripts = post:{target_script}",
                    f"custom_lsh_stack_ota_template = {ota_template}",
                    "custom_lsh_stack_ota_devices =",
                    *[f"    {device}" for device in devices],
                ]
            )

    lines.append("")
    return lines


def _render_bridge_usb_upload_envs(
    config: StackConfig,
    devices: list[str],
    profiles: tuple[BridgeProfileSettings, ...],
) -> list[str]:
    lines: list[str] = []
    for profile in profiles:
        for device in devices:
            usb_port = bridge_usb_port(config, device)
            if usb_port is None:
                continue
            lines.extend(_render_bridge_usb_upload_env(config, profile, device, usb_port))
    return lines


def _render_bridge_usb_upload_env(
    config: StackConfig,
    profile: BridgeProfileSettings,
    device: str,
    usb_port: str,
) -> list[str]:
    return [
        f"[env:{bridge_usb_upload_env(config, profile, device)}]",
        f"extends = env:{bridge_build_env(config, profile)}",
        f"upload_port = {usb_port}",
        "",
    ]


def _node_red_setting_rows(node_red_config: JsonObject) -> list[str]:
    rows: list[str] = []
    for raw_key in sorted(node_red_config):
        key = str(raw_key)
        if key == "systemConfigJson":
            continue
        rows.append(
            "| "
            f"{_markdown_table_cell(_human_label(key))} | "
            f"`{_markdown_table_cell(key)}` | "
            f"{_markdown_inline_code(node_red_config[key])} |"
        )
    return rows


def _node_red_system_config_json(node_red_config: JsonObject) -> str:
    raw_system_config = str(node_red_config.get("systemConfigJson", "{}"))
    try:
        return json.dumps(json.loads(raw_system_config), indent=2)
    except json.JSONDecodeError:
        return raw_system_config


def _human_label(key: str) -> str:
    if key == "lshBasePath":
        return "LSH Base Path"
    label = re.sub(r"(?<!^)([A-Z])", r" \1", key).replace("_", " ")
    return label[:1].upper() + label[1:]


def _markdown_inline_code(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return f"`{_markdown_table_cell(text)}`"


def _markdown_table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("`", r"\`").replace("\n", "<br>")


def _coordinator_cli_command(stack: JsonObject, system_config_path: str) -> str:
    coordinator = json_object(stack["coordinator"])
    options = json_object(coordinator["options"])
    command = [
        "npx",
        "labo-smart-home-coordinator",
        "--broker",
        "mqtt://localhost:1883",
        "--config",
        system_config_path,
        *_coordinator_cli_options(options),
    ]
    return " ".join(shlex.quote(part) for part in command)


def _project_command_path(path: Path | None, base_dir: Path) -> str:
    """Return a readable project path for commands in generated docs."""
    if path is None:
        return project_command_path(path)
    return path_from(base_dir, path)


def _coordinator_cli_options(options: JsonObject) -> list[str]:
    pairs: list[tuple[str, object | None]] = [
        ("--protocol", options.get("protocol")),
        ("--homie-base-path", options.get("homieBasePath")),
        ("--lsh-base-path", options.get("lshBasePath")),
        ("--service-topic", options.get("serviceTopic")),
        ("--other-devices-prefix", options.get("otherDevicesPrefix")),
        ("--click-timeout", options.get("clickTimeout")),
        ("--click-cleanup", options.get("clickCleanupInterval")),
        ("--watchdog-interval", options.get("watchdogInterval")),
        ("--ping-threshold", options.get("interrogateThreshold")),
        ("--ping-timeout", options.get("pingTimeout")),
        ("--initial-state-timeout", options.get("initialStateTimeout")),
        ("--other-actors-topic", options.get("otherActorsTopic")),
    ]
    qos = json_object(options.get("subscriptionQos", {}), "coordinator.options.subscriptionQos")
    pairs.extend(
        [
            ("--qos-conf", qos.get("conf")),
            ("--qos-state", qos.get("state")),
            ("--qos-events", qos.get("events")),
            ("--qos-bridge", qos.get("bridge")),
            ("--qos-homie-state", qos.get("homieState")),
        ]
    )
    cli_options: list[str] = []
    for name, value in pairs:
        if value is None:
            continue
        cli_options.extend([name, str(value)])
    return cli_options


def _core_static_config_script_path(config: StackConfig, env_name: str) -> str:
    configured = config.platformio.core_extra_script
    if configured is not None:
        return path_for_platformio(configured, config.platformio.core_project)

    if config.core.tool is not None:
        script = config.core.tool.parent / "platformio_lsh_static_config.py"
        return path_for_platformio(script, config.platformio.core_project)

    return f".pio/libdeps/{env_name}/lsh-core/tools/platformio_lsh_static_config.py"


def _core_extra_script_entries(
    config: StackConfig,
    env_name: str,
    system_tools_script_path: Path | None,
) -> list[str]:
    entries: list[str] = []
    if system_tools_script_path is not None:
        system_script = path_for_platformio(
            system_tools_script_path,
            config.platformio.core_project,
        )
        entries.append(f"pre:{system_script}")
    entries.append(f"pre:{_core_static_config_script_path(config, env_name)}")
    return entries


def _core_extra_script_lines(
    config: StackConfig,
    base_env: str,
    script_entries: list[str],
) -> list[str]:
    base_extra_scripts = _base_extra_scripts(config, base_env)
    missing_entries = [
        entry for entry in script_entries if not script_entry_present(entry, base_extra_scripts)
    ]
    if not missing_entries:
        return []
    base_extra_scripts_reference = _base_extra_scripts_reference(base_env, base_extra_scripts)
    if base_extra_scripts_reference is not None:
        before_base = [
            entry for entry in missing_entries if "platformio-core-system-tools.py" in entry
        ]
        after_base = [entry for entry in missing_entries if entry not in before_base]
        return [
            "extra_scripts =",
            *[f"    {entry}" for entry in before_base],
            f"    {base_extra_scripts_reference}",
            *[f"    {entry}" for entry in after_base],
        ]
    if len(missing_entries) == 1:
        return [f"extra_scripts = {missing_entries[0]}"]
    return ["extra_scripts =", *[f"    {entry}" for entry in missing_entries]]


def _base_extra_scripts(config: StackConfig, base_env: str) -> list[str]:
    parser = read_platformio_config(config.platformio.core_project)
    if parser is None:
        return []
    return inherited_option_values(
        parser,
        base_env,
        "extra_scripts",
    )


def _base_extra_scripts_reference(
    base_env: str,
    base_extra_scripts: list[str],
) -> str | None:
    if not base_extra_scripts:
        return None
    return f"${{{base_env}.extra_scripts}}"
