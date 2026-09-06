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


def test_good_test_naming_passes() -> None:
    assert _reports("good_project")["ARCH-040"].outcome is Outcome.PASS


def test_bad_test_naming_warns() -> None:
    r = _reports("bad_project")["ARCH-040"]
    assert r.outcome is Outcome.WARN
    assert any("test_add_line_works" in f.message for f in r.findings)


def test_promotion_thresholds_pass_on_small_fixture() -> None:
    assert _reports("good_project")["ARCH-041"].outcome is Outcome.PASS


def test_good_aggregate_encapsulation_passes() -> None:
    reports = _reports("good_project")
    assert reports["ARCH-019"].outcome is Outcome.PASS
    assert reports["ARCH-018"].outcome is Outcome.PASS


def test_bad_aggregate_public_collection_fails_arch_019() -> None:
    r = _reports("bad_project")["ARCH-019"]
    assert r.outcome is Outcome.FAIL
    assert any("lines" in f.message for f in r.findings)


def test_bad_service_size_warns_arch_030() -> None:
    r = _reports("bad_project")["ARCH-030"]
    assert r.outcome is Outcome.WARN
    assert any("method" in f.message.lower() or "param" in f.message.lower() for f in r.findings)


def test_good_service_size_passes() -> None:
    assert _reports("good_project")["ARCH-030"].outcome is Outcome.PASS
