"""Tests for the public LSH stack composer."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from lsh_stack_config import __version__, cli, cli_runtime, scaffold
from lsh_stack_config.composer import compose_stack
from lsh_stack_config.errors import StackConfigError
from lsh_stack_config.models import JsonObject, StackConfig
from lsh_stack_config.parser import load_stack_config
from lsh_stack_config.render import write_output_tree


def test_package_version_matches_pyproject() -> None:
    """The runtime version shown by release artifacts tracks pyproject."""
    pyproject = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert __version__ == pyproject["project"]["version"]


def test_lsh_stack_new_uses_zipapp_launcher_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starter docs should keep working when lsh-stack is a release .pyz file."""
    archive = tmp_path / "lsh-stack.pyz"
    archive.write_bytes(b"zipapp")
    project = tmp_path / "installation"
    monkeypatch.setattr(sys, "argv", [str(archive), "new"])
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(scaffold, "_source_checkout_root", lambda: None)

    assert cli.main(["new", str(project)]) == 0
    readme = (project / "README.md").read_text(encoding="utf-8")
    stack_toml = (project / "lsh_stack.toml").read_text(encoding="utf-8")
    assert f"/usr/bin/python3 {archive} setup" in readme
    assert f"/usr/bin/python3 {archive} status" in readme
    assert f"/usr/bin/python3 {archive} doctor" in readme
    assert "[bridge.defaults.build_flags]" in stack_toml
    assert '# append = ["-Wall"]' in stack_toml


