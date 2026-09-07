from __future__ import annotations

from arch_standard.release.compatibility import (
    actual_bump,
    bump_satisfies,
    find_unsanctioned_must_promotions,
    required_bump,
)
from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.model import Level


def test_given_should_promoted_to_must__when_required_bump__then_major() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-900",
            kind=ChangeKind.LEVEL_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.MUST,
        )
    ]
    assert required_bump(changes) == "major"


def test_given_new_should_rule_added__when_required_bump__then_minor() -> None:
    changes = [RuleChange(rule_id="ARCH-900", kind=ChangeKind.ADDED, new_level=Level.SHOULD)]
    assert required_bump(changes) == "minor"


def test_given_only_wording_changed__when_required_bump__then_patch() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-900",
            kind=ChangeKind.CONTENT_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.SHOULD,
        )
    ]
    assert required_bump(changes) == "patch"


def test_given_no_changes__when_required_bump__then_none() -> None:
    assert required_bump([]) == "none"


def test_given_actual_and_required_bumps__when_compared__then_satisfies() -> None:
    assert bump_satisfies("major", "major")
    assert bump_satisfies("major", "minor")
    assert not bump_satisfies("minor", "major")
    assert not bump_satisfies("patch", "minor")


def test_given_version_pair__when_actual_bump__then_classified() -> None:
    assert actual_bump("1.1.0", "2.0.0") == "major"
    assert actual_bump("1.1.0", "1.2.0") == "minor"
    assert actual_bump("1.1.0", "1.1.1") == "patch"
    assert actual_bump("1.1.0", "1.1.0") == "none"


def test_given_should_promoted_to_must__when_checked_for_sanction__then_no_violation() -> None:
    """The sanctioned path: SHOULD in the preceding snapshot, MUST now."""
    changes = [
        RuleChange(
            rule_id="ARCH-900",
            kind=ChangeKind.LEVEL_CHANGED,
            old_level=Level.SHOULD,
            new_level=Level.MUST,
        )
    ]
    assert find_unsanctioned_must_promotions(changes) == []


def test_given_new_rule_landing_directly_as_must__when_checked__then_violation() -> None:
    changes = [RuleChange(rule_id="ARCH-901", kind=ChangeKind.ADDED, new_level=Level.MUST)]
    assert find_unsanctioned_must_promotions(changes) == ["ARCH-901"]


def test_given_may_jumping_straight_to_must__when_checked__then_violation() -> None:
    changes = [
        RuleChange(
            rule_id="ARCH-902",
            kind=ChangeKind.LEVEL_CHANGED,
            old_level=Level.MAY,
            new_level=Level.MUST,
        )
    ]
    assert find_unsanctioned_must_promotions(changes) == ["ARCH-902"]
