from __future__ import annotations

from arch_standard.release.diff import ChangeKind, RuleChange
from arch_standard.rules.model import Level
from arch_standard.version_stamp import parse_semver

_BINDING = (Level.MUST, Level.MUST_CONDITIONAL)
_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}


def required_bump(changes: list[RuleChange]) -> str:
    """The minimum version-bump kind (spec Section 16.3) implied by a diff."""
    if any(
        change.kind in (ChangeKind.ADDED, ChangeKind.LEVEL_CHANGED) and change.new_level in _BINDING
        for change in changes
    ):
        return "major"
    if any(change.kind in (ChangeKind.ADDED, ChangeKind.LEVEL_CHANGED) for change in changes):
        return "minor"
    if changes:
        return "patch"
    return "none"


def actual_bump(old_version: str, new_version: str) -> str:
    old_major, old_minor, old_patch = parse_semver(old_version)
    new_major, new_minor, new_patch = parse_semver(new_version)
    if new_major != old_major:
        return "major"
    if new_minor != old_minor:
        return "minor"
    if new_patch != old_patch:
        return "patch"
    return "none"


def bump_satisfies(actual: str, required: str) -> bool:
    return _ORDER[actual] >= _ORDER[required]


def find_unsanctioned_must_promotions(changes: list[RuleChange]) -> list[str]:
    """A rule must never jump straight to MUST/MUST* -- it must have been
    SHOULD in the immediately preceding released snapshot (spec Section
    16.3: 'a new MUST never lands directly'). Returns the offending rule ids."""
    violations: list[str] = []
    for change in changes:
        if change.kind not in (ChangeKind.ADDED, ChangeKind.LEVEL_CHANGED):
            continue  # wording/rationale/example-only edits never promote a rule
        if change.new_level not in _BINDING:
            continue
        if change.kind == ChangeKind.LEVEL_CHANGED and change.old_level in _BINDING:
            continue  # already binding (MUST <-> MUST_CONDITIONAL) -- not a new promotion
        if change.kind == ChangeKind.LEVEL_CHANGED and change.old_level is Level.SHOULD:
            continue  # SHOULD -> MUST is exactly the sanctioned promotion
        violations.append(change.rule_id)
    return violations