def test_cli_help_shows_first_run_examples(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The top-level help should teach the shortest successful path."""
    monkeypatch.setattr(cli, "lsh_stack_command", lambda: "python ./lsh-stack.pyz")

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "Typical flow:" in output
    assert "python ./lsh-stack.pyz new my-home" in output
    assert "python ./lsh-stack.pyz setup" in output
    assert "python ./lsh-stack.pyz status" in output
    assert "python ./lsh-stack.pyz ota --dry-run" in output


def test_cli_subcommand_help_uses_current_launcher(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Subcommand examples should not assume the console script exists."""
    monkeypatch.setattr(cli, "lsh_stack_command", lambda: "/usr/bin/python3 ./lsh-stack.pyz")

    with pytest.raises(SystemExit) as exc:
        cli.main(["ota", "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "/usr/bin/python3 ./lsh-stack.pyz ota --dry-run" in output
    assert "/usr/bin/python3 ./lsh-stack.pyz ota panel" in output


def test_lsh_stack_entrypoint_preserves_error_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zipapp execution must exit non-zero when the CLI rejects input."""
    monkeypatch.setattr(sys, "argv", ["lsh-stack", "new", str(tmp_path / "legacy.toml")])

    with pytest.raises(SystemExit) as exc:
        cli.entrypoint()

    assert exc.value.code == 2


def test_stack_config_generates_end_to_end_node_red_and_bridge_config(tmp_path: Path) -> None:
    """Friendly TOML names become validated coordinator and Node-RED JSON."""
    config_path = _write_stack_config(
        tmp_path,
        """
        schema_version = 1

        [core]
        devices = "lsh_devices.toml"

        [mqtt]
        codec = "json"

        [coordinator]
        click_timeout = "2500ms"

        [external_actors.zigbee_table_lamp]
        state_key = "other_devices.zigbee_table_lamp.state"

        [[network_clicks]]
        source = "panel.logic_button"
        type = "long"
        actors = [{ device = "lights", actuators = ["ceiling"] }]
        other_actors = ["zigbee_table_lamp"]
        """,
    )

    stack = compose_stack(load_stack_config(config_path), _core_export())
    panel = _device_entry(stack, "panel")
    action = panel["longClickButtons"][0]

    assert stack["protocol"] == "json"
    assert (
        "-DCONFIG_MSG_PACK_ARDUINO" in stack["bridge"]["devices"]["panel"]["platformioBuildFlags"]
    )
    assert (
        "-DCONFIG_MSG_PACK_MQTT" not in stack["bridge"]["devices"]["panel"]["platformioBuildFlags"]
    )
    assert stack["coordinator"]["options"]["clickTimeout"] == 2.5
    assert action == {
        "id": 7,
        "actors": [{"name": "lights", "allActuators": False, "actuators": [3]}],
        "otherActors": ["zigbee_table_lamp"],
    }
    assert stack["externalActors"] == [
        {
            "name": "zigbee_table_lamp",
            "stateKey": "other_devices.zigbee_table_lamp.state",
        }
    ]
    assert "externalActors" not in stack["nodeRed"]["lshLogic"]
    assert (
        json.loads(stack["nodeRed"]["lshLogic"]["systemConfigJson"])
        == stack["coordinator"]["systemConfig"]
    )


def test_stack_config_writes_platformio_fragments_and_deploy_plan(tmp_path: Path) -> None:
    """Generated PlatformIO files build one wide bridge firmware for the stack."""
    config_path = _write_stack_config(
        tmp_path,
        """
        schema_version = 1

        [core]
        devices = "lsh_devices.toml"

        [platformio]
        core_project = "core"
        bridge_project = "bridge"
        core_base_env = "core_release"
        bridge_base_env = "bridge_base"

        [deploy.bridge]
        default_method = "ota"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_username = "homie"
        broker_password_env = "LSH_OTA_PASSWORD"

        [deploy.bridge.devices.panel]
        usb_port = "/dev/ttyUSB0"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    bridge_ini = (output_dir / "platformio-bridge.ini").read_text(encoding="utf-8")
    deploy_plan = json.loads((output_dir / "deploy-plan.json").read_text(encoding="utf-8"))
    generated_readme = (output_dir / "README.generated.md").read_text(encoding="utf-8")
    expected_template = (
        "custom_lsh_stack_ota_template = {python} ../generated/bridge-ota.py "
        "--config ../generated/bridge-ota.json --device-id {device} {firmware}"
    )
    expected_command = (
        "python ../generated/bridge-ota.py --config ../generated/bridge-ota.json "
        "--device-id panel $SOURCE"
    )

    assert "[lsh_stack_bridge_wide]" in bridge_ini
    assert "-DCONFIG_MAX_ACTUATORS=1U" in bridge_ini
    assert "[env:bridge]" in bridge_ini
    assert "extends = bridge_base" in bridge_ini
    assert "${bridge_base.build_flags}" in bridge_ini
    assert "${lsh_stack_bridge_wide.build_flags}" in bridge_ini
    assert expected_template in bridge_ini
    assert "custom_lsh_stack_ota_devices =" in bridge_ini
    assert "    panel" in bridge_ini
    assert "    lights" in bridge_ini
    assert "[env:bridge_usb_panel]" in bridge_ini
    assert "extends = env:bridge" in bridge_ini
    assert "upload_port = /dev/ttyUSB0" in bridge_ini
    assert deploy_plan["bridgeFirmware"]["buildEnv"] == "bridge"
    assert deploy_plan["bridgeFirmware"]["usbTargets"]["panel"] == {
        "env": "bridge_usb_panel",
        "uploadPort": "/dev/ttyUSB0",
        "command": [
            "platformio",
            "run",
            "-d",
            str(tmp_path / "bridge"),
            "-e",
            "bridge_usb_panel",
            "-t",
            "upload",
        ],
    }
    assert deploy_plan["bridge"]["panel"]["otaTarget"] == "lsh_ota_panel"
    assert deploy_plan["bridge"]["panel"]["defaultMethod"] == "ota"
    assert deploy_plan["bridge"]["panel"]["defaultUploadCommand"] == expected_command
    assert deploy_plan["bridge"]["panel"]["usbPort"] == "/dev/ttyUSB0"
    assert deploy_plan["batch"]["buildAllBridgeProfiles"] == [
        "platformio",
        "run",
        "-d",
        str(tmp_path / "bridge"),
        "-e",
        "bridge",
    ]
    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")
    assert (
        "extra_scripts = pre:.pio/libdeps/core_panel/lsh-core/tools/platformio_lsh_static_config.py"
        in core_ini
    )
    assert "LSH OTA <device>" in generated_readme
    assert " ota panel" in generated_readme
    assert "OTA custom targets are not generated until" not in generated_readme
    assert "bridge-platformio-flags/bridge.txt" in generated_readme
    assert "platformio-bridge-targets.py" in generated_readme
    assert "bridge_usb_panel" in generated_readme
    assert "Upload.\n\nIf newly generated custom targets" in generated_readme
    assert "--protocol msgpack" in generated_readme
    assert "--config" in generated_readme
    assert "Developer: Reload Window" in generated_readme


def test_stack_config_writes_typed_mqtt_ota_command(tmp_path: Path) -> None:
    """Users can configure broker-specific OTA arguments without shell templates."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [mqtt]
        homie_base_path = "lab/homie/5/"

        [deploy.bridge]
        default_method = "ota"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_port = 8883
        broker_username = "lsh"
        broker_password_env = "LSH_OTA_PASSWORD"
        homie_version = "5"
        timeout = 180
        broker_tls_cacert = "certs/ca.pem"
        broker_tls_insecure = true
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    bridge_ini = (output_dir / "platformio-bridge.ini").read_text(encoding="utf-8")
    deploy_plan = json.loads((output_dir / "deploy-plan.json").read_text(encoding="utf-8"))
    generated_readme = (output_dir / "README.generated.md").read_text(encoding="utf-8")
    stack_export = json.loads((output_dir / "lsh-stack-config.json").read_text(encoding="utf-8"))
    ota_script = output_dir / "bridge-ota.py"
    ota_config = output_dir / "bridge-ota.json"

    expected_template = (
        f"custom_lsh_stack_ota_template = {{python}} {ota_script} --config {ota_config} "
        "--device-id {device} {firmware}"
    )
    expected_command = f"python {ota_script} --config {ota_config} --device-id panel $SOURCE"

    assert ota_script.is_file()
    assert ota_config.is_file()
    ota_script_text = ota_script.read_text(encoding="utf-8")
    assert 'UPDATER_ENV = "LSH_HOMIE_OTA_UPDATER"' in ota_script_text
    assert 'Path("scripts") / "homie_ota.py"' in ota_script_text
    assert "ota_updater.py" not in ota_script_text
    assert "def _prompt_for_password_env" in ota_script_text
    assert "def _check_python_ota_dependencies" in ota_script_text
    assert "def _print_wrapper_help" in ota_script_text
    assert 'root / "bridge" / ".pio" / "libdeps"' in ota_script_text
    assert "paho-mqtt" in ota_script_text
    assert "def _help_requested" in ota_script_text
    assert "MQTT/OTA password" in ota_script_text
    assert "subprocess.run(" in ota_script_text
    assert "[sys.executable, str(updater), *passthrough]" in ota_script_text
    help_result = subprocess.run(  # noqa: S603 - generated tmp_path script under test.
        [sys.executable, str(ota_script), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert "Generated LSH bridge OTA wrapper." in help_result.stdout
    assert "lsh-stack ota [device...]" in help_result.stdout
    assert "Could not find" not in help_result.stderr
    assert json.loads(ota_config.read_text(encoding="utf-8")) == {
        "schema": "homie-ota-config/v1",
        "broker": {
            "host": "mqtt.lan",
            "port": 8883,
            "username": "lsh",
            "password_env": "LSH_OTA_PASSWORD",
            "tls_cacert": "certs/ca.pem",
            "tls_insecure": True,
        },
        "homie": {"base_topic": "lab/homie/5/", "version": "5"},
        "ota": {"timeout": 180},
    }
    assert expected_template in bridge_ini
    assert deploy_plan["bridge"]["panel"]["defaultUploadCommand"] == expected_command
    assert deploy_plan["bridgeFirmware"]["otaAllCommands"] == [
        expected_command,
        expected_command.replace("--device-id panel", "--device-id lights"),
    ]
    assert " ota panel" in generated_readme
    assert " ota\n" in generated_readme
    assert stack_export["deploy"]["bridge"]["ota"]["brokerPasswordEnv"] == "LSH_OTA_PASSWORD"
    assert stack_export["deploy"]["bridge"]["ota"]["baseTopic"] is None


def test_generated_readme_uses_zipapp_launcher_for_stack_ota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated OTA docs should match the launcher used to run the pyz."""
    archive = tmp_path / "lsh-stack.pyz"
    archive.write_bytes(b"zipapp")
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [deploy.bridge]
        default_method = "ota"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())
    monkeypatch.setattr(sys, "argv", [str(archive), "generate"])
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    generated_readme = (output_dir / "README.generated.md").read_text(encoding="utf-8")
    assert f"/usr/bin/python3 {archive} ota panel" in generated_readme
    assert "lsh-stack ota" not in generated_readme


def test_stack_config_generated_readme_hides_ota_when_no_ota_template(
    tmp_path: Path,
) -> None:
    """The generated guide only documents OTA targets when they really exist."""
    config_path = _write_stack_config(
        tmp_path,
        """
        schema_version = 1

        [core]
        devices = "lsh_devices.toml"

        [platformio]
        core_project = "core"
        bridge_project = "bridge"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    generated_readme = (output_dir / "README.generated.md").read_text(encoding="utf-8")

    assert "OTA custom targets are not generated until" in generated_readme
    assert "## Regenerate" in generated_readme
    assert "Commands below are intended to be run from the stack project root." in generated_readme
    assert "lsh-stack.py generate" in generated_readme
    assert "lsh-stack.py doctor" in generated_readme
    assert "lsh-stack.py status" in generated_readme
    assert "LSH OTA <device>" not in generated_readme
    assert "bridge-platformio-flags/bridge.txt" in generated_readme
    assert "platformio-bridge-targets.py" not in generated_readme
    assert "Developer: Reload Window" not in generated_readme
    assert "core/platformio.ini" in generated_readme
    assert "bridge/platformio.ini" in generated_readme
    assert "bridge_batch" not in generated_readme
    assert "root `platformio.ini`" not in generated_readme
    assert f"platformio run -d {tmp_path}" not in generated_readme
    assert "platformio run -d core -e core_panel" in generated_readme
    assert "platformio run -d bridge -e bridge" in generated_readme
    assert "--config generated/system-config.json" in generated_readme
    assert not (output_dir / "platformio-bridge-targets.py").exists()
    assert not (output_dir / "platformio-bridge-batch.py").exists()


def test_stack_config_writes_bridge_profiles_custom_ota_and_batch_targets(
    tmp_path: Path,
) -> None:
    """PlatformIO IDE users get wide profile envs plus Homie OTA custom targets."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        bridge_project = "bridge"
        bridge_env_prefix = "bridge"

        [[platformio.bridge_profiles]]
        name = "release"
        extends = "stack_bridge_release"

        [[platformio.bridge_profiles]]
        name = "littlefs"
        extends = "stack_bridge_littlefs"
        default = true

        [deploy.bridge]
        default_method = "ota"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_username = "homie"
        broker_password_env = "LSH_OTA_PASSWORD"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    bridge_ini = (output_dir / "platformio-bridge.ini").read_text(encoding="utf-8")
    deploy_plan = json.loads((output_dir / "deploy-plan.json").read_text(encoding="utf-8"))
    targets_script = (output_dir / "platformio-bridge-targets.py").read_text(encoding="utf-8")

    assert "[env:bridge_release]" in bridge_ini
    assert "extends = stack_bridge_release" in bridge_ini
    assert "[env:bridge_littlefs]" in bridge_ini
    assert "extends = stack_bridge_littlefs" in bridge_ini
    assert "[platformio]\ndefault_envs = bridge_littlefs" in bridge_ini
    assert "[env:bridge]\n" not in bridge_ini
    assert "extends = env:bridge_littlefs" not in bridge_ini
    assert "custom_lsh_stack_ota_template = {python}" in bridge_ini
    assert "bridge-ota.py --config" in bridge_ini
    assert "custom_lsh_stack_ota_devices =" in bridge_ini
    assert "[env:bridge_batch]" not in bridge_ini
    assert "custom_lsh_stack_batch_build_envs =" not in bridge_ini
    assert "bridge_release" in bridge_ini
    assert "bridge_littlefs" in bridge_ini
    assert "env.AddCustomTarget(" in targets_script
    assert "import sys" in targets_script
    assert "sys.exit(exit_code)" in targets_script
    assert "lambda" not in targets_script
    assert "lsh_build_all" not in targets_script
    assert 'title=f"LSH OTA {device_id}"' in targets_script
    assert 'title="LSH OTA All"' in targets_script

    firmware = deploy_plan["bridgeFirmware"]
    assert firmware["defaultProfile"] == "littlefs"
    assert firmware["buildEnv"] == "bridge_littlefs"
    assert firmware["profiles"]["release"]["buildEnv"] == "bridge_release"
    assert firmware["profiles"]["littlefs"]["otaTargets"]["panel"]["target"] == "lsh_ota_panel"
    assert deploy_plan["batch"]["buildAllBridgeProfiles"] == [
        "platformio",
        "run",
        "-d",
        str(tmp_path / "bridge"),
        "-e",
        "bridge_release",
        "-e",
        "bridge_littlefs",
    ]


def test_stack_config_writes_node_red_gui_setup_guide(tmp_path: Path) -> None:
    """GUI users get exact values without coupling the generator to Node-RED flows."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [node_red]
        expose_state_context = "global"
        expose_config_context = "global"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    guide = (output_dir / "node-red-setup.md").read_text(encoding="utf-8")

    assert "`exposeStateContext` | `global`" in guide
    assert "`exposeConfigContext` | `global`" in guide
    assert "LSH Base Path" in guide
    assert "Lsh Base Path" not in guide
    assert "`protocol` | `msgpack`" in guide
    assert "Paste this into the `System Config JSON` field" in guide
    assert '"devices"' in guide
    assert not (output_dir / "node-red-flow.json").exists()


def test_stack_config_derives_local_core_extra_script_and_preserves_base_scripts(
    tmp_path: Path,
) -> None:
    """Local lsh-core checkouts can append to unrelated base extra scripts."""
    core_project = tmp_path / "lsh-core-personal"
    core_project.mkdir()
    (core_project / "platformio.ini").write_text(
        """
        [common_base]
        extra_scripts =
            scripts/setup_build_actions.py

        [common_release]
        extends = common_base
        """,
        encoding="utf-8",
    )
    core_tool = tmp_path / "lsh-core" / "tools" / "generate_lsh_static_config.py"
    core_tool.parent.mkdir(parents=True)
    core_tool.write_text("", encoding="utf-8")
    (core_tool.parent / "platformio_lsh_static_config.py").write_text("", encoding="utf-8")
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"
        tool = "lsh-core/tools/generate_lsh_static_config.py"

        [platformio]
        core_project = "lsh-core-personal"
        core_base_env = "common_release"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _starter_core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")
    assert "extra_scripts =\n    ${common_release.extra_scripts}\n" in core_ini
    assert "pre:../lsh-core/tools/platformio_lsh_static_config.py" in core_ini
    assert ".pio/libdeps/core_panel/lsh-core/tools/platformio_lsh_static_config.py" not in core_ini


def test_stack_config_writes_core_profiles_for_each_device(tmp_path: Path) -> None:
    """Core profiles generate one environment per profile and selected controller."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        core_project = "core"

        [[platformio.core_profiles]]
        name = "release"
        extends = "common_release"
        default = true

        [[platformio.core_profiles]]
        name = "debug"
        extends = "common_debug"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")
    deploy_plan = json.loads((output_dir / "deploy-plan.json").read_text(encoding="utf-8"))

    assert "[env:core_panel]" in core_ini
    assert "extends = common_release" in core_ini
    assert "[env:core_panel_debug]" in core_ini
    assert "extends = common_debug" in core_ini
    assert "[env:core_lights]" in core_ini
    assert "[env:core_lights_debug]" in core_ini
    assert deploy_plan["coreProfiles"] == [
        {"name": "release", "baseEnv": "common_release", "default": True},
        {"name": "debug", "baseEnv": "common_debug", "default": False},
    ]
    assert deploy_plan["core"]["panel"]["env"] == "core_panel"
    assert deploy_plan["core"]["panel"]["profiles"]["debug"]["env"] == "core_panel_debug"
    assert deploy_plan["batch"]["buildAllCoreProfiles"] == [
        "platformio",
        "run",
        "-d",
        str(tmp_path / "core"),
        "-e",
        "core_panel",
        "-e",
        "core_panel_debug",
        "-e",
        "core_lights",
        "-e",
        "core_lights_debug",
    ]


def test_stack_config_preserves_symlinked_core_config_paths(tmp_path: Path) -> None:
    """Generated paths should match the user's project layout, not resolved symlink targets."""
    core_project = tmp_path / "core"
    core_project.mkdir()
    real_devices = tmp_path / "real" / "lsh_devices.toml"
    real_devices.parent.mkdir()
    real_devices.write_text("", encoding="utf-8")
    try:
        (core_project / "lsh_devices.toml").symlink_to(real_devices)
    except OSError:
        pytest.skip("filesystem does not support symlinks in this test environment")

    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "core/lsh_devices.toml"

        [platformio]
        core_project = "core"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _starter_core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")

    assert "custom_lsh_config = lsh_devices.toml" in core_ini
    assert str(real_devices) not in core_ini


def test_stack_config_can_prepend_system_tools_for_core_builds(tmp_path: Path) -> None:
    """The optional system-tool helper is generated only when explicitly requested."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        core_project = "core"
        core_prefer_system_tools = true
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _starter_core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    helper = output_dir / "platformio-core-system-tools.py"
    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")
    helper_text = helper.read_text(encoding="utf-8")

    assert helper.is_file()
    assert "pre:../generated/platformio-core-system-tools.py" in core_ini
    assert "pre:.pio/libdeps/core_panel/lsh-core/tools/platformio_lsh_static_config.py" in core_ini
    assert "LSH_PLATFORMIO_SYSTEM_TOOL_DIRS" in helper_text
    compile(helper_text, str(helper), "exec")


def test_stack_config_rejects_duplicate_core_profiles(tmp_path: Path) -> None:
    """Core profile names are env suffixes and must stay unique."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[platformio.core_profiles]]
        name = "debug"
        extends = "common_debug"

        [[platformio.core_profiles]]
        name = "debug"
        extends = "other_debug"
        """,
    )

    with pytest.raises(StackConfigError, match=r"platformio\.core_profiles\.name\[1\]"):
        load_stack_config(config_path)


def test_stack_config_does_not_duplicate_inherited_core_extra_script(tmp_path: Path) -> None:
    """Existing base lsh-core scripts are inherited rather than emitted twice."""
    core_project = tmp_path / "lsh-core-personal"
    core_project.mkdir()
    (core_project / "platformio.ini").write_text(
        """
        [common_base]
        extra_scripts =
            pre:../lsh-core/tools/platformio_lsh_static_config.py
            scripts/setup_build_actions.py

        [common_release]
        extends = common_base
        """,
        encoding="utf-8",
    )
    core_tool = tmp_path / "lsh-core" / "tools" / "generate_lsh_static_config.py"
    core_tool.parent.mkdir(parents=True)
    core_tool.write_text("", encoding="utf-8")
    (core_tool.parent / "platformio_lsh_static_config.py").write_text("", encoding="utf-8")
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"
        tool = "lsh-core/tools/generate_lsh_static_config.py"

        [platformio]
        core_project = "lsh-core-personal"
        core_base_env = "common_release"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _starter_core_export())

    output_dir = tmp_path / "generated"
    write_output_tree(output_dir, config, stack)

    core_ini = (output_dir / "platformio-core.ini").read_text(encoding="utf-8")
    assert "extra_scripts" not in core_ini
    assert "pre:../lsh-core/tools/platformio_lsh_static_config.py" not in core_ini


def test_stack_config_applies_bridge_define_overrides_without_duplicate_flags(
    tmp_path: Path,
) -> None:
    """Typed bridge defaults replace generated defines before raw flags append."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [bridge.defaults.defines]
        CONFIG_MAX_ACTUATORS = "8U"
        CONFIG_MSG_PACK_MQTT = false
        CONFIG_ARDCOM_SERIAL_RX_PIN = "16U"

        LSH_DEBUG = true

        [bridge.defaults.build_flags]
        append = ["-Wall"]
        """,
    )

    stack = compose_stack(load_stack_config(config_path), _core_export())
    flags = stack["bridge"]["platformioBuildFlags"]

    assert "-DCONFIG_MAX_ACTUATORS=1U" not in flags
    assert flags.count("-DCONFIG_MAX_ACTUATORS=8U") == 1
    assert "-DCONFIG_MSG_PACK_MQTT" not in flags
    assert "-DCONFIG_ARDCOM_SERIAL_RX_PIN=16U" in flags
    assert "-DLSH_DEBUG" in flags
    assert flags[-1] == "-Wall"


def test_stack_config_rejects_bridge_device_build_override_section(tmp_path: Path) -> None:
    """One wide bridge firmware has only stack-wide bridge build overrides."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [bridge.devices.panel.defines]
        LSH_DEBUG = true
        """,
    )

    with pytest.raises(StackConfigError, match="bridge contains unknown keys: devices"):
        load_stack_config(config_path)


def test_stack_config_rejects_duplicate_selected_devices(tmp_path: Path) -> None:
    """Selected core devices are a set, not an ordered multiset."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"
        selected_devices = ["panel", "panel"]
        """,
    )

    with pytest.raises(StackConfigError, match=r"core\.selected_devices\[1\] duplicates"):
        load_stack_config(config_path)


def test_stack_config_rejects_duplicate_bridge_profile_names(tmp_path: Path) -> None:
    """PlatformIO bridge profile names must map to one generated env."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[platformio.bridge_profiles]]
        name = "littlefs"
        extends = "base_littlefs"

        [[platformio.bridge_profiles]]
        name = "littlefs"
        extends = "base_debug"
        """,
    )

    with pytest.raises(
        StackConfigError, match=r"platformio\.bridge_profiles\.name\[1\] duplicates"
    ):
        load_stack_config(config_path)


def test_stack_config_rejects_homie_firmware_version_as_stack_option(
    tmp_path: Path,
) -> None:
    """The bridge firmware version is not a normal stack-level user option."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [bridge.defaults.defines]
        CONFIG_HOMIE_FIRMWARE_VERSION = '\\"custom\\"'
        """,
    )

    with pytest.raises(StackConfigError, match="follows the bridge firmware"):
        load_stack_config(config_path)


def test_lsh_stack_new_creates_personal_project_shape(tmp_path: Path) -> None:
    """A new user gets source files, disposable output dir and persistent overrides."""
    project = tmp_path / "my-lsh-installation"

    assert cli.main(["new", str(project)]) == 0

    assert (project / "README.md").is_file()
    assert (project / "lsh_stack.toml").is_file()
    assert (project / "core" / "lsh_devices.toml").is_file()
    assert (project / "core" / "platformio.ini").is_file()
    assert (project / "bridge" / "platformio.ini").is_file()
    assert (project / "generated").is_dir()
    assert (project / "overrides" / "README.md").is_file()
    assert (project / "core" / "src" / "main.cpp").is_file()
    assert (project / "bridge" / "src" / "main.cpp").is_file()
    assert (project / "core" / "scripts" / "lsh_core_bootstrap.py").is_file()
    assert (project / "generated" / "platformio-core.ini").is_file()
    assert (project / "generated" / "platformio-bridge.ini").is_file()

    bootstrap_core = (project / "generated" / "platformio-core.ini").read_text(encoding="utf-8")
    assert "extra_scripts = pre:scripts/lsh_core_bootstrap.py" in bootstrap_core
    core_platformio = (project / "core" / "platformio.ini").read_text(encoding="utf-8")
    assert "Optional stack overlay" in core_platformio
    assert "[env:core_panel]" in core_platformio
    bridge_platformio = (project / "bridge" / "platformio.ini").read_text(encoding="utf-8")
    assert "Optional stack overlay" in bridge_platformio
    assert "[lsh_bridge_standalone_contract]" in bridge_platformio
    assert "default_envs = bridge_littlefs" in bridge_platformio
    assert "[env:bridge_littlefs]" in bridge_platformio
    assert "[env:bridge]\n" not in bridge_platformio

    stack_toml = (project / "lsh_stack.toml").read_text(encoding="utf-8")
    assert 'devices = "core/lsh_devices.toml"' in stack_toml
    assert 'core_project = "core"' in stack_toml
    assert 'bridge_project = "bridge"' in stack_toml
    assert 'expose_state_context = "global"' in stack_toml
    assert 'expose_config_context = "global"' in stack_toml
    assert 'name = "littlefs_debug"' in stack_toml
    assert 'name = "littlefs_migration_debug"' in stack_toml
    assert '# source = "panel.wall_button"' in stack_toml
    assert '# actors = [{ device = "panel", actuators = ["light"] }]' in stack_toml
    assert "logic_button" not in stack_toml

    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "lsh-stack.py generate" in readme
    assert "lsh-stack.py status" in readme
    assert "Use the doctor" in readme
    assert "after setup has succeeded" in readme
    assert "uv run" not in readme
    devices_toml = (project / "core" / "lsh_devices.toml").read_text(encoding="utf-8")
    assert '# long = { network = true, fallback = "do_nothing" }' in devices_toml


def test_lsh_stack_new_reports_existing_files_on_separate_lines(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Existing starter conflicts stay readable when many files already exist."""
    project = tmp_path / "my-lsh-installation"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()

    assert cli.main(["new", str(project)]) == 2

    error = capsys.readouterr().err
    assert "starter files already exist:" in error
    assert f"- {project / 'README.md'}" in error
    assert "Pass --force to overwrite them." in error


def test_lsh_stack_new_core_creates_standalone_core_project(tmp_path: Path) -> None:
    """Core-only adopters can start without bridge, MQTT or Node-RED files."""
    project = tmp_path / "my-lsh-core"

    assert cli.main(["new-core", str(project)]) == 0

    assert (project / "README.md").is_file()
    assert (project / "lsh_devices.toml").is_file()
    assert (project / "platformio.ini").is_file()
    assert (project / "generated" / "platformio-core.ini").is_file()
    assert (project / "scripts" / "lsh_core_bootstrap.py").is_file()
    assert (project / "src" / "main.cpp").is_file()
    assert not (project / "lsh_stack.toml").exists()
    assert not (project / "bridge").exists()

    platformio_ini = (project / "platformio.ini").read_text(encoding="utf-8")
    assert "extra_configs = generated/platformio-core.ini" in platformio_ini
    assert "[env:core_panel]" in platformio_ini

    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "platformio run -e core_panel" in readme
    assert "lsh-stack setup" not in readme
    assert "point `[core].devices`" in readme


@pytest.mark.parametrize("command", ["new", "new-core"])
def test_lsh_stack_new_commands_reject_legacy_toml_targets(
    tmp_path: Path,
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Starter commands only accept project directories, not historical TOML targets."""
    target = tmp_path / "lsh_stack.toml"

    assert cli.main([command, str(target)]) == 2

    captured = capsys.readouterr()
    assert "creates a project directory" in captured.err
    assert not target.exists()


def test_lsh_stack_setup_bootstraps_core_and_generates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fresh project has one simple setup command for the normal first run."""
    project = tmp_path / "fresh-installation"
    assert cli.main(["new", str(project)]) == 0

    config = load_stack_config(project / "lsh_stack.toml")
    stack = compose_stack(config, _starter_core_export())
    compose_calls = 0

    def fake_compose(_path: Path) -> tuple[StackConfig, JsonObject]:
        nonlocal compose_calls
        compose_calls += 1
        return config, stack

    run_commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> SimpleNamespace:
        assert not check
        assert capture_output
        assert text
        run_commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "_compose", fake_compose)
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: ["platformio"])
    monkeypatch.setattr("lsh_stack_config.cli_runtime.subprocess.run", fake_run)
    monkeypatch.chdir(project)

    assert cli.main(["setup"]) == 0

    assert compose_calls == 1
    assert run_commands == [["platformio", "run", "-d", str(project / "core"), "-e", "core_panel"]]
    assert (project / "generated" / "README.generated.md").is_file()
    output = capsys.readouterr().out
    assert "lsh-core generator not found; building the core project once" in output
    assert "lsh-core bootstrap build succeeded." in output
    assert "setup complete" in output
    assert "next steps:" in output
    assert "bridge build: platformio run -d bridge -e bridge_littlefs" in output


def test_lsh_stack_status_guides_fresh_project_without_core_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Status should work before lsh-core can be executed."""
    project = tmp_path / "fresh-installation"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()

    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: None)
    monkeypatch.chdir(project)

    assert cli.main(["status"]) == 0

    output = capsys.readouterr().out
    assert "LSH stack status" in output
    assert "core config: core/lsh_devices.toml (present)" in output
    assert "PlatformIO CLI: not available in this shell" in output
    assert "lsh-core generator: not installed yet" in output
    assert "generated files: incomplete" in output
    assert "next action:" in output
    assert " setup" in output
    assert "LSH stack composer" not in output


def test_lsh_stack_status_reports_ready_project_next_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Status should stay concise after generated files and the core tool exist."""
    project = tmp_path / "ready-installation"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()

    core_tool = project / "core" / ".pio" / "libdeps" / "core_panel" / "lsh-core" / "tools"
    core_tool.mkdir(parents=True)
    (core_tool / "generate_lsh_static_config.py").write_text("", encoding="utf-8")
    (project / "generated" / "bridge-platformio-flags").mkdir(exist_ok=True)
    for name in (
        "lsh-stack-config.json",
        "system-config.json",
        "node-red-lsh-logic.json",
        "node-red-setup.md",
        "bridge-platformio-flags/bridge.txt",
        "deploy-plan.json",
        "README.generated.md",
    ):
        (project / "generated" / name).write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: ["platformio"])
    monkeypatch.chdir(project)

    assert cli.main(["status"]) == 0

    output = capsys.readouterr().out
    assert "lsh-core generator: installed at core/.pio/libdeps" in output
    assert "generated files: key files present" in output
    assert "OTA: not configured" in output
    assert "next action:" in output
    assert "build firmware" in output


def test_lsh_stack_status_prefers_guided_setup_when_generated_files_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Even with a core tool available, missing generated files should point to setup."""
    project = tmp_path / "half-ready-installation"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()

    core_tool = project / "tools" / "generate_lsh_static_config.py"
    core_tool.parent.mkdir()
    core_tool.write_text("", encoding="utf-8")
    config_path = project / "lsh_stack.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            '# tool = "../lsh-core/tools/generate_lsh_static_config.py"',
            f'tool = "{core_tool}"',
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(project)

    assert cli.main(["status"]) == 0

    output = capsys.readouterr().out
    assert "lsh-core generator: configured:" in output
    assert "generated files: incomplete" in output
    assert "next action:" in output
    next_action = output.split("next action:\n", maxsplit=1)[1]
    assert " setup" in next_action
    assert " generate" not in next_action


def test_lsh_stack_setup_without_platformio_prints_actionable_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing PlatformIO CLI should explain both CLI and VSCode recovery paths."""
    archive = tmp_path / "lsh-stack.pyz"
    archive.write_bytes(b"zipapp")
    project = tmp_path / "fresh-installation"
    monkeypatch.setattr(sys, "argv", [str(archive), "setup"])
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: None)

    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(project)

    assert cli.main(["setup"]) == 1

    error = capsys.readouterr().err
    expected_command = f"/usr/bin/python3 {archive.resolve()} setup"
    assert "PlatformIO CLI is not available" in error
    assert f"Install the PlatformIO CLI, then run: {expected_command}" in error
    assert "in VSCode with the PlatformIO extension" in error
    assert "first core build downloads lsh-core" in error


