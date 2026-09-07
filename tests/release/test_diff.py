from __future__ import annotations

from arch_standard.release.diff import ChangeKind, diff_catalogs
from arch_standard.rules.catalog import Catalog
from arch_standard.rules.model import Automation, Level, Rule, ValidationSpec


def _rule(rule_id: str, level: Level, description: str = "desc") -> Rule:
    return Rule(
        id=rule_id,
        name=f"name for {rule_id}",
        level=level,
        automation=Automation.MANUAL,
        category="example",
        description=description,
        rationale="rationale",
        correct="ok",
        incorrect="bad",
        validation=ValidationSpec(tool="review"),
    )


def test_given_new_rule_added__when_diffed__then_reports_added() -> None:
    old = Catalog([])
    new = Catalog([_rule("ARCH-900", Level.SHOULD)])
    changes = diff_catalogs(old, new)
    assert changes == [_rule_change("ARCH-900", ChangeKind.ADDED, new_level=Level.SHOULD)]


def test_given_rule_removed__when_diffed__then_reports_removed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([])
    changes = diff_catalogs(old, new)
    assert changes == [_rule_change("ARCH-900", ChangeKind.REMOVED, old_level=Level.SHOULD)]


def test_given_level_raised__when_diffed__then_reports_level_changed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.MUST)])
    changes = diff_catalogs(old, new)
    assert changes == [
        _rule_change(
            "ARCH-900",
            ChangeKind.LEVEL_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.MUST,
        )
    ]


def test_given_only_description_changed__when_diffed__then_reports_content_changed() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD, description="old wording")])
    new = Catalog([_rule("ARCH-900", Level.SHOULD, description="new wording")])
    changes = diff_catalogs(old, new)
    assert changes == [
        _rule_change(
            "ARCH-900",
            ChangeKind.CONTENT_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.SHOULD,
        )
    ]


def test_given_identical_catalogs__when_diffed__then_no_changes() -> None:
    old = Catalog([_rule("ARCH-900", Level.SHOULD)])
    new = Catalog([_rule("ARCH-900", Level.SHOULD)])
    assert diff_catalogs(old, new) == []


def _rule_change(
    rule_id: str,
    kind: ChangeKind,
    old_level: Level | None = None,
    new_level: Level | None = None,
) -> object:
    from arch_standard.release.diff import RuleChange

    return RuleChange(rule_id=rule_id, kind=kind, old_level=old_level, new_level=new_level)
