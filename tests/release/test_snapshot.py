from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.release.snapshot import (
    latest_snapshot_version,
    list_snapshot_versions,
    write_snapshot,
)


def _make_rules_dir(tmp_path: Path) -> Path:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "example.yaml").write_text("rules: []\n", encoding="utf-8")
    return rules_dir


def test_given_rules_dir__when_write_snapshot__then_copies_yaml_files(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    dest = write_snapshot(rules_dir, "1.0.0")
    assert dest == rules_dir / ".released" / "1.0.0"
    assert (dest / "example.yaml").read_text(encoding="utf-8") == "rules: []\n"


def test_given_existing_snapshot__when_write_snapshot_again__then_raises(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    write_snapshot(rules_dir, "1.0.0")
    try:
        write_snapshot(rules_dir, "1.0.0")
        raise AssertionError("expected FileExistsError")
    except FileExistsError:
        pass


def test_given_multiple_snapshots__when_listed__then_semver_sorted(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    write_snapshot(rules_dir, "1.10.0")
    write_snapshot(rules_dir, "1.2.0")
    write_snapshot(rules_dir, "2.0.0")
    assert list_snapshot_versions(rules_dir) == ["1.2.0", "1.10.0", "2.0.0"]
    assert latest_snapshot_version(rules_dir) == "2.0.0"


def test_given_no_snapshots__when_latest__then_none(tmp_path: Path) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    assert latest_snapshot_version(rules_dir) is None


def test_given_nonexistent_rules_dir__when_write_snapshot__then_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_snapshot(tmp_path / "does-not-exist", "1.0.0")