def test_lsh_stack_setup_bootstrap_failure_ends_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """PlatformIO failures should end with a clear next action, not only raw logs."""
    project = tmp_path / "fresh-installation"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()

    def fake_run(
        command: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> SimpleNamespace:
        assert command == ["platformio", "run", "-d", str(project / "core"), "-e", "core_panel"]
        assert not check
        assert capture_output
        assert text
        return SimpleNamespace(returncode=1, stdout="platformio stdout\n", stderr="tool failed\n")

    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: ["platformio"])
    monkeypatch.setattr("lsh_stack_config.cli_runtime.subprocess.run", fake_run)
    monkeypatch.chdir(project)

    assert cli.main(["setup"]) == 1

    captured = capsys.readouterr()
    assert "platformio stdout" in captured.err
    assert "tool failed" in captured.err
    assert "lsh-core bootstrap build failed" in captured.err
    assert "rerun: python" in captured.err
    assert "setup" in captured.err


def test_lsh_stack_setup_materializes_missing_personal_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Existing stack/core TOML files are enough to recreate project shells."""
    stack_project = tmp_path / "lsh-stack-personal"
    core_project = tmp_path / "lsh-core-personal"
    stack_project.mkdir()
    core_project.mkdir()
    (core_project / "lsh_devices.toml").write_text(
        """
        schema_version = 2

        [features]
        etl_profile_override_header = "lsh_etl_profile_override.h"

        [devices.panel]
        name = "panel"
        """,
        encoding="utf-8",
    )
    config_path = stack_project / "lsh_stack.toml"
    config_path.write_text(
        """
        [core]
        devices = "../lsh-core-personal/lsh_devices.toml"
        selected_devices = ["panel"]

        [platformio]
        core_project = "../lsh-core-personal"
        bridge_project = "../lsh-bridge-personal"
        """,
        encoding="utf-8",
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _starter_core_export())

    monkeypatch.setattr(cli, "_should_bootstrap_core_project", lambda _config: False)
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.chdir(stack_project)

    assert cli.main(["setup"]) == 0

    assert (core_project / "platformio.ini").is_file()
    assert (core_project / "scripts" / "lsh_core_bootstrap.py").is_file()
    assert (core_project / "src" / "main.cpp").is_file()
    assert (core_project / "include" / "lsh_etl_profile_override.h").is_file()
    assert (tmp_path / "lsh-bridge-personal" / "platformio.ini").is_file()
    assert (tmp_path / "lsh-bridge-personal" / "src" / "main.cpp").is_file()
    assert (stack_project / "overrides" / "README.md").is_file()
    output = capsys.readouterr().out
    assert "created project files:" in output


def test_lsh_stack_setup_materializes_missing_etl_header_for_existing_core_project(
    tmp_path: Path,
) -> None:
    """Changing core TOML features should still create the optional ETL header."""
    core_project = tmp_path / "core"
    core_project.mkdir()
    (core_project / "platformio.ini").write_text("[platformio]\n", encoding="utf-8")
    devices_path = core_project / "lsh_devices.toml"
    devices_path.write_text(
        """
        schema_version = 2

        [features]
        etl_profile_override_header = "lsh_etl_profile_override.h"
        """,
        encoding="utf-8",
    )
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "core/lsh_devices.toml"

        [platformio]
        core_project = "core"
        """,
    )

    written = scaffold.ensure_project_scaffolds(load_stack_config(config_path))

    header = core_project / "include" / "lsh_etl_profile_override.h"
    assert header in written
    assert header.is_file()


