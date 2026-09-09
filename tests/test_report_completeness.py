from __future__ import annotations

from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def test_given_any_project__when_collecting__then_every_catalog_rule_is_reported() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    reported = {r.rule_id for r in report.reports}
    assert reported == {r.id for r in catalog}, (
        f"unreported: {sorted({r.id for r in catalog} - reported)}"
    )


def test_given_prose_only_rules__when_collecting__then_marked_not_automated() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    by_id = {r.rule_id: r for r in report.reports}
    # ARCH-021 is declared validation.tool == "review" in the catalog.
    assert by_id["ARCH-021"].outcome is Outcome.NOT_AUTOMATED


def test_given_no_duplicate_rows__when_collecting__then_one_row_per_rule() -> None:
    catalog = Catalog.load(packaged_rules_dir())
    layout = ProjectLayout.detect(Path("tests/fixtures/good_project").resolve())
    report = Report.collect(layout, catalog, all_checks())
    ids = [r.rule_id for r in report.reports]
    assert len(ids) == len(set(ids))
