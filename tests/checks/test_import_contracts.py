from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


def test_errored_run_after_a_kept_contract_fails_all(monkeypatch: pytest.MonkeyPatch) -> None:
    # import-linter reports one KEPT contract, then exits non-zero for a reason
    # other than a broken contract (grimp exception, module-not-in-graph, ...).
    # RULING 4: no covered rule may PASS off an errored run.
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["lint-imports"],
            returncode=1,
            stdout="ARCH-001 ARCH-002 ARCH-005 ARCH-006 layered KEPT\n",
            stderr="grimp.exceptions.ModuleNotPresent: boom\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.FAIL for r in reports)
    assert all("exited 1" in r.findings[0].message for r in reports)


def test_minimal_project_with_no_commons_or_bootstrap_passes() -> None:
    # C1: build_contracts must not invent commons/bootstrap roots or require every
    # layer to exist — a single-context project with only domain/ must not spuriously
    # FAIL rules it does cover.
    layout = ProjectLayout.detect(FIX / "minimal_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.PASS for r in reports)


def test_timeout_fails_all(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="lint-imports", timeout=120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.FAIL for r in reports)
    assert all("timed out" in r.findings[0].message for r in reports)