def test_lsh_stack_ota_builds_and_updates_selected_devices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The public stack CLI can OTA one bridge subset without shell-specific env setup."""
    (tmp_path / "bridge").mkdir()
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        bridge_project = "bridge"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_username = "homie"
        broker_password_env = "LSH_OTA_PASSWORD"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())
    output_dir = tmp_path / "generated"

    run_commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool = False,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
        text: bool = False,
    ) -> SimpleNamespace:
        assert not check
        assert not capture_output
        assert not text
        assert env is None
        run_commands.append(command)
        if command[:2] == ["platformio", "run"]:
            firmware = tmp_path / "bridge" / ".pio" / "build" / "bridge" / "firmware.bin"
            firmware.parent.mkdir(parents=True)
            firmware.write_bytes(b"firmware")
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("LSH_OTA_PASSWORD", "secret")
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: ["platformio"])
    monkeypatch.setattr("lsh_stack_config.cli_runtime.subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["ota", "panel", "lights"]) == 0

    firmware = tmp_path / "bridge" / ".pio" / "build" / "bridge" / "firmware.bin"
    assert run_commands == [
        ["platformio", "run", "-d", str(tmp_path / "bridge"), "-e", "bridge"],
        [
            sys.executable,
            str(output_dir / "bridge-ota.py"),
            "--config",
            str(output_dir / "bridge-ota.json"),
            "--device-id",
            "panel",
            str(firmware),
        ],
        [
            sys.executable,
            str(output_dir / "bridge-ota.py"),
            "--config",
            str(output_dir / "bridge-ota.json"),
            "--device-id",
            "lights",
            str(firmware),
        ],
    ]
    output = capsys.readouterr().out
    assert "platformio run" in output
    assert "bridge-ota.py" in output


def test_lsh_stack_ota_checks_password_before_building(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing OTA secrets fail before an expensive bridge firmware build starts."""
    (tmp_path / "bridge").mkdir()
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        bridge_project = "bridge"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_username = "homie"
        broker_password_env = "LSH_OTA_PASSWORD"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())
    run_commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        run_commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.delenv("LSH_OTA_PASSWORD", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: ["platformio"])
    monkeypatch.setattr("lsh_stack_config.cli_runtime.subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["ota", "panel"]) == 2
    assert run_commands == []


def test_lsh_stack_ota_dry_run_does_not_require_platformio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Users can inspect OTA commands before installing PlatformIO."""
    (tmp_path / "bridge").mkdir()
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        bridge_project = "bridge"

        [deploy.bridge.ota]
        broker_host = "mqtt.lan"
        broker_username = "homie"
        broker_password_env = "LSH_OTA_PASSWORD"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: None)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["ota", "panel", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "running: platformio run" in output
    assert "bridge-ota.py" in output
    assert str(tmp_path) not in output


def test_lsh_stack_new_supports_documented_first_use_without_sibling_repos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fresh project can be parsed before any generated file regeneration."""
    platformio = shutil.which("platformio")
    if platformio is None:
        pytest.skip("PlatformIO is required for the first-use bootstrap smoke test.")

    project = tmp_path / "fresh-installation"
    assert cli.main(["new", str(project)]) == 0

    core_config = subprocess.run(  # noqa: S603 - executable comes from shutil.which in test env.
        [platformio, "project", "config"],
        cwd=project / "core",
        check=False,
        capture_output=True,
        text=True,
    )
    assert core_config.returncode == 0, core_config.stderr + core_config.stdout
    assert "env:core_panel" in core_config.stdout
    assert "ProjectEnvsNotAvailableError" not in core_config.stderr

    bridge_config = subprocess.run(  # noqa: S603 - executable comes from shutil.which in test env.
        [platformio, "project", "config"],
        cwd=project / "bridge",
        check=False,
        capture_output=True,
        text=True,
    )
    assert bridge_config.returncode == 0, bridge_config.stderr + bridge_config.stdout
    assert "env:bridge_littlefs" in bridge_config.stdout
    assert "env:bridge\n" not in bridge_config.stdout
    assert "ProjectEnvsNotAvailableError" not in bridge_config.stderr

    core_tool = project / "core" / ".pio" / "libdeps" / "core_panel" / "lsh-core" / "tools"
    core_tool.mkdir(parents=True)
    (core_tool / "generate_lsh_static_config.py").write_text(
        "import json\nprint(" + repr(json.dumps(_starter_core_export())) + ")\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(project)
    assert cli.main(["generate"]) == 0

    generated_core = (project / "generated" / "platformio-core.ini").read_text(encoding="utf-8")
    assert "extra_scripts = pre:.pio/libdeps/core_panel/lsh-core/tools" in generated_core
    assert "custom_lsh_config = lsh_devices.toml" in generated_core
    generated_bridge = (project / "generated" / "platformio-bridge.ini").read_text(encoding="utf-8")
    assert "[env:bridge_littlefs_debug]" in generated_bridge
    assert "[env:bridge_littlefs_migration_debug]" in generated_bridge
    generated_readme = (project / "generated" / "README.generated.md").read_text(encoding="utf-8")
    assert "OTA custom targets are not generated until" in generated_readme
    assert "LSH OTA <device>" not in generated_readme
    assert "bridge_batch" not in generated_readme


def test_lsh_stack_explain_reports_one_device(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The explain command shows the generated firmware and runtime contract."""
    config_path = _write_stack_config(tmp_path, "[core]\ndevices = 'lsh_devices.toml'\n")
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))

    assert cli.main(["explain", "panel", "--config", str(config_path)]) == 0
    capsys.readouterr()

    monkeypatch.chdir(tmp_path)
    assert cli.main(["explain", "panel"]) == 0

    output = capsys.readouterr().out
    assert "controller TOML: lsh_devices.toml" in output
    assert "controller environment: core_panel" in output
    assert "bridge firmware environment: bridge" in output
    assert "bridge OTA target: not configured" in output
    assert "coordinator systemConfig entry" in output


def test_lsh_stack_doctor_does_not_warn_for_separate_platformio_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A stack-only repo should not be told to create a local PlatformIO project."""
    (tmp_path / "lsh-core-personal").mkdir()
    (tmp_path / "lsh-core-personal" / "platformio.ini").write_text(
        """
        [platformio]
        extra_configs = ../generated/platformio-core.ini
        """,
        encoding="utf-8",
    )
    (tmp_path / "lsh-bridge-personal").mkdir()
    (tmp_path / "lsh-bridge-personal" / "platformio.ini").write_text(
        """
        [platformio]
        extra_configs = ../generated/platformio-bridge.ini
        """,
        encoding="utf-8",
    )
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "platformio-core.ini").write_text("", encoding="utf-8")
    (tmp_path / "generated" / "platformio-bridge.ini").write_text("", encoding="utf-8")
    (tmp_path / "overrides").mkdir()

    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [platformio]
        core_project = "lsh-core-personal"
        bridge_project = "lsh-bridge-personal"
        """,
    )
    config = load_stack_config(config_path)
    stack = compose_stack(config, _core_export())

    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.chdir(tmp_path)

    assert cli.main(["doctor"]) == 0

    output = capsys.readouterr().out
    assert "warnings:" not in output
    assert "No stack configuration problems found." in output
    assert "LSH stack composer" not in output


def test_lsh_stack_doctor_warns_when_platformio_does_not_include_generated_fragment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor catches scaffold drift without mutating user-owned PlatformIO files."""
    project = tmp_path / "install"
    assert cli.main(["new", str(project)]) == 0
    (project / "core" / "platformio.ini").write_text("[platformio]\n", encoding="utf-8")

    config = load_stack_config(project / "lsh_stack.toml")
    stack = compose_stack(config, _starter_core_export())
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))

    assert cli.main(["doctor", "--config", str(project / "lsh_stack.toml")]) == 0

    output = capsys.readouterr().out
    assert "warnings:" in output
    assert "core platformio.ini should include `../generated/platformio-core.ini`" in output

    assert cli.main(["doctor", "--strict", "--config", str(project / "lsh_stack.toml")]) == 1


