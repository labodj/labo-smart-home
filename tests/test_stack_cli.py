"""Tests for the lsh-stack CLI launcher surface."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

from lsh_stack_config import __version__, cli, scaffold


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
