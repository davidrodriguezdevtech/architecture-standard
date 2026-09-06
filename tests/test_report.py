from __future__ import annotations

from datetime import date
from pathlib import Path

from arch_standard.checks import all_checks
from arch_standard.checks.adr_waivers import Waiver
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.report import Report
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent / "fixtures"
RULES = Path(__file__).parent.parent / "rules"


def test_collect_runs_every_check_and_covers_rules() -> None:
    catalog = Catalog.load(RULES)
    layout = ProjectLayout.detect(FIX / "good_project")
    report = Report.collect(layout, catalog, all_checks())
    covered = {r.rule_id for r in report.reports}
    assert {"ARCH-001", "ARCH-023", "ARCH-003"} <= covered
    assert report.exit_code(catalog) == 0


def test_bad_project_exit_code_is_one() -> None:
    catalog = Catalog.load(RULES)
    layout = ProjectLayout.detect(FIX / "bad_project")
    report = Report.collect(layout, catalog, all_checks())
    assert report.exit_code(catalog) == 1


def test_waiver_downgrades_fail_to_warn() -> None:
    catalog = Catalog.load(RULES)
    report = Report(reports=(CheckReport(rule_id="ARCH-001", outcome=Outcome.FAIL),))
    waived = report.with_waivers(
        {"ARCH-001": [Waiver("ARCH-001", "scope", date(2999, 1, 1), "0009.md")]}
    )
    assert waived.reports[0].outcome is Outcome.WARN
    assert waived.exit_code(catalog) == 0


def test_format_text_has_summary_footer() -> None:
    catalog = Catalog.load(RULES)
    report = Report(reports=(CheckReport(rule_id="ARCH-001", outcome=Outcome.PASS),))
    text = report.format_text(catalog)
    assert "ARCH-001" in text
    assert "passed" in text