def test_lsh_stack_doctor_uses_project_relative_missing_file_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor output should stay readable from the project root."""
    project = tmp_path / "install"
    assert cli.main(["new", str(project)]) == 0
    capsys.readouterr()
    (project / "generated" / "platformio-core.ini").unlink()
    (project / "generated" / "platformio-bridge.ini").unlink()

    config = load_stack_config(project / "lsh_stack.toml")
    stack = compose_stack(config, _starter_core_export())
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.chdir(project)

    assert cli.main(["doctor"]) == 0

    output = capsys.readouterr().out
    assert "missing generated/platformio-core.ini" in output
    assert "missing generated/platformio-bridge.ini" in output
    assert str(tmp_path) not in output


def test_stack_config_rejects_clicks_not_declared_as_network_clicks(tmp_path: Path) -> None:
    """The stack cannot invent coordinator actions for local-only firmware clicks."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.local_only"
        actors = [{ device = "lights", actuators = "all" }]
        """,
    )

    with pytest.raises(StackConfigError, match="not declared as network=true"):
        compose_stack(load_stack_config(config_path), _core_export())


def test_stack_config_rejects_unknown_actuator_names(tmp_path: Path) -> None:
    """Actor targets are checked against the controller contract before output."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [{ device = "lights", actuators = ["missing"] }]
        """,
    )

    with pytest.raises(StackConfigError, match="unknown actuator 'missing'"):
        compose_stack(load_stack_config(config_path), _core_export())


def test_stack_config_rejects_duplicate_network_click_entries(tmp_path: Path) -> None:
    """Duplicate click bindings fail at the TOML boundary instead of overriding later."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [{ device = "lights", actuators = ["ceiling"] }]

        [[network_clicks]]
        source = "panel.logic_button"
        type = "long"
        other_actors = ["zigbee_table_lamp"]
        """,
    )

    with pytest.raises(StackConfigError, match=r"network_clicks\[1\] duplicates"):
        load_stack_config(config_path)


def test_stack_config_rejects_duplicate_network_click_targets(tmp_path: Path) -> None:
    """The stack config must not silently deduplicate actor or external targets."""
    duplicate_actor_config = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [
          { device = "lights", actuators = ["ceiling"] },
          { device = "lights", actuators = "all" },
        ]
        """,
    )
    with pytest.raises(
        StackConfigError, match=r"network_clicks\[0\]\.actors\.device\[1\] duplicates"
    ):
        load_stack_config(duplicate_actor_config)

    duplicate_other_config = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        other_actors = ["zigbee_table_lamp", "zigbee_table_lamp"]
        """,
    )
    with pytest.raises(
        StackConfigError, match=r"network_clicks\[0\]\.other_actors\[1\] duplicates"
    ):
        load_stack_config(duplicate_other_config)

    duplicate_actuator_config = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [{ device = "lights", actuators = ["ceiling", "ceiling"] }]
        """,
    )
    with pytest.raises(
        StackConfigError, match=r"network_clicks\[0\]\.actors\.actuators\[1\] duplicates"
    ):
        load_stack_config(duplicate_actuator_config)


