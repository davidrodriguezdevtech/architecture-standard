from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.checks.schemas import IntegrationEventSchemaCheck
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _reports(name: str) -> dict[str, CheckReport]:
    layout = ProjectLayout.detect(FIX / name)
    return {r.rule_id: r for r in IntegrationEventSchemaCheck().run(layout, Catalog.load(RULES))}


def test_good_project_events_present_and_enveloped() -> None:
    reports = _reports("good_project")
    assert reports["ARCH-024"].outcome is Outcome.PASS
    assert reports["ARCH-043"].outcome is Outcome.PASS
    assert reports["ARCH-044"].outcome is Outcome.PASS


def test_bad_project_missing_integration_events_skips_or_warns() -> None:
    r = _reports("bad_project")["ARCH-043"]
    assert r.outcome in (Outcome.SKIP, Outcome.WARN)
