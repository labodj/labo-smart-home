"""First-run and operational regression checks; no real device/broker is contacted."""

from __future__ import annotations

import json
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from lsh_stack_config import cli, cli_runtime, operations, scaffold, status, template_updates
from lsh_stack_config.composer import compose_stack
from lsh_stack_config.deploy import render_bridge_ota_config
from lsh_stack_config.errors import StackConfigError
from lsh_stack_config.models import BridgeOtaSettings, JsonObject, StackConfig
from lsh_stack_config.operations import select_bridge_profile
from lsh_stack_config.parser import load_stack_config
from lsh_stack_config.paths import stack_config_path
from lsh_stack_config.render import generated_file_problems, render_node_red_flow, write_output_tree
from test_stack_config import _core_export


@pytest.fixture
def installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[StackConfig, JsonObject]:
    """Create an isolated stack with a mocked controller contract, not live hardware."""
    root = tmp_path / "home"
    scaffold.write_starter(root, force=False)
    config = load_stack_config(root / "lsh_stack.toml")
    config = replace(
        config,
        deploy=replace(
            config.deploy,
            bridge=replace(config.deploy.bridge, ota=BridgeOtaSettings(broker_host="localhost")),
        ),
    )
    stack = compose_stack(config, _core_export())
    monkeypatch.setattr(cli, "_compose", lambda _path: (config, stack))
    monkeypatch.chdir(root)
    return config, stack


def test_root_discovery_and_explicit_config(
    installation: tuple[StackConfig, JsonObject], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subdirectories select the nearest stack; explicit paths always win."""
    config, _ = installation
    monkeypatch.chdir(config.path.parent / "core/src")
    assert stack_config_path(None) == config.path
    assert stack_config_path(Path("custom.toml")) == Path.cwd() / "custom.toml"
    assert cli.main(["core", "list"]) == 0
    nested = Path.cwd() / "lsh_stack.toml"
    nested.touch()
    assert stack_config_path(None) == nested


@pytest.mark.parametrize("arguments", [[], ["panel", "--all"], ["missing"], ["--all", "missing"]])
@pytest.mark.usefixtures("installation")
def test_ota_requires_valid_explicit_targets(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    """Invalid selections must fail before building or contacting a device."""
    monkeypatch.setattr(
        cli, "run_or_print", lambda *_a, **_kw: pytest.fail("must not build/upload")
    )
    assert cli.main(["ota", *arguments]) == 2


def test_ota_preview_and_partial_failure_summary(
    installation: tuple[StackConfig, JsonObject],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed target is reported while subsequent targets can still finish."""
    config, _ = installation
    firmware = config.path.parent / "bridge/.pio/build/bridge_littlefs/firmware.bin"
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b"test firmware")
    calls = []

    def run(command: list[str], **_kwargs: object) -> int:
        calls.append(command)
        return 5 if "lights" in command else 0

    monkeypatch.setattr(cli, "run_or_print", run)
    monkeypatch.setattr(cli, "required_platformio_invocation", lambda **_kw: ["platformio"])
    assert cli.main(["ota", "--all"]) == 1
    output = capsys.readouterr().out
    assert "OTA targets: panel, lights; profile: littlefs" in output
    assert "panel: OK" in output
    assert "lights: FAILED (5)" in output
    assert len(calls) == 3