def test_stack_config_rejects_duplicate_resolved_actor_actuator_ids(tmp_path: Path) -> None:
    """A name and numeric id pointing to the same actuator are still a duplicate target."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [[network_clicks]]
        source = "panel.logic_button"
        actors = [{ device = "lights", actuators = ["ceiling", 3] }]
        """,
    )

    with pytest.raises(StackConfigError, match="duplicate actuator target 3 on device lights"):
        compose_stack(load_stack_config(config_path), _core_export())


def test_stack_config_reserves_bridgeless_mode_until_core_support_exists(tmp_path: Path) -> None:
    """Future transport names are explicit but cannot silently generate wrong output."""
    config_path = _write_stack_config(
        tmp_path,
        """
        [core]
        devices = "lsh_devices.toml"

        [transport]
        mode = "onboard_ethernet"
        """,
    )

    with pytest.raises(StackConfigError, match="reserved for future bridgeless firmware"):
        compose_stack(load_stack_config(config_path), _core_export())


def _write_stack_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "lsh_stack.toml"
    path.write_text(content, encoding="utf-8")
    return path


def _device_entry(stack: dict[str, object], name: str) -> dict[str, object]:
    devices = stack["coordinator"]["systemConfig"]["devices"]
    return next(device for device in devices if device["name"] == name)


