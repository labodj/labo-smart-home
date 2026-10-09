"""Operational CLI safety and generated PlatformIO tasks, without real hardware."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lsh_stack_config import cli, cli_runtime, scaffold
from lsh_stack_config.development import switch_dependencies
from lsh_stack_config.errors import StackConfigError
from lsh_stack_config.parser import load_stack_config
from lsh_stack_config.platformio_core_targets_script import render_platformio_core_targets_script


def _local_repositories(root: Path) -> Path:
    for name in ("lsh-core", "lsh-bridge", "homie-esp8266"):
        path = root / name
        path.mkdir(parents=True)
        (path / "library.json").touch()
    tool = root / "lsh-core" / "tools" / "generate_lsh_static_config.py"
    tool.parent.mkdir()
    tool.touch()
    return tool


def test_dev_cli_rebuilds_both_modes_and_restores_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A switch delegates to full setup; release ignores stale local-tool environment pins."""
    installation = tmp_path / "home"
    scaffold.write_starter(installation, force=False)
    config = installation / "lsh_stack.toml"
    tool = _local_repositories(tmp_path / "repos")
    seen: list[str | None] = []

    def setup(_args: object) -> int:
        seen.append(os.environ.get("LSH_CORE_TOOL"))
        return 9

    monkeypatch.setattr(cli, "_setup", setup)
    monkeypatch.setenv("LSH_CORE_TOOL", "original")
    assert (
        cli.main(
            [
                "dev",
                "local",
                "--config",
                str(config),
                "--repositories-root",
                str(tmp_path / "repos"),
            ]
        )
        == 9
    )
    assert cli.main(["dev", "release", "--config", str(config)]) == 9
    assert seen == [str(tool), None]
    assert os.environ["LSH_CORE_TOOL"] == "original"
    assert (
        cli.main(
            [
                "dev",
                "local",
                "--no-build",
                "--config",
                str(config),
                "--repositories-root",
                str(tmp_path / "repos"),
            ]
        )
        == 0
    )
    assert len(seen) == 2


def test_switch_rolls_back_both_files_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed second write leaves neither project in an unintended dependency mode."""
    installation = tmp_path / "home"
    scaffold.write_starter(installation, force=False)
    _local_repositories(tmp_path / "repos")
    config = load_stack_config(installation / "lsh_stack.toml")
    original_write = Path.write_text
    blocked = installation / "bridge" / "platformio.local.ini"

    def write(path: Path, text: str, **kwargs: object) -> int:
        if path == blocked:
            raise OSError("simulated full disk")
        return original_write(path, text, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(StackConfigError, match="simulated full disk"):
        switch_dependencies(config, tmp_path / "repos", local=True)
    assert not (installation / "core" / "platformio.local.ini").exists()
    assert not blocked.exists()


@pytest.mark.parametrize("problem", ["invalid-ini", "missing-library", "invalid-override"])
def test_dev_rejects_invalid_input_without_switching(tmp_path: Path, problem: str) -> None:
    """Broken or incomplete custom configs fail before either project's overrides change."""
    installation = tmp_path / "home"
    scaffold.write_starter(installation, force=False)
    _local_repositories(tmp_path / "repos")
    config = load_stack_config(installation / "lsh_stack.toml")
    ini = installation / "bridge" / "platformio.ini"
    override = ini.with_name("platformio.local.ini")
    if problem == "invalid-ini":
        ini.write_text("missing section header\n")
    elif problem == "missing-library":
        ini.write_text(
            "\n".join(line for line in ini.read_text().splitlines() if "homie-v5" not in line)
        )
    else:
        override.write_bytes(b"\xff")
    with pytest.raises(StackConfigError, match=r"cannot read|declare release lib_deps"):
        switch_dependencies(config, tmp_path / "repos", local=True)
    assert not (installation / "core" / "platformio.local.ini").exists()
    if problem == "invalid-override":
        assert override.read_bytes() == b"\xff"
    else:
        assert not override.exists()


def test_core_batch_tasks_use_same_profile_without_shell_or_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the generated SCons actions, verifying actual argv and failure propagation."""
    tasks = {}
    names = "core_panel_debug core_lights_debug"
    environment = SimpleNamespace(
        GetProjectOption=lambda *_args: names,
        subst=lambda _arg: str(tmp_path / "project with spaces"),
        AddCustomTarget=lambda **kwargs: tasks.update({kwargs["name"]: kwargs}),
    )
    namespace = {"env": environment, "Import": lambda _name: None}
    exec(render_platformio_core_targets_script(), namespace)  # noqa: S102 - generated source under test.
    calls = []

    def call(argv: list[str], **kwargs: object) -> int:
        calls.append((argv, kwargs))
        return 8

    monkeypatch.setattr(subprocess, "call", call)
    for name in ("lsh_core_build_all", "lsh_core_clean_all"):
        assert tasks[name]["actions"]([name], [], environment) == 8
    base = [
        sys.executable,
        "-m",
        "platformio",
        "run",
        "-e",
        "core_panel_debug",
        "-e",
        "core_lights_debug",
    ]
    assert calls == [
        (base, {"cwd": str(tmp_path / "project with spaces")}),
        ([*base, "-t", "clean"], {"cwd": str(tmp_path / "project with spaces")}),
    ]
    names = ""
    with pytest.raises(RuntimeError, match="Missing controller environments"):
        tasks["lsh_core_build_all"]["actions"](["lsh_core_build_all"], [], environment)
    assert len(calls) == 2


def test_platformio_short_alias_and_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pio alias works; preview never starts a subprocess or requires an installation."""
    monkeypatch.setattr(
        cli_runtime.shutil, "which", lambda name: "/bin/pio" if name == "pio" else None
    )
    assert cli_runtime.platformio_invocation() == ["/bin/pio"]
    monkeypatch.setattr(
        cli_runtime, "platformio_invocation", lambda: pytest.fail("unexpected probe")
    )
    assert cli_runtime.required_platformio_invocation(dry_run=True) == ["platformio"]
