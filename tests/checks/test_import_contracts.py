from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.import_contracts import ImportContractsCheck, build_contracts
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"
MODULAR = FIX / "modular_project"


def test_build_contracts_names_contracts_after_rule_ids() -> None:
    layout = ProjectLayout.detect(FIX / "good_project")
    ini = build_contracts(layout)
    # good_project has an aggregate module (sales.orders) since Task 10's fixture
    # migration, so it is covered by the per-module layers contract, not the
    # legacy single-context ``ARCH-001`` contract (which no fixture triggers
    # anymore, since every fixture now has aggregate modules).
    assert "[importlinter:contract:ARCH-layers-sales-orders]" in ini
    assert "[importlinter:contract:ARCH-001]" not in ini
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
    # ARCH-002/ARCH-005 share the same per-module ``layers`` contract as ARCH-001
    # (sales.orders' domain importing its own infrastructure breaks all three).
    assert reports["ARCH-002"].outcome is Outcome.FAIL
    assert reports["ARCH-005"].outcome is Outcome.FAIL
    # ARCH-006 is its own ``forbidden`` contract post-Task-10, only emitted when
    # the context has an entrypoints/ dir. bad_project has none, so ARCH-006 has
    # nothing to break and PASSes (uncovered, not a genuine violation) — unlike
    # pre-migration, when it artificially FAILed as collateral from sharing one
    # coarse ``layers`` contract with ARCH-001/002/005.
    assert reports["ARCH-006"].outcome is Outcome.PASS
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


def test_non_ddd_tree_skips_instead_of_erroring(tmp_path: Path) -> None:
    # Follow-through from C1 + I5: with no contexts and no commons/bootstrap,
    # there is no root package at all for import-linter to build a graph from
    # (it errors on an empty root_packages list). That must SKIP, not FAIL —
    # otherwise running arch-standard against a tree it doesn't understand
    # invents findings instead of reporting "nothing to check here".
    (tmp_path / "src" / "somepkg").mkdir(parents=True)
    (tmp_path / "src" / "somepkg" / "foo.py").write_text("x = 1\n")
    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ()
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.SKIP for r in reports)


def test_given_the_modular_fixture__when_building_contracts__then_module_layers_are_emitted() -> (
    None
):
    ini = build_contracts(ProjectLayout.detect(MODULAR))
    assert "sales.users.domain" in ini
    assert "[importlinter:contract:ARCH-046-sales]" in ini
    assert "[importlinter:contract:ARCH-052-sales]" in ini
    # entrypoints is no longer part of a module-scoped `layers` contract: it is a
    # context-level sibling of the modules, covered separately by ARCH-006-<ctx>.
    assert "[importlinter:contract:ARCH-006-sales]" in ini
    assert "[importlinter:contract:ARCH-006-billing]" in ini
    # billing has only one module, so ARCH-046 (cross-module isolation) does not apply.
    assert "[importlinter:contract:ARCH-046-billing]" not in ini
    # billing has no read/ dir.
    assert "[importlinter:contract:ARCH-052-billing]" not in ini
    # Legacy single-context layers contract must not appear: both fixture contexts
    # have aggregate modules.
    assert "[importlinter:contract:ARCH-001]" not in ini


def test_given_the_modular_fixture__when_checked__then_every_rule_passes() -> None:
    layout = ProjectLayout.detect(MODULAR)
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert all(r.outcome is Outcome.PASS for r in reports), [
        (r.rule_id, [f.message for f in r.findings])
        for r in reports
        if r.outcome is not Outcome.PASS
    ]
    # All 9 rules must be present and accounted for.
    assert {r.rule_id for r in reports} == set(ImportContractsCheck.rule_ids)


