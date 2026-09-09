from __future__ import annotations

from pathlib import Path

import pytest

from arch_standard.cli import main

_RULE_TEMPLATE = """
rules:
  - id: ARCH-900
    name: example rule
    level: {level}
    automation: manual
    category: example
    description: an example rule for release-check testing
    rationale: {rationale}
    correct: |
      pass
    incorrect: |
      fail
    validation:
      tool: review
"""

_DEFAULT_RATIONALE = "exercises the compatibility checker end to end"


def _write_rules(path: Path, level: str, rationale: str = _DEFAULT_RATIONALE) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "example.yaml").write_text(
        _RULE_TEMPLATE.format(level=level, rationale=rationale), encoding="utf-8"
    )


def test_given_sanctioned_should_to_must_promotion_with_major_bump__when_release_check__then_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "2.0.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_given_unsanctioned_must_promotion__when_release_check__then_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="MAY")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "2.0.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 1
    assert "ARCH-900" in capsys.readouterr().out


def test_given_must_promotion_with_only_minor_bump_requested__when_release_check__then_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")

    exit_code = main(["release-check", "--version", "1.2.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 1
    assert "requires at least a major bump" in capsys.readouterr().out


def test_given_no_released_snapshot__when_release_check__then_fails_with_guidance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir, level="SHOULD")

    exit_code = main(["release-check", "--version", "1.1.0", "--rules-dir", str(rules_dir)])
    assert exit_code == 1
    assert "no released snapshot to compare against" in capsys.readouterr().out


def test_given_wording_edit_to_an_already_must_rule__when_release_check__then_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The most common catalog edit: prose touched, level untouched at MUST."""
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="MUST")
    _write_rules(rules_dir, level="MUST", rationale="a reworded rationale, same binding level")

    exit_code = main(["release-check", "--version", "1.1.1", "--rules-dir", str(rules_dir)])
    assert exit_code == 0
    assert "OK" in capsys.readouterr().out
