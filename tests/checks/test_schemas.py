from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.checks.schemas import IntegrationEventSchemaCheck
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

FIX = Path(__file__).parent.parent / "fixtures"
RULES = packaged_rules_dir()


def _reports(name: str) -> dict[str, CheckReport]:
    layout = ProjectLayout.detect(FIX / name)
    return {r.rule_id: r for r in IntegrationEventSchemaCheck().run(layout, Catalog.load(RULES))}


def test_good_project_events_present_and_enveloped() -> None:
    # I1: ARCH-024's dead accumulator never produced a finding, so it always
    # rubber-stamped PASS; the check no longer claims to cover it (dropped from
    # rule_ids) rather than keep a false PASS on a MUST.
    reports = _reports("good_project")
    assert "ARCH-024" not in reports
    assert reports["ARCH-043"].outcome is Outcome.PASS
    assert reports["ARCH-044"].outcome is Outcome.PASS


def test_bad_project_missing_integration_events_skips() -> None:
    # No integration_events.py at all in any context -> SKIP (any_events is False).
    r = _reports("bad_project")["ARCH-043"]
    assert r.outcome is Outcome.SKIP


def test_heuristic_finding_skips_a_must_rule_instead_of_failing_or_warning(
    tmp_path: Path,
) -> None:
    # I2: ARCH-043/044 are level: MUST in the catalog, but this check is a
    # shallow heuristic. A heuristic finding must SKIP with the finding attached
    # as an informational note — never WARN-on-a-MUST, never FAIL a MUST off a
    # low-confidence signal.
    # Post-Task-10, integration_events.py lives at the context root (there is no
    # context-level application/ anymore) — the module below just needs to exist
    # so "sales" is detected as a context at all.
    (tmp_path / "src" / "sales" / "orders" / "domain").mkdir(parents=True)
    src = tmp_path / "src" / "sales"
    (src / "integration_events.py").write_text(
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass OrderPlaced:\n"
        "    order_id: str\n",
        encoding="utf-8",
    )
    layout = ProjectLayout.detect(tmp_path)
    reports = {r.rule_id: r for r in IntegrationEventSchemaCheck().run(layout, Catalog.load(RULES))}
    r = reports["ARCH-043"]
    assert r.outcome is Outcome.SKIP
    assert r.findings
    assert "EventEnvelope" in r.findings[0].message
