"""Render stack composer outputs for humans and files."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .bridge_ota_script import render_bridge_ota_script
from .deploy import (
    BridgeOtaArtifacts,
    bridge_ota_command,
    bridge_ota_template,
    bridge_usb_port,
    pio_command,
    render_bridge_ota_config,
    render_deploy_plan,
    uses_generated_bridge_ota_script,
)
from .models import BridgeProfileSettings, JsonObject, StackConfig
from .platformio_batch_script import render_platformio_bridge_batch_script
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
    default_bridge_profile,
    device_names,
    json_list,
    json_object,
    profile_key,
)
from .render_common import (
    env_name as stack_env_name,
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
    mapped_clicks = json_list(stack.get("mappedNetworkClicks", []))
    unmapped_clicks = json_list(coordinator.get("unmappedNetworkClicks", []))

    lines = [
        "LSH stack composer",
        f"- stack config: {config.path}",
        f"- core config: {config.core.devices}",
        f"- transport: {json_object(stack['transport'])['mode']}",
        f"- MQTT protocol: {stack['protocol']}",
        f"- devices: {len(devices)}",
        f"- mapped network clicks: {len(mapped_clicks)}",
        f"- core network-click declarations: {len(unmapped_clicks)}",
        f"- bridge firmware: one wide build profile ({len(bridge_flags)} build flags)",
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

    core_ini_path = output_dir / "platformio-core.ini"
    core_ini_path.write_text(render_platformio_core_ini(config, stack), encoding="utf-8")
    written.append(core_ini_path)

    bridge_batch_script_path = output_dir / "platformio-bridge-batch.py"
    bridge_batch_script_path.write_text(render_platformio_bridge_batch_script(), encoding="utf-8")
    written.append(bridge_batch_script_path)

    bridge_ota = _write_bridge_ota_artifacts(output_dir, config, written)

    bridge_ini_path = output_dir / "platformio-bridge.ini"
    bridge_ini_path.write_text(
        render_platformio_bridge_ini(
            config,
            stack,
            bridge_batch_script_path,
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


def render_platformio_core_ini(config: StackConfig, stack: JsonObject) -> str:
    """Render PlatformIO environments for controller firmware builds."""
    devices = device_names(stack)
    core_project = config.platformio.core_project
    config_path = path_for_platformio(config.core.devices, core_project)
    lines = [
        "; Generated by lsh-stack. Do not edit by hand.",
        "; Include this file from the controller PlatformIO project:",
        "; [platformio]",
        "; extra_configs = generated/platformio-core.ini",
        "",
        "[lsh_stack_core]",
        f"custom_lsh_config = {config_path}",
        "",
    ]

    for device in devices:
        env_name = stack_env_name(config.platformio.core_env_prefix, device)
        script_path = _core_extra_script_path(config, env_name)
        extra_scripts = _core_extra_script_lines(config, script_path)
        lines.extend(
            [
                f"[env:{env_name}]",
                f"extends = {config.platformio.core_base_env}",
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
    batch_script_path: Path,
    bridge_ota: BridgeOtaArtifacts | None = None,
) -> str:
    """Render one wide bridge firmware per profile plus OTA targets per device."""
    bridge_device_names = list(bridge_devices(stack))
    profiles = bridge_profiles(config)
    default_profile = default_bridge_profile(profiles)
    batch_script = path_for_platformio(batch_script_path, config.platformio.bridge_project)
    flags = [str(flag) for flag in json_list(json_object(stack["bridge"])["platformioBuildFlags"])]
    flag_section = bridge_flag_section("wide")
    lines = [
        "; Generated by lsh-stack. Do not edit by hand.",
        "; Include this file from the bridge PlatformIO project:",
        "; [platformio]",
        "; extra_configs = generated/platformio-bridge.ini",
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
                batch_script=batch_script,
                bridge_ota=bridge_ota,
            )
        )

    if default_profile is not None and config.platformio.bridge_profiles:
        lines.extend(_render_bridge_default_profile_alias(config, default_profile))

    lines.extend(_render_bridge_usb_upload_envs(config, bridge_device_names, profiles))
    lines.extend(_render_bridge_batch_envs(config, profiles, batch_script))
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


def render_generated_readme(config: StackConfig, stack: JsonObject, output_dir: Path) -> str:
    """Render a friendly guide beside generated deployment artifacts."""
    devices = device_names(stack)
    bridge_project = project_command_path(config.platformio.bridge_project)
    core_project = project_command_path(config.platformio.core_project)
    first_device = devices[0] if devices else "device"
    core_env = stack_env_name(config.platformio.core_env_prefix, first_device)
    bridge_env = stack_env_name(config.platformio.bridge_env_prefix)
    core_extra_config = path_for_platformio(
        output_dir / "platformio-core.ini", config.platformio.core_project
    )
    bridge_extra_config = path_for_platformio(
        output_dir / "platformio-bridge.ini",
        config.platformio.bridge_project,
    )
    bridge_device_names = list(bridge_devices(stack))
    profiles = bridge_profiles(config)
    default_profile = default_bridge_profile(profiles)
    usb_devices = [
        device for device in bridge_device_names if bridge_usb_port(config, device) is not None
    ]
    first_usb_device = usb_devices[0] if usb_devices else None
    bridge_build_envs = [bridge_build_env(config, profile) for profile in profiles]
    bridge_profile_names = ", ".join(profile_key(profile) for profile in profiles)
    bridge_batch_env = stack_env_name(config.platformio.bridge_env_prefix, "batch")
    has_multiple_bridge_profiles = len(profiles) > 1
    bridge_ota_script_path = (
        output_dir / "bridge-ota.py" if uses_generated_bridge_ota_script(config) else None
    )
    bridge_ota_config_path = (
        output_dir / "bridge-ota.json" if uses_generated_bridge_ota_script(config) else None
    )
    bridge_ota = BridgeOtaArtifacts(script=bridge_ota_script_path, config=bridge_ota_config_path)
    sample_ota_device = bridge_device_names[0] if bridge_device_names else ""
    default_ota_command = bridge_ota_command(
        config,
        sample_ota_device,
        f".pio/build/{bridge_build_env(config, default_profile)}/firmware.bin",
        bridge_ota,
    )
    ota_targets_available = default_ota_command is not None
    stack_cli_ota_available = uses_generated_bridge_ota_script(config)

    lines = [
        "# Generated LSH Stack Files",
        "",
        "These files are generated from `lsh_stack.toml`. Edit the TOML files, then regenerate.",
        "",
        "## PlatformIO Includes",
        "",
        "Controller project:",
        "",
        "```ini",
        "[platformio]",
        f"extra_configs = {core_extra_config}",
        "```",
        "",
        "Bridge project:",
        "",
        "```ini",
        "[platformio]",
        f"extra_configs = {bridge_extra_config}",
        "```",
        "",
        "## PlatformIO CLI",
        "",
        "If `platformio` is available in your shell, these commands are the direct CLI "
        "equivalent of the generated IDE tasks.",
        "",
        "Build one controller firmware:",
        "",
        "```bash",
        " ".join(pio_command(core_project, [core_env], target=None)),
        "```",
        "",
        "Build the default wide bridge firmware:",
        "",
        "```bash",
        " ".join(pio_command(bridge_project, [bridge_env], target=None)),
        "```",
        "",
    ]
    if has_multiple_bridge_profiles:
        lines.extend(
            [
                "Build every bridge firmware profile:",
                "",
                "```bash",
                " ".join(pio_command(bridge_project, bridge_build_envs, target=None)),
                "```",
                "",
            ]
        )
    if first_usb_device is not None:
        lines.extend(
            [
                "USB-upload a configured bridge port with the default profile firmware:",
                "",
                "```bash",
                " ".join(
                    pio_command(
                        bridge_project,
                        [bridge_usb_upload_env(config, default_profile, first_usb_device)],
                        target="upload",
                    )
                ),
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
    if default_ota_command is not None:
        if stack_cli_ota_available:
            lines.extend(
                [
                    "Build and OTA-upload bridge firmware from the stack CLI:",
                    "",
                    "```bash",
                    _stack_ota_cli_command(config, sample_ota_device),
                    _stack_ota_cli_command(config),
                    "```",
                    "",
                    "With no device argument, `lsh-stack ota` targets every configured bridge. "
                    "Pass multiple device ids for a subset.",
                    "If a prerequisite is missing, the command exits with the install "
                    "command to run.",
                    "",
                ]
            )
        lines.extend(
            [
                "OTA a device subset with the default profile firmware:",
                "",
                "```bash",
                default_ota_command,
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
    lines.extend(
        [
            "Use `deploy-plan.json` when another tool or script needs the same commands as data.",
            "",
            "## PlatformIO IDE",
            "",
            "Open the core or bridge project in VSCode with the PlatformIO extension. Refresh "
            "Project Tasks after regenerating this directory.",
            "If newly generated custom targets do not appear, run `Developer: Reload Window`; "
            "VSCode can keep a stale PlatformIO task tree after files under `../generated` "
            "change.",
            "",
            f"- Default bridge profile: `{profile_key(default_profile)}`.",
            f"- Available bridge profiles: {bridge_profile_names}.",
            f"- Build one default bridge firmware: Project Tasks -> `{bridge_env}` -> Build.",
            f"- USB-upload one connected bridge: Project Tasks -> `{bridge_env}` -> Upload.",
            "- Build or USB-upload one explicit profile: use `bridge_<profile>`.",
        ]
    )
    if first_usb_device is not None:
        default_usb_env = bridge_usb_upload_env(config, default_profile, first_usb_device)
        lines.append(
            "- USB-upload one configured device port: Project Tasks -> "
            f"`{default_usb_env}` -> Upload."
        )
    if ota_targets_available:
        lines.extend(
            [
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
                "",
            ]
        )
    if has_multiple_bridge_profiles:
        lines.extend(
            [
                f"- Build every generated profile: Project Tasks -> `{bridge_batch_env}` -> "
                "Custom -> `LSH Build All`.",
            ]
        )
    lines.extend(
        [
            "",
            "## Node-RED",
            "",
            "Install `node-red-contrib-lsh-logic`, add the node to a flow and follow "
            "`node-red-setup.md`. The stack generates exact node settings, but the "
            "surrounding Node-RED flow stays in Node-RED where it is easier to inspect and "
            "change.",
            "",
            "## Generated Outputs",
            "",
            "- `lsh-stack-config.json`: complete stack export, including external actor metadata.",
            "- `system-config.json`: coordinator `systemConfig`.",
            "- `node-red-setup.md`: Node-RED GUI setup steps and copy-paste values.",
            "- `node-red-lsh-logic.json`: raw Node-RED `lsh-logic` node fields for scripts.",
            "- `bridge-platformio-flags/bridge.txt`: bridge `build_flags` as a plain list.",
            "- `platformio-core.ini`: controller build environments.",
            "- `platformio-bridge.ini`: bridge build and upload environments.",
            "- `platformio-bridge-batch.py`: PlatformIO IDE helper targets.",
            *(
                [
                    "- `bridge-ota.py`: wrapper around the `homie-esp8266` OTA updater.",
                    "- `bridge-ota.json`: broker and Homie defaults passed explicitly "
                    "to bridge MQTT OTA.",
                ]
                if uses_generated_bridge_ota_script(config)
                else []
            ),
            "- `deploy-plan.json`: build and upload commands as JSON.",
            "- `README.generated.md`: this guide.",
            "",
            "## Persistent Overrides",
            "",
            "Keep hand-written PlatformIO extensions and local notes outside `generated/`, "
            "usually in `overrides/`, `core/platformio.ini` or `bridge/platformio.ini`.",
            "Bridge `defines` in `lsh_stack.toml` replace generated `-D` flags with the "
            "same name before raw appended flags are added.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_bridge_profile_env(  # noqa: PLR0913
    *,
    config: StackConfig,
    devices: list[str],
    flag_section: str,
    profile: BridgeProfileSettings,
    batch_script: str,
    bridge_ota: BridgeOtaArtifacts | None,
) -> list[str]:
    build_env = bridge_build_env(config, profile)
    lines = [
        f"[env:{build_env}]",
        f"extends = {profile.base_env}",
        f"extra_scripts = post:{batch_script}",
        "build_flags =",
        f"    ${{{profile.base_env}.build_flags}}",
        f"    ${{{flag_section}.build_flags}}",
        f"custom_lsh_stack_profile = {profile_key(profile)}",
    ]

    if profile.ota:
        ota_template = bridge_ota_template(config, bridge_ota)
        if ota_template is not None:
            lines.extend(
                [
                    f"custom_lsh_stack_ota_template = {ota_template}",
                    "custom_lsh_stack_ota_devices =",
                    *[f"    {device}" for device in devices],
                ]
            )

    lines.append("")
    return lines


def _render_bridge_default_profile_alias(
    config: StackConfig,
    profile: BridgeProfileSettings,
) -> list[str]:
    build_env = stack_env_name(config.platformio.bridge_env_prefix)
    profile_build_env = bridge_build_env(config, profile)
    return [f"[env:{build_env}]", f"extends = env:{profile_build_env}", ""]


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


def _render_bridge_batch_envs(
    config: StackConfig,
    profiles: tuple[BridgeProfileSettings, ...],
    batch_script: str,
) -> list[str]:
    lines: list[str] = []
    if len(profiles) > 1:
        default_profile = default_bridge_profile(profiles)
        lines.extend(
            _render_bridge_batch_env(
                name=stack_env_name(config.platformio.bridge_env_prefix, "batch"),
                base_env=default_profile.base_env,
                batch_script=batch_script,
                build_envs=[bridge_build_env(config, profile) for profile in profiles],
            )
        )
    return lines


def _render_bridge_batch_env(
    *,
    name: str,
    base_env: str,
    batch_script: str,
    build_envs: list[str],
) -> list[str]:
    lines = [
        f"[env:{name}]",
        f"extends = {base_env}",
        f"extra_scripts = post:{batch_script}",
        "custom_lsh_stack_batch_build_envs =",
        *[f"    {env_name}" for env_name in build_envs],
    ]
    lines.append("")
    return lines


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
    label = re.sub(r"(?<!^)([A-Z])", r" \1", key).replace("_", " ")
    return label[:1].upper() + label[1:]


def _markdown_inline_code(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return f"`{_markdown_table_cell(text)}`"


def _markdown_table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("`", r"\`").replace("\n", "<br>")


def _stack_ota_cli_command(config: StackConfig, device: str | None = None) -> str:
    parts = ["lsh-stack", "ota"]
    if config.path.name != "lsh_stack.toml":
        parts.extend(["--config", config.path.name])
    if device is not None:
        parts.append(device)
    return " ".join(parts)


def _core_extra_script_path(config: StackConfig, env_name: str) -> str:
    configured = config.platformio.core_extra_script
    if configured is not None:
        return path_for_platformio(configured, config.platformio.core_project)

    if config.core.tool is not None:
        script = config.core.tool.parent / "platformio_lsh_static_config.py"
        return path_for_platformio(script, config.platformio.core_project)

    return f".pio/libdeps/{env_name}/lsh-core/tools/platformio_lsh_static_config.py"


def _core_extra_script_lines(config: StackConfig, script_path: str) -> list[str]:
    base_extra_scripts = _base_extra_scripts(config)
    script_entry = f"pre:{script_path}"
    if script_entry_present(script_entry, base_extra_scripts):
        return []
    base_extra_scripts_reference = _base_extra_scripts_reference(config, base_extra_scripts)
    if base_extra_scripts_reference is not None:
        return [
            "extra_scripts =",
            f"    {base_extra_scripts_reference}",
            f"    {script_entry}",
        ]
    return [f"extra_scripts = {script_entry}"]


def _base_extra_scripts(config: StackConfig) -> list[str]:
    parser = read_platformio_config(config.platformio.core_project)
    if parser is None:
        return []
    return inherited_option_values(
        parser,
        config.platformio.core_base_env,
        "extra_scripts",
    )


def _base_extra_scripts_reference(
    config: StackConfig,
    base_extra_scripts: list[str],
) -> str | None:
    base_env = config.platformio.core_base_env
    if not base_extra_scripts:
        return None
    return f"${{{base_env}.extra_scripts}}"