def _core_export() -> dict[str, object]:
    return {
        "schema": "lsh-stack-config/v1",
        "source": "lsh_devices.toml",
        "lshBasePath": "LSH/",
        "homieBasePath": "homie/5/",
        "serviceTopic": "LSH/Node-RED/SRV",
        "protocol": "msgpack",
        "qosPolicy": {
            "coordinatorSubscriptions": {
                "bridge": 2,
                "conf": 2,
                "events": 2,
                "homieState": 1,
                "state": 2,
            }
        },
        "bridge": {
            "devices": {
                "panel": {
                    "deviceName": "panel",
                    "platformioBuildFlags": [
                        "-DCONFIG_MAX_ACTUATORS=1U",
                        '-DCONFIG_MQTT_TOPIC_BASE=\\"LSH\\"',
                        '-DCONFIG_MQTT_TOPIC_SERVICE=\\"LSH/Node-RED/SRV\\"',
                        "-DCONFIG_MSG_PACK_ARDUINO",
                        "-DCONFIG_MSG_PACK_MQTT",
                    ],
                    "topics": {},
                },
                "lights": {
                    "deviceName": "lights",
                    "platformioBuildFlags": [],
                    "topics": {},
                },
            }
        },
        "controllers": {
            "panel": {
                "deviceName": "panel",
                "actuators": [],
                "buttons": [{"name": "logic_button", "id": 7}],
                "indicators": [],
            },
            "lights": {
                "deviceName": "lights",
                "actuators": [{"name": "ceiling", "id": 3}],
                "buttons": [],
                "indicators": [],
            },
        },
        "coordinator": {
            "options": {
                "lshBasePath": "LSH/",
                "homieBasePath": "homie/5/",
                "serviceTopic": "LSH/Node-RED/SRV",
                "protocol": "msgpack",
                "subscriptionQos": {
                    "bridge": 2,
                    "conf": 2,
                    "events": 2,
                    "homieState": 1,
                    "state": 2,
                },
            },
            "systemConfig": {"devices": [{"name": "panel"}, {"name": "lights"}]},
            "subscriptions": {},
            "unmappedNetworkClicks": [
                {
                    "device": "panel",
                    "buttonId": 7,
                    "button": "logic_button",
                    "clickType": "long",
                }
            ],
        },
        "nodeRed": {"lshLogic": {"protocol": "msgpack", "systemConfigJson": "{}"}},
        "footprint": {},
    }


