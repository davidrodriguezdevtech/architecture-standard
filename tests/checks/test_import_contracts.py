from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.import_contracts import ImportContractsCheck, build_contracts
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def test_build_contracts_names_contracts_after_rule_ids() -> None:
    layout = ProjectLayout.detect(FIX / "good_project")
    ini = build_contracts(layout)
    assert "[importlinter:contract:ARCH-001]" in ini
    assert "[importlinter:contract:ARCH-012]" in ini
    assert "type = layers" in ini
    assert "type = independence" in ini


def test_good_project_passes() -> None:
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert all(r.outcome is Outcome.PASS for r in reports)


def test_bad_project_fails_arch_001() -> None:
    layout = ProjectLayout.detect(FIX / "bad_project")
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-001"].outcome is Outcome.FAIL
    assert reports["ARCH-001"].findings
    # Fails because import-linter reported a broken contract, not because it errored.
    assert reports["ARCH-001"].findings[0].message == "import-linter contract broken"
    # A clean edge (application layer) still passes under the coarse v1 mapping only
    # when the contract is kept; here the layered contract is broken so all four fail.
    assert reports["ARCH-006"].outcome is Outcome.FAIL
    # Contracts unrelated to the violation stay green.
    assert reports["ARCH-012"].outcome is Outcome.PASS
    assert reports["ARCH-034"].outcome is Outcome.PASS
