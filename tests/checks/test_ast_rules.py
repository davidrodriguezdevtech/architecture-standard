from __future__ import annotations

from pathlib import Path

from arch_standard.checks.ast_rules import AstRulesCheck
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _reports(project_name: str) -> dict[str, CheckReport]:
    layout = ProjectLayout.detect(FIX / project_name)
    return {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}


def test_good_project_events_and_vos_pass() -> None:
    reports = _reports("good_project")
    assert reports["ARCH-023"].outcome is Outcome.PASS
    assert reports["ARCH-031"].outcome is Outcome.PASS


def test_bad_project_event_not_frozen_or_past_tense() -> None:
    r = _reports("bad_project")["ARCH-023"]
    assert r.outcome is Outcome.FAIL
    assert any("PlaceOrder" in f.message for f in r.findings)


def test_bad_project_value_object_not_frozen() -> None:
    r = _reports("bad_project")["ARCH-031"]
    assert r.outcome is Outcome.FAIL
    assert any("Email" in f.message for f in r.findings)


def test_unimplemented_rules_skip_for_now() -> None:
    assert _reports("good_project")["ARCH-041"].outcome is Outcome.SKIP
