from __future__ import annotations

from arch_standard.release.changelog import render_changelog_entry
from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Automation, Level, Rule, ValidationSpec


def _rule(rule_id: str, level: Level, name: str = "example rule") -> Rule:
    return Rule(
        id=rule_id,
        name=name,
        level=level,
        automation=Automation.MANUAL,
        category="example",
        description="desc",
        rationale="rationale",
        correct="ok",
        incorrect="bad",
        validation=ValidationSpec(tool="review"),
    )


def test_given_added_and_removed_rules__when_rendered__then_both_sections_present() -> None:
    old = Catalog([_rule("ARCH-800", Level.SHOULD, name="retired rule")])
    new = Catalog([_rule("ARCH-900", Level.SHOULD, name="new rule")])
    changes = [
        RuleChange(rule_id="ARCH-900", kind=ChangeKind.ADDED, new_level=Level.SHOULD),
        RuleChange(rule_id="ARCH-800", kind=ChangeKind.REMOVED, old_level=Level.SHOULD),
    ]

    entry = render_changelog_entry("1.1.0", old, new, changes, migration_notes=None)

    assert "## 1.1.0" in entry
    assert "### Added" in entry and "ARCH-900" in entry and "new rule" in entry
    assert "### Removed" in entry and "ARCH-800" in entry and "retired rule" in entry


def test_given_must_promotion_with_migration_notes__when_rendered__then_notes_included() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.MUST)])
    changes = [
        RuleChange(
            rule_id="ARCH-900",
            kind=ChangeKind.LEVEL_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.MUST,
        )
    ]

    entry = render_changelog_entry(
        "2.0.0",
        old,
        new,
        changes,
        migration_notes="Fix any remaining ARCH-900 warnings before upgrading.",
    )

    assert "### Changed" in entry
    assert "ARCH-900" in entry and "SHOULD -> MUST" in entry
    assert "#### Migration notes" in entry
    assert "Fix any remaining ARCH-900 warnings" in entry