def test_migrated_fixtures_report_the_expected_outcomes() -> None:
    # Guardrail for Task 10: good_project/bad_project migrated into the
    # aggregate-module shape and now go entirely through the per-module contract
    # path (the legacy single-context branch is gone). good_project must still be
    # all-green; bad_project must still trip its genuine violations.
    good = ImportContractsCheck().run(
        ProjectLayout.detect(FIX / "good_project"), Catalog.load(RULES)
    )
    assert all(r.outcome is Outcome.PASS for r in good)

    bad = {
        r.rule_id: r
        for r in ImportContractsCheck().run(
            ProjectLayout.detect(FIX / "bad_project"), Catalog.load(RULES)
        )
    }
    assert bad["ARCH-001"].outcome is Outcome.FAIL
    # bad_project has no entrypoints/ dir, so no ARCH-006 contract is emitted for
    # it (there's nothing for the rule to check) -> uncovered-but-not-broken PASS.
    assert bad["ARCH-006"].outcome is Outcome.PASS
    assert bad["ARCH-012"].outcome is Outcome.PASS
    assert bad["ARCH-034"].outcome is Outcome.PASS
    # bad_project has only one module and no read/ dir: nothing for ARCH-046/052
    # to check, and no contract is emitted for them, so they stay
    # uncovered-but-not-broken -> PASS.
    assert bad["ARCH-046"].outcome is Outcome.PASS
    assert bad["ARCH-052"].outcome is Outcome.PASS


def test_two_module_context_with_a_cross_module_import_fails_arch_046(tmp_path: Path) -> None:
    src = tmp_path / "src"
    for module in ("orders", "users"):
        (src / "sales" / module / "domain" / "model").mkdir(parents=True)
        (src / "sales" / module / "domain" / "model" / "__init__.py").write_text("")
        (src / "sales" / module / "domain" / "__init__.py").write_text("")
        (src / "sales" / module / "application").mkdir(parents=True)
        (src / "sales" / module / "application" / "__init__.py").write_text("")
        (src / "sales" / module / "__init__.py").write_text("")
    (src / "sales" / "__init__.py").write_text("")
    (src / "__init__.py").write_text("")

    # Deliberate ARCH-046 violation: orders' application reaches into users' application.
    (src / "sales" / "orders" / "application" / "service.py").write_text(
        "from sales.users.application import UserService\n"
    )
    (src / "sales" / "users" / "application" / "__init__.py").write_text("class UserService: ...\n")

    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ("sales",)
    assert layout.modules("sales") == ("orders", "users")

    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-046"].outcome is Outcome.FAIL
    assert reports["ARCH-046"].findings


def test_context_with_entrypoints_and_an_application_import_of_it_fails_arch_006(
    tmp_path: Path,
) -> None:
    # Guardrail: post-Task-10, no fixture has both an entrypoints/ dir and an
    # application module that actually imports it, so nothing drives ARCH-006 to
    # FAIL anywhere else in the suite. This synthetic case exercises the genuine
    # violation the per-context ARCH-006-<ctx> forbidden contract exists to catch.
    src = tmp_path / "src"
    (src / "sales" / "orders" / "domain" / "model").mkdir(parents=True)
    (src / "sales" / "orders" / "domain" / "model" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "application").mkdir(parents=True)
    (src / "sales" / "orders" / "application" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "__init__.py").write_text("")
    (src / "sales" / "entrypoints").mkdir(parents=True)
    (src / "sales" / "entrypoints" / "__init__.py").write_text("")
    (src / "sales" / "entrypoints" / "http.py").write_text("class Router: ...\n")
    (src / "sales" / "__init__.py").write_text("")
    (src / "__init__.py").write_text("")

    # Deliberate ARCH-006 violation: orders' application reaches into sales.entrypoints.
    (src / "sales" / "orders" / "application" / "service.py").write_text(
        "from sales.entrypoints.http import Router\n"
    )

    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ("sales",)
    assert layout.modules("sales") == ("orders",)

    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-006"].outcome is Outcome.FAIL
    assert reports["ARCH-006"].findings
    # The violation is entrypoints-specific: it must not spill into the per-module
    # layers contract (ARCH-001/002/005), which knows nothing about entrypoints.
    assert reports["ARCH-001"].outcome is Outcome.PASS
    assert reports["ARCH-002"].outcome is Outcome.PASS
    assert reports["ARCH-005"].outcome is Outcome.PASS


def test_timeout_fails_all(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="lint-imports", timeout=120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.FAIL for r in reports)
    assert all("timed out" in r.findings[0].message for r in reports)
