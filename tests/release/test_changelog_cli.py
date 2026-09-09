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
    description: an example rule for changelog testing
    rationale: exercises the changelog CLI end to end
    correct: |
      pass
    incorrect: |
      fail
    validation:
      tool: review
"""


def _write_rules(path: Path, level: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "example.yaml").write_text(_RULE_TEMPLATE.format(level=level), encoding="utf-8")


def test_given_must_promotion_without_migration_notes__when_changelog__then_fails(
    tmp_path: Path,
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\n", encoding="utf-8")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(changelog_file),
        ]
    )
    assert exit_code == 1


def test_given_must_promotion_with_migration_notes__when_changelog__then_prepends_entry(
    tmp_path: Path,
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\nolder entries here\n", encoding="utf-8")
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("Upgrade guidance for ARCH-900.", encoding="utf-8")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(changelog_file),
            "--migration-notes",
            str(notes_file),
        ]
    )
    assert exit_code == 0
    content = changelog_file.read_text(encoding="utf-8")
    assert content.startswith("# Changelog\n\n## 2.0.0")
    assert "Upgrade guidance for ARCH-900." in content
    assert "older entries here" in content  # existing history preserved, not overwritten


_REAL_SHAPED_CHANGELOG = """\
# Changelog

All notable changes to the rule catalog are recorded here, one version per
section. The compatibility policy governs which bump each change requires.

## 1.1.0

Initial catalog and tooling.
"""


def test_given_a_changelog_with_an_intro_paragraph__when_changelog__then_intro_stays_on_top(
    tmp_path: Path,
) -> None:
    """The intro prose belongs to the title, not to whichever entry follows it."""
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir / ".released" / "1.1.0", level="SHOULD")
    _write_rules(rules_dir, level="MUST")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(_REAL_SHAPED_CHANGELOG, encoding="utf-8")
    notes_file = tmp_path / "notes.md"
    notes_file.write_text("Upgrade guidance for ARCH-900.", encoding="utf-8")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(changelog_file),
            "--migration-notes",
            str(notes_file),
        ]
    )
    assert exit_code == 0

    content = changelog_file.read_text(encoding="utf-8")
    intro = "All notable changes to the rule catalog are recorded here, one version per"
    assert content.count(intro) == 1  # not duplicated
    assert content.startswith(
        "# Changelog\n\n"
        "All notable changes to the rule catalog are recorded here, one version per\n"
        "section. The compatibility policy governs which bump each change requires.\n"
        "\n"
        "## 2.0.0\n"
    )
    assert content.index("## 2.0.0") < content.index("## 1.1.0")  # newest entry first
    assert "Initial catalog and tooling." in content  # old entry's body survives


def test_given_no_released_snapshot__when_changelog__then_fails_with_guidance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules_dir = tmp_path / "rules"
    _write_rules(rules_dir, level="SHOULD")

    exit_code = main(
        [
            "changelog",
            "--version",
            "2.0.0",
            "--rules-dir",
            str(rules_dir),
            "--changelog-file",
            str(tmp_path / "CHANGELOG.md"),
        ]
    )
    assert exit_code == 1
    assert "no released snapshot to compare against" in capsys.readouterr().out
