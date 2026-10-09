"""Update only pristine, recorded scaffold files; never overwrite customizations."""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from .errors import StackConfigError
from .models import StackConfig
from .platformio_utils import path_for_platformio
from .scaffold_templates import (
    BRIDGE_MAIN_TEMPLATE,
    BRIDGE_PLATFORMIO_TEMPLATE,
    CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
    CORE_MAIN_TEMPLATE,
    CORE_PLATFORMIO_TEMPLATE,
)

MANIFEST = ".lsh-stack/templates.json"


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def template_files(config: StackConfig) -> dict[Path, str]:
    """Limit ownership to build shells; topology, secrets and overrides are never templates."""
    root = config.path.parent
    core = config.platformio.core_project or config.core.devices.parent
    bridge = config.platformio.bridge_project or root / "bridge"
    return {
        core / "platformio.ini": CORE_PLATFORMIO_TEMPLATE.replace(
            "../generated/platformio-core.ini",
            path_for_platformio(root / "generated/platformio-core.ini", core),
        ).replace(
            "custom_lsh_config = lsh_devices.toml",
            f"custom_lsh_config = {path_for_platformio(config.core.devices, core)}",
        ),
        core / "scripts/lsh_core_bootstrap.py": CORE_BOOTSTRAP_SCRIPT_TEMPLATE,
        core / "src/main.cpp": CORE_MAIN_TEMPLATE,
        bridge / "platformio.ini": BRIDGE_PLATFORMIO_TEMPLATE.replace(
            "../generated/platformio-bridge.ini",
            path_for_platformio(root / "generated/platformio-bridge.ini", bridge),
        ),
        bridge / "src/main.cpp": BRIDGE_MAIN_TEMPLATE,
    }


def record_templates(config: StackConfig) -> None:
    """Record originals only when a new installation has just been created."""
    root = config.path.parent
    hashes = {
        str(path.relative_to(root)): _digest(content)
        for path, content in template_files(config).items()
    }
    _save_manifest(root, hashes)


def _safe_path(root: Path, path: Path) -> None:
    # Refuse symlinks, including parent directories, before reads or writes.
    if not path.is_relative_to(root):
        raise StackConfigError(f"template is outside this installation: {path}")
    current = path
    while current != root:
        if current.is_symlink():
            raise StackConfigError(f"refusing a symlink in template path: {current}")
        current = current.parent


def _save_manifest(root: Path, hashes: dict[str, str]) -> None:
    path = root / MANIFEST
    _safe_path(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(json.dumps({"schema": 1, "files": hashes}, indent=2) + "\n")
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def update_templates(config: StackConfig, *, action: str) -> int:
    """Preview every difference; apply only files equal to their recorded originals."""
    root = config.path.parent
    manifest = root / MANIFEST
    _safe_path(root, manifest)
    hashes = _read_manifest(manifest)
    changes: list[tuple[Path, str, str]] = []
    conflicts = 0
    for path, desired in template_files(config).items():
        _safe_path(root, path)
        relative = str(path.relative_to(root))
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == desired:
            hashes[relative] = _digest(desired)
            continue
        safe = current is not None and hashes.get(relative) == _digest(current)
        label = "update available" if safe else "custom/unknown: preserved"
        sys.stdout.write(f"{relative}: {label}\n")
        if action == "diff":
            sys.stdout.write(
                "".join(
                    difflib.unified_diff(
                        (current or "").splitlines(keepends=True),
                        desired.splitlines(keepends=True),
                        fromfile=relative,
                        tofile=relative + " (new template)",
                    )
                ),
            )
        if safe and current is not None:
            changes.append((path, current, desired))
        else:
            conflicts += 1
    if action != "apply":
        return 1 if changes or conflicts else 0
    backup = root / ".lsh-stack/backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    for path, current, desired in changes:
        copy = backup / path.relative_to(root)
        _safe_path(root, copy)
        copy.parent.mkdir(parents=True, exist_ok=True)
        with copy.open("x", encoding="utf-8") as handle:
            handle.write(current)
        path.write_text(desired, encoding="utf-8")
        hashes[str(path.relative_to(root))] = _digest(desired)
        sys.stdout.write(f"updated {path.relative_to(root)}; backup: {copy.relative_to(root)}\n")
    _save_manifest(root, hashes)
    sys.stdout.write(
        "Custom files need manual review with templates diff; run setup after updates.\n"
        if conflicts
        else "Templates current; run setup to regenerate and verify firmware.\n"
    )
    return 1 if conflicts else 0


def _read_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise StackConfigError(f"invalid {MANIFEST}: {exc}; restore its backup") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != 1
        or not isinstance(raw.get("files"), dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw["files"].items())
    ):
        raise StackConfigError(f"invalid {MANIFEST}; restore its backup")
    return dict(raw["files"])
