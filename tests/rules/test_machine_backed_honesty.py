from __future__ import annotations

from arch_standard.checks import all_checks
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

MACHINE_TOOLS = frozenset({"import-linter", "grimp", "ruff", "ast-checker", "schema"})


def test_given_a_machine_backed_rule__when_scanning_checks__then_some_check_claims_it() -> None:
    """The invariant the v1 audit found violated by 14 rules.

    A rule whose validation.tool names a machine validator is a promise to the
    reader of ARCHITECTURE_STANDARD.md that the rule is automatically enforced.
    Keep that promise structural: if no registered check claims the rule id,
    either build the check or relabel the rule as `review`.
    """
    catalog = Catalog.load(packaged_rules_dir())
    claimed: set[str] = set()
    for check in all_checks():
        claimed |= set(check.rule_ids)
    unbacked = sorted(
        rule.id
        for rule in catalog
        if rule.validation.tool in MACHINE_TOOLS and rule.id not in claimed
    )
    assert not unbacked, (
        "these rules declare a machine validator but no check implements them: "
        f"{unbacked} -- implement the check, or set validation.tool to 'review'"
    )


def test_given_a_core_rule__when_scanning_checks__then_it_is_machine_checked() -> None:
    """Spec 9: core rules are 'binding from day one, all machine-checkable'."""
    catalog = Catalog.load(packaged_rules_dir())
    claimed: set[str] = set()
    for check in all_checks():
        claimed |= set(check.rule_ids)
    unchecked = sorted(r.id for r in catalog.core() if r.id not in claimed)
    assert not unchecked, f"core rules with no check: {unchecked}"


def test_given_a_claimed_rule__when_looked_up__then_it_exists_in_the_catalog() -> None:
    """The inverse: no check may claim a rule id the catalog does not define."""
    catalog = Catalog.load(packaged_rules_dir())
    known = {r.id for r in catalog}
    for check in all_checks():
        for rule_id in check.rule_ids:
            assert rule_id in known, f"{type(check).__name__} claims unknown rule {rule_id}"