def _starter_core_export() -> dict[str, object]:
    return {
        "schema": "lsh-stack-config/v1",
        "source": "lsh_devices.toml",
        "lshBasePath": "LSH/",
        "homieBasePath": "homie/5/",
        "serviceTopic": "LSH/Node-RED/SRV",
        "protocol": "msgpack",
        "bridge": {
            "devices": {
                "panel": {
                    "deviceName": "panel",
                    "platformioBuildFlags": [
                        "-DCONFIG_MAX_ACTUATORS=1U",
                        "-DCONFIG_MAX_BUTTONS=1U",
                        "-DCONFIG_MAX_NAME_LENGTH=5U",
                        "-DCONFIG_MSG_PACK_ARDUINO",
                    ],
                    "topics": {},
                }
            }
        },
        "controllers": {
            "panel": {
                "deviceName": "panel",
                "actuators": [{"name": "light", "id": 1}],
                "buttons": [{"name": "wall_button", "id": 1}],
                "indicators": [],
            }
        },
        "coordinator": {
            "options": {
                "lshBasePath": "LSH/",
                "homieBasePath": "homie/5/",
                "serviceTopic": "LSH/Node-RED/SRV",
                "protocol": "msgpack",
                "subscriptionQos": {
                    "bridge": 2,
                    "conf": 2,
                    "events": 2,
                    "homieState": 1,
                    "state": 2,
                },
            },
            "systemConfig": {"devices": [{"name": "panel"}]},
            "subscriptions": {},
            "unmappedNetworkClicks": [],
        },
        "nodeRed": {"lshLogic": {"protocol": "msgpack", "systemConfigJson": "{}"}},
        "footprint": {},
    }