def test_ota_dry_run_debug_keeps_family_and_does_not_write(
    installation: tuple[StackConfig, JsonObject], capsys: pytest.CaptureFixture[str]
) -> None:
    """A debug preview preserves LittleFS and leaves generated files unchanged."""
    config, _ = installation
    before = {
        p: p.read_bytes() for p in (config.path.parent / "generated").rglob("*") if p.is_file()
    }
    assert cli.main(["ota", "panel", "--debug", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "profile: littlefs_debug (bridge_littlefs_debug)" in output
    assert "panel: planned" in output
    assert before == {p: p.read_bytes() for p in before}
    assert not (config.path.parent / "generated/bridge-ota.json").exists()


def test_debug_rejects_ambiguous_custom_and_migration_profiles(
    installation: tuple[StackConfig, JsonObject],
) -> None:
    """Automatic debug selection is limited to unambiguous standard pairs."""
    config, _ = installation
    assert select_bridge_profile(config, "release", debug=True).name == "debug"
    assert select_bridge_profile(config, "littlefs_debug", debug=True).name == "littlefs_debug"
    with pytest.raises(StackConfigError, match="explicitly"):
        select_bridge_profile(config, "littlefs_migration", debug=True)
    candidate = select_bridge_profile(config, "littlefs_debug", debug=False)
    ambiguous = replace(
        config,
        platformio=replace(
            config.platformio,
            bridge_profiles=(
                *config.platformio.bridge_profiles,
                replace(candidate, name="another"),
            ),
        ),
    )
    with pytest.raises(StackConfigError, match="safely"):
        select_bridge_profile(ambiguous, None, debug=True)
    with pytest.raises(StackConfigError, match="unknown"):
        select_bridge_profile(config, "nope", debug=False)


@pytest.mark.parametrize(
    "command",
    [
        ["build", "--debug"],
        ["clean"],
        ["upload", "panel", "--port", "/dev/ttyUSB0"],
        ["monitor", "panel", "--port", "/dev/ttyUSB0"],
    ],
)
@pytest.mark.usefixtures("installation")
def test_bridge_dry_run(
    capsys: pytest.CaptureFixture[str],
    command: list[str],
) -> None:
    """Bridge commands resolve ordinary PlatformIO operations without executing them."""
    assert cli.main(["bridge", *command, "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "platformio" in output
    assert "bridge_littlefs" in output
    if command[0] == "monitor":
        assert "device monitor" in output
    if command[0] == "upload":
        assert "--upload-port /dev/ttyUSB0" in output


@pytest.mark.parametrize(
    "command",
    [
        ["upload", "--all", "--port", "/dev/ttyUSB0"],
        ["upload", "panel"],
        ["monitor", "panel", "lights", "--port", "/dev/ttyUSB0"],
        ["build", "--port", "bad"],
        ["diagnose", "panel", "--duration", "0"],
        ["diagnose", "--all", "--debug"],
        ["list", "panel"],
        ["build", "--duration", "10"],
    ],
)
@pytest.mark.usefixtures("installation")
def test_bridge_rejects_unsafe_or_irrelevant_arguments(command: list[str]) -> None:
    """USB target/port selection and action-specific options are enforced."""
    assert cli.main(["bridge", *command, "--dry-run"]) == 2


def test_passive_diagnostics_reuses_installed_tool(
    installation: tuple[StackConfig, JsonObject], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The launcher delegates to the shared script without active-test flags."""
    config, _ = installation
    tool = (
        config.path.parent
        / "bridge/.pio/libdeps/bridge_littlefs/lsh-bridge/tools/mqtt_diagnostics.py"
    )
    tool.parent.mkdir(parents=True)
    tool.touch()
    calls = []
    monkeypatch.setattr(
        operations, "run_or_print", lambda command, **_kw: calls.append(command) or 0
    )
    assert cli.main(["bridge", "diagnose", "panel", "--duration", "4", "--dry-run"]) == 0
    assert str(tool) in calls[0]
    assert calls[0][-2:] == ["--duration", "4"]
    assert "--burst" not in calls[0]


@pytest.mark.parametrize(
    "name",
    [
        "platformio-core-targets.py",
        "platformio-bridge-targets.py",
        "bridge-ota.py",
        "bridge-ota.json",
        "node-red-flow.json",
    ],
)
def test_doctor_detects_missing_helpers(
    installation: tuple[StackConfig, JsonObject], capsys: pytest.CaptureFixture[str], name: str
) -> None:
    """Every generated executable, OTA config and import flow is required when enabled."""
    config, stack = installation
    directory = config.path.parent / "generated"
    write_output_tree(directory, config, stack)
    assert cli.main(["doctor", "--strict"]) == 0
    (directory / name).unlink()
    assert cli.main(["doctor"]) == 1
    assert name in capsys.readouterr().out


def test_freshness_checks_contents_not_just_existence(
    installation: tuple[StackConfig, JsonObject], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupted helper is stale even when configuration validation succeeds."""
    config, stack = installation
    directory = config.path.parent / "generated"
    write_output_tree(directory, config, stack)
    unchanged = (directory / "system-config.json").stat().st_mtime_ns
    write_output_tree(directory, config, stack)
    assert (directory / "system-config.json").stat().st_mtime_ns == unchanged
    (directory / "platformio-core-targets.py").write_text("# corrupted\n", encoding="utf-8")
    assert any("outdated" in p for p in generated_file_problems(directory, config, stack))
    tool = config.path.parent / "generator.py"
    tool.touch()
    config = replace(config, core=replace(config.core, tool=tool))
    monkeypatch.setattr(status, "load_core_export", lambda _c: _core_export())
    report = status.render_stack_status(status.inspect_stack_status(config, directory))
    assert "configuration: valid" in report
    assert "generated content: outdated/incomplete" in report
    assert "firmware: not verified" in report
    assert "run " in report
    assert " generate" in report


@pytest.mark.parametrize("codec", ["json", "msgpack"])
def test_node_red_flow_is_disabled_linked_and_secret_free(
    installation: tuple[StackConfig, JsonObject], codec: str
) -> None:
    """All wires resolve and both codecs use a raw-buffer dynamic MQTT subscription."""
    config, _ = installation
    config = replace(config, mqtt=replace(config.mqtt, codec=codec))
    stack = compose_stack(config, _core_export())
    flow = render_node_red_flow(stack)
    by_id = {node["id"]: node for node in flow}
    assert len(by_id) == len(flow)
    assert by_id["lsh-stack-flow"]["disabled"] is True
    logic = by_id["lsh-stack-logic"]
    assert logic["protocol"] == codec
    assert logic["wires"][3] == ["lsh-stack-in"]
    assert by_id["lsh-stack-in"]["inputs"] == 1
    assert by_id["lsh-stack-in"]["datatype"] == "buffer"
    assert by_id["lsh-stack-in"]["broker"] == by_id["lsh-stack-out"]["broker"] == ""
    assert json.loads(logic["systemConfigJson"]) == stack["coordinator"]["systemConfig"]
    for node in flow:
        for output in node.get("wires", []):
            assert all(target in by_id for target in output)
    assert "password" not in json.dumps(flow)


def test_template_update_backup_and_custom_preservation(
    installation: tuple[StackConfig, JsonObject], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only original files update; backups are exact and reruns are idempotent."""
    config, _ = installation
    root = config.path.parent
    core = root / "core/src/main.cpp"
    bridge = root / "bridge/src/main.cpp"
    before = core.read_text(encoding="utf-8")
    bridge.write_text("// customized\n", encoding="utf-8")
    monkeypatch.setattr(template_updates, "CORE_MAIN_TEMPLATE", before + "// updated template\n")
    assert template_updates.update_templates(config, action="check") == 1
    assert core.read_text(encoding="utf-8") == before
    assert template_updates.update_templates(config, action="apply") == 1
    assert core.read_text(encoding="utf-8") == before + "// updated template\n"
    assert bridge.read_text(encoding="utf-8") == "// customized\n"
    backups = list((root / ".lsh-stack/backups").glob("*/core/src/main.cpp"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == before
    assert template_updates.update_templates(config, action="apply") == 1
    assert list((root / ".lsh-stack/backups").glob("*/core/src/main.cpp")) == backups


def test_template_update_unknown_original_and_symlink_are_not_overwritten(
    installation: tuple[StackConfig, JsonObject], tmp_path: Path
) -> None:
    """Unrecorded custom files and paths escaping through symlinks are protected."""
    config, _ = installation
    (config.path.parent / template_updates.MANIFEST).unlink()
    target = config.path.parent / "core/src/main.cpp"
    target.write_text("// unknown\n", encoding="utf-8")
    assert template_updates.update_templates(config, action="apply") == 1
    assert target.read_text(encoding="utf-8") == "// unknown\n"
    external = tmp_path / "outside.cpp"
    external.write_text("// do not touch\n", encoding="utf-8")
    target.unlink()
    target.symlink_to(external)
    with pytest.raises(StackConfigError, match="symlink"):
        template_updates.update_templates(config, action="apply")
    assert external.read_text(encoding="utf-8") == "// do not touch\n"


def test_interactive_creation_validates_input_without_guessing_wiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid answers are retried and the resulting TOMLs contain no assumed pins."""
    answers = iter(
        [
            "y",
            "a,a",
            "bad name",
            "salotto,cucina",
            "bad",
            "msgpack",
            "mqtt.test",
            "0",
            "1883",
            "homie",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    root = tmp_path / "home"
    assert cli.main(["new", str(root), "--interactive"]) == 0
    config = load_stack_config(root / "lsh_stack.toml")
    devices = tomllib.loads(config.core.devices.read_text(encoding="utf-8"))
    assert list(devices["devices"]) == ["salotto", "cucina"]
    assert all("actuators" not in device for device in devices["devices"].values())
    assert config.mqtt.codec == "msgpack"
    assert config.deploy.bridge.ota.broker_password is None
    assert config.deploy.bridge.ota.broker_password_env == "LSH_OTA_PASSWORD"  # noqa: S105 - env name


def test_cancelled_wizard_creates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rejecting the supported hardware must not leave a partial project."""
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert cli.main(["new", str(tmp_path / "home"), "--interactive"]) == 2
    assert not (tmp_path / "home").exists()


def test_vscode_platformio_discovery_without_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Find Core in VSCode's penv even when neither executable is on PATH."""
    executable = tmp_path / "pio/penv/bin/platformio"
    executable.parent.mkdir(parents=True)
    executable.touch(mode=0o755)
    monkeypatch.setenv("PLATFORMIO_CORE_DIR", str(tmp_path / "pio"))
    monkeypatch.setattr(cli_runtime.shutil, "which", lambda _name: None)
    assert cli_runtime.platformio_invocation() == [str(executable)]


def test_preflight_failure_does_not_remove_generated_files(
    installation: tuple[StackConfig, JsonObject], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prerequisites are checked before touching existing generated fragments."""
    config, _ = installation
    fragment = config.path.parent / "generated/platformio-core.ini"
    before = fragment.read_bytes()
    monkeypatch.setattr(cli_runtime, "platformio_invocation", lambda: None)
    assert cli.main(["setup"]) == 1
    assert fragment.read_bytes() == before


def test_core_default_environment_tracks_configured_devices(
    installation: tuple[StackConfig, JsonObject],
) -> None:
    """IDE/default Upload selects one real device; all other build environments still exist."""
    config, stack = installation
    directory = config.path.parent / "generated"
    write_output_tree(directory, config, stack)
    content = (directory / "platformio-core.ini").read_text(encoding="utf-8")
    assert "default_envs = core_panel\n" in content
    assert "[env:core_lights]" in content


def test_tls_paths_do_not_depend_on_current_directory(
    installation: tuple[StackConfig, JsonObject],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OTA and shared diagnostics receive the same absolute TLS paths from any subdirectory."""
    config, _ = installation
    ota = replace(
        config.deploy.bridge.ota,
        broker_tls_cacert="certs/ca.pem",
        broker_tls_keyfile="/etc/lsh/example-key.pem",
    )
    config = replace(
        config, deploy=replace(config.deploy, bridge=replace(config.deploy.bridge, ota=ota))
    )
    expected = render_bridge_ota_config(config)
    monkeypatch.chdir(config.path.parent / "core")
    assert render_bridge_ota_config(config) == expected
    assert expected["broker"]["tls_cacert"] == str(config.path.parent / "certs/ca.pem")
    assert expected["broker"]["tls_keyfile"] == "/etc/lsh/example-key.pem"


def test_new_refuses_symlinked_metadata_before_writing(tmp_path: Path) -> None:
    """Existing metadata redirects must not cause a partially created or external project."""
    project, external = tmp_path / "home", tmp_path / "external"
    project.mkdir()
    external.mkdir()
    (project / ".lsh-stack").symlink_to(external, target_is_directory=True)
    assert cli.main(["new", str(project)]) == 2
    assert not (project / "lsh_stack.toml").exists()
    assert not list(external.iterdir())


@pytest.mark.usefixtures("installation")
@pytest.mark.parametrize(
    "arguments",
    [
        ["ota", "--list-devices", "--all"],
        ["ota", "--list-devices", "panel"],
        ["core", "list", "--debug"],
        ["bridge", "list", "--duration", "4"],
    ],
)
def test_listing_rejects_ignored_options(arguments: list[str]) -> None:
    """Listing must not silently swallow options that look like device operations."""
    assert cli.main(arguments) == 2


def test_read_only_template_check_leaves_legacy_metadata_absent(
    installation: tuple[StackConfig, JsonObject],
) -> None:
    """A check never adopts files or creates state for an older installation."""
    config, _ = installation
    manifest = config.path.parent / template_updates.MANIFEST
    manifest.unlink()
    assert template_updates.update_templates(config, action="check") == 0
    assert not manifest.exists()
    assert template_updates.update_templates(config, action="apply") == 0
    assert manifest.exists()


def test_wizard_unicode_strings_and_long_invalid_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interactive text is valid TOML even outside the BMP; oversized ports are retried."""
    username = "user\U0001f680"
    answers = iter(["", "", "", "mqtt.test", "9" * 5000, "1883", username])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    project = tmp_path / "home"
    assert cli.main(["new", str(project), "--interactive"]) == 0
    assert (
        load_stack_config(project / "lsh_stack.toml").deploy.bridge.ota.broker_username == username
    )
