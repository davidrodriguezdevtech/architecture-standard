from __future__ import annotations

import shutil
from pathlib import Path

from arch_standard.version_stamp import parse_semver

_RELEASED_DIRNAME = ".released"


def snapshot_dir(rules_dir: Path, version: str) -> Path:
    return rules_dir / _RELEASED_DIRNAME / version


def write_snapshot(rules_dir: Path, version: str) -> Path:
    """Copy every rule YAML at rules_dir into rules_dir/.released/<version>/,
    freezing that version's catalog for future compatibility/changelog diffs."""
    if not rules_dir.is_dir():
        raise FileNotFoundError(f"rules_dir does not exist: {rules_dir}")
    dest = snapshot_dir(rules_dir, version)
    if dest.exists():
        raise FileExistsError(f"snapshot {version} already exists at {dest}")
    dest.mkdir(parents=True)
    for path in sorted(rules_dir.glob("*.yaml")):
        shutil.copy2(path, dest / path.name)
    return dest


def list_snapshot_versions(rules_dir: Path) -> list[str]:
    released = rules_dir / _RELEASED_DIRNAME
    if not released.is_dir():
        return []
    return sorted(
        (p.name for p in released.iterdir() if p.is_dir()),
        key=parse_semver,
    )


def latest_snapshot_version(rules_dir: Path) -> str | None:
    versions = list_snapshot_versions(rules_dir)
    return versions[-1] if versions else None
