from __future__ import annotations

from arch_standard.checks.base import CheckReport, Outcome
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def _catalog() -> Catalog:
    return Catalog.load(packaged_rules_dir())


def test_given_an_error_outcome__when_computing_exit_code__then_non_zero() -> None:
    report = Report(reports=(CheckReport(rule_id="ARCH-040", outcome=Outcome.ERROR),))
    assert report.exit_code(_catalog()) == 1


def test_given_an_error_on_a_should_rule__when_computing_exit_code__then_still_non_zero() -> None:
    """ERROR is about the validator, not the rule's severity."""
    report = Report(reports=(CheckReport(rule_id="ARCH-013", outcome=Outcome.ERROR),))
    assert report.exit_code(_catalog()) == 1


def test_given_not_automated__when_computing_exit_code__then_zero() -> None:
    report = Report(reports=(CheckReport(rule_id="ARCH-021", outcome=Outcome.NOT_AUTOMATED),))
    assert report.exit_code(_catalog()) == 0


def test_given_mixed_outcomes__when_formatting__then_counts_every_outcome() -> None:
    report = Report(
        reports=(
            CheckReport(rule_id="ARCH-001", outcome=Outcome.PASS),
            CheckReport(rule_id="ARCH-002", outcome=Outcome.SKIP),
            CheckReport(rule_id="ARCH-021", outcome=Outcome.NOT_AUTOMATED),
            CheckReport(rule_id="ARCH-040", outcome=Outcome.ERROR),
        )
    )
    text = report.format_text(_catalog())
    assert "1 passed" in text
    assert "1 skipped" in text
    assert "1 not automated" in text
    assert "1 errored" in text
