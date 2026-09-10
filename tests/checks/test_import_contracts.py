from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.import_contracts import ImportContractsCheck, build_contracts
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

FIX = Path(__file__).parent.parent / "fixtures"
RULES = packaged_rules_dir()
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
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    # good_project has only one module and no read/ dir: ARCH-046/052 have
    # nothing to check (I3: uncovered means SKIP, not a vacuous PASS).
    # good_project has no shared_kernel/ (Task 7: zero fixture presence, see
    # ``_shared_kernel_available``), so ARCH-014 has nothing to check either.
    skipped = {"ARCH-046", "ARCH-052", "ARCH-014"}
    for rule_id, report in reports.items():
        expected = Outcome.SKIP if rule_id in skipped else Outcome.PASS
        assert report.outcome is expected, rule_id


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
    # nothing to check at all — I3: that is SKIP (uncovered), not a vacuous
    # PASS — unlike pre-migration, when it artificially FAILed as collateral
    # from sharing one coarse ``layers`` contract with ARCH-001/002/005.
    assert reports["ARCH-006"].outcome is Outcome.SKIP
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
    # I3: minimal_project has no entrypoints/, no commons/, only one module, and no
    # read/ dir — ARCH-006/046/052 have nothing to check and SKIP instead of a
    # vacuous PASS. ARCH-034/035 no longer SKIP here (Task 10 correction): commons
    # is not vendored under minimal_project's own src/, but it resolves via the
    # installed arch-commons dependency in the interpreter running this test (this
    # repo's own workspace), so both contracts ARE genuinely emitted and genuinely
    # satisfied (nothing in minimal_project imports commons.infrastructure, and
    # commons.types imports no forbidden framework) — a real PASS, not a vacuous one.
    # Task 7: minimal_project also has no entrypoints/ (ARCH-009/011 have nothing
    # to check) and no shared_kernel/ (ARCH-014 has nothing to check). ARCH-017
    # also has nothing to check (no bootstrap/). ARCH-015 DOES get evaluated: its
    # source is commons.types, which resolves via the installed arch-commons
    # dependency the same way ARCH-034/035 do, and nothing in minimal_project
    # imports the sales context from commons.types, so it is a genuine PASS.
    layout = ProjectLayout.detect(FIX / "minimal_project")
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports
    skipped = {
        "ARCH-006",
        "ARCH-046",
        "ARCH-052",
        "ARCH-009",
        "ARCH-011",
        "ARCH-014",
        "ARCH-017",
    }
    for rule_id, report in reports.items():
        expected = Outcome.SKIP if rule_id in skipped else Outcome.PASS
        assert report.outcome is expected, rule_id


def test_non_ddd_tree_skips_instead_of_erroring(tmp_path: Path) -> None:
    # Follow-through from C1 + I5: with no contexts, there is nothing for
    # import-linter to build a *layering/independence* graph from, so ARCH-001/
    # 002/005/006/012/046/052 (all context-scoped) SKIP.
    # ARCH-035 is the one exception (Task 10 correction): commons.types resolves
    # via the installed arch-commons dependency in the interpreter running this
    # test regardless of whether this tree has any contexts at all, so
    # `root_packages = [commons]` alone is enough for import-linter to build a
    # graph and genuinely evaluate ARCH-035 -- it PASSes (commons.types imports no
    # forbidden framework), not SKIPs. ARCH-034 still SKIPs: it additionally
    # requires a non-empty domain_app (there being anything to forbid commons.
    # infrastructure FROM), which this contextless tree has none of.
    (tmp_path / "src" / "somepkg").mkdir(parents=True)
    (tmp_path / "src" / "somepkg" / "foo.py").write_text("x = 1\n")
    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ()
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports
    assert reports["ARCH-035"].outcome is Outcome.PASS
    skipped = set(reports) - {"ARCH-035"}
    for rule_id in skipped:
        assert reports[rule_id].outcome is Outcome.SKIP, rule_id


def test_given_a_completely_empty_project__when_checked__then_skips_instead_of_crashing(
    tmp_path: Path,
) -> None:
    """No .arch-standard, no src/ at all -- ImportContractsCheck must SKIP
    everything, not crash trying to subprocess.run(cwd=<nonexistent src>)."""
    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ()
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports
    for report in reports.values():
        assert report.outcome is Outcome.SKIP


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
    # modular_project has no commons/ dir vendored under its own src/, but
    # commons resolves via the installed arch-commons dependency in the
    # interpreter running this test (Task 10 correction), so ARCH-034/035 are
    # genuinely emitted (not SKIPped) here too. Every rule's contract is
    # genuinely emitted (sales has 2 modules, entrypoints, and a read/ dir;
    # billing has entrypoints; both contexts have 2 entrypoint modules each as
    # of Task 7, so ARCH-011 is genuinely emitted too) and nothing in the
    # fixture violates any of them, so every rule PASSes -- except ARCH-014
    # (no shared_kernel/ anywhere in this fixture; Task 7 gives it zero
    # fixture presence, see ``_shared_kernel_available``) and ARCH-017 (no
    # bootstrap/ in this fixture either), which both SKIP instead.
    layout = ProjectLayout.detect(MODULAR)
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    skipped_here = {"ARCH-014", "ARCH-017"}
    for rule_id, report in reports.items():
        if rule_id in skipped_here:
            assert report.outcome is Outcome.SKIP, (rule_id, [f.message for f in report.findings])
            continue
        assert report.outcome is Outcome.PASS, (rule_id, [f.message for f in report.findings])
    # All 18 rules must be present and accounted for.
    assert set(reports) == set(ImportContractsCheck.rule_ids)


def test_migrated_fixtures_report_the_expected_outcomes() -> None:
    # Guardrail for Task 10: good_project/bad_project migrated into the
    # aggregate-module shape and now go entirely through the per-module contract
    # path (the legacy single-context branch is gone). good_project must still be
    # green on every rule it actually covers; bad_project must still trip its
    # genuine violations. good_project has only one module and no read/ dir, so
    # ARCH-046/052 have nothing to check and SKIP (I3) instead of a vacuous PASS.
    good = {
        r.rule_id: r
        for r in ImportContractsCheck().run(
            ProjectLayout.detect(FIX / "good_project"), Catalog.load(RULES)
        )
    }
    # good_project has no shared_kernel/ (Task 7: zero fixture presence), so
    # ARCH-014 has nothing to check either.
    good_skipped = {"ARCH-046", "ARCH-052", "ARCH-014"}
    for rule_id, report in good.items():
        expected = Outcome.SKIP if rule_id in good_skipped else Outcome.PASS
        assert report.outcome is expected, rule_id

    bad = {
        r.rule_id: r
        for r in ImportContractsCheck().run(
            ProjectLayout.detect(FIX / "bad_project"), Catalog.load(RULES)
        )
    }
    assert bad["ARCH-001"].outcome is Outcome.FAIL
    # bad_project has no entrypoints/ dir, so no ARCH-006 contract is emitted for
    # it (there's nothing for the rule to check) -> SKIP (I3), not a vacuous PASS.
    assert bad["ARCH-006"].outcome is Outcome.SKIP
    assert bad["ARCH-012"].outcome is Outcome.PASS
    assert bad["ARCH-034"].outcome is Outcome.PASS
    # bad_project has only one module and no read/ dir: nothing for ARCH-046/052
    # to check, and no contract is emitted for them, so they SKIP (I3).
    assert bad["ARCH-046"].outcome is Outcome.SKIP
    assert bad["ARCH-052"].outcome is Outcome.SKIP


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


def test_given_a_single_module_context__when_checked__then_arch_046_skips_not_passes(
    tmp_path: Path,
) -> None:
    # I3: with only one module, no ARCH-046 contract is ever emitted (nothing to
    # check — a single module cannot import a sibling). That must report SKIP,
    # not a vacuous PASS: "nothing to check" and "checked, no violation" are
    # different categories, and ARCH-046 is a core-tier MUST.
    src = tmp_path / "src"
    (src / "sales" / "orders" / "domain" / "model").mkdir(parents=True)
    (src / "sales" / "orders" / "domain" / "model" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "__init__.py").write_text("")
    (src / "sales" / "__init__.py").write_text("")
    (src / "__init__.py").write_text("")

    layout = ProjectLayout.detect(tmp_path)
    assert layout.modules("sales") == ("orders",)
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-046"].outcome is Outcome.SKIP
    assert reports["ARCH-046"].findings == ()
    # The per-module layers contract IS emitted regardless, so it stays covered.
    assert reports["ARCH-001"].outcome is Outcome.PASS


def test_timeout_fails_all(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="lint-imports", timeout=120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = ImportContractsCheck().run(layout, Catalog.load(RULES))
    assert reports
    assert all(r.outcome is Outcome.FAIL for r in reports)
    assert all("timed out" in r.findings[0].message for r in reports)


def test_given_installed_commons_types__when_build_contracts__then_arch_035_present(
    tmp_path: Path,
) -> None:
    """commons.types is NOT vendored under this project's src/ -- it resolves
    only because arch-commons is installed in the running interpreter (this
    repo's own dev environment, via the Task 1 workspace dependency)."""
    root = tmp_path / "proj"
    for rel in [
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")
    assert not (root / "src" / "commons").exists()

    layout = ProjectLayout.detect(root)
    ini = build_contracts(layout)

    assert "ARCH-034" in ini
    assert "ARCH-035" in ini


def test_given_installed_commons__when_checked__then_arch_034_catches_violation(
    tmp_path: Path,
) -> None:
    """Negative-case guardrail for Task 10's correction: commons being resolvable
    only via the installed arch-commons dependency (not vendored) must not turn
    ARCH-034 into a rule that can never fail. An application module that actually
    imports commons.infrastructure must still be caught."""
    src = tmp_path / "src"
    (src / "sales" / "orders" / "domain" / "model").mkdir(parents=True)
    (src / "sales" / "orders" / "domain" / "model" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "application").mkdir(parents=True)
    (src / "sales" / "orders" / "application" / "__init__.py").write_text("")
    (src / "sales" / "orders" / "__init__.py").write_text("")
    (src / "sales" / "__init__.py").write_text("")
    (src / "__init__.py").write_text("")
    assert not (src / "commons").exists()

    # Deliberate ARCH-034 violation: application reaches into commons.infrastructure.
    (src / "sales" / "orders" / "application" / "service.py").write_text(
        "from commons.infrastructure import x\n"
    )

    layout = ProjectLayout.detect(tmp_path)
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-034"].outcome is Outcome.FAIL
    assert reports["ARCH-034"].findings


def test_given_a_modular_project__when_building__then_layer_contract_names_arch_007_and_008() -> (
    None
):
    layout = ProjectLayout.detect(MODULAR)
    ini = build_contracts(layout)
    assert "ARCH-007" in ini
    assert "ARCH-008" in ini


def test_given_contexts__when_building__then_independence_names_arch_013_and_025() -> None:
    layout = ProjectLayout.detect(MODULAR)
    ini = build_contracts(layout)
    independence = [b for b in ini.split("[importlinter:contract:") if b.startswith("ARCH-012")]
    assert independence, "independence contract missing"
    assert "ARCH-013" in independence[0]
    assert "ARCH-025" in independence[0]


def test_given_the_check__when_listing_rules__then_attributed_rules_are_claimed() -> None:
    for rid in ("ARCH-007", "ARCH-008", "ARCH-013", "ARCH-025"):
        assert rid in ImportContractsCheck.rule_ids


# --- Task 7: ARCH-009, ARCH-011, ARCH-014, ARCH-015, ARCH-017 -------------------


def test_given_a_bootstrap_dir__when_building__then_arch_017_forbids_importing_it(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "bootstrap").mkdir(parents=True)
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    ini = build_contracts(layout)
    assert "ARCH-017" in ini
    assert "bootstrap" in ini


def test_given_a_shared_kernel__when_building__then_arch_014_contract_is_emitted(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "shared_kernel").mkdir(parents=True)
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    ini = build_contracts(layout)
    assert "ARCH-014" in ini


def test_given_no_shared_kernel__when_building__then_no_arch_014_contract(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    assert "ARCH-014" not in build_contracts(layout)


def test_given_commons_types__when_building__then_arch_015_forbids_contexts() -> None:
    layout = ProjectLayout.detect(FIX / "good_project")
    ini = build_contracts(layout)
    assert "ARCH-015" in ini


def test_given_entrypoints__when_building__then_arch_009_and_011_contracts_exist() -> None:
    layout = ProjectLayout.detect(FIX / "good_project")
    ini = build_contracts(layout)
    assert "ARCH-009" in ini
    assert "ARCH-011" in ini


def test_given_no_shared_kernel_dir__when_checked__then_arch_014_skips_cleanly() -> None:
    # good_project has no shared_kernel/ anywhere -- ARCH-014's contract must
    # never be emitted for it, so the rule SKIPs (I3), not ERRORs or PASSes
    # vacuously.
    layout = ProjectLayout.detect(FIX / "good_project")
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-014"].outcome is Outcome.SKIP
    assert reports["ARCH-014"].findings == ()


def test_given_a_context_importing_bootstrap__when_checked__then_arch_017_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "bootstrap").mkdir(parents=True)
    (src / "bootstrap" / "__init__.py").write_text("container = 1\n", encoding="utf-8")
    app = src / "sales" / "orders" / "application"
    app.mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "__init__.py").write_text("", encoding="utf-8")
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "svc.py").write_text("from bootstrap import container\n", encoding="utf-8")
    (src / "sales" / "orders" / "domain").mkdir(parents=True)
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("", encoding="utf-8")

    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-017"].outcome is Outcome.FAIL


def test_given_a_shared_kernel_importing_a_context__when_checked__then_arch_014_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    sk = src / "shared_kernel"
    sk.mkdir(parents=True)
    (sk / "__init__.py").write_text("", encoding="utf-8")
    (sk / "leak.py").write_text("from sales.orders.domain import model\n", encoding="utf-8")
    domain_model = src / "sales" / "orders" / "domain" / "model"
    domain_model.mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (domain_model / "__init__.py").write_text("", encoding="utf-8")

    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-014"].outcome is Outcome.FAIL


def test_given_commons_types_importing_a_context__when_checked__then_arch_015_fails(
    tmp_path: Path,
) -> None:
    # commons.types is vendored under this project's own src/, so ARCH-015's
    # contract is emitted with an on-disk source-module import-linter can
    # actually parse a genuine violation into.
    src = tmp_path / "src"
    types_dir = src / "commons" / "types"
    types_dir.mkdir(parents=True)
    (src / "commons" / "__init__.py").write_text("", encoding="utf-8")
    (types_dir / "__init__.py").write_text("", encoding="utf-8")
    (types_dir / "leak.py").write_text("from sales.orders.domain import model\n", encoding="utf-8")
    domain_model = src / "sales" / "orders" / "domain" / "model"
    domain_model.mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "__init__.py").write_text("", encoding="utf-8")
    (src / "sales" / "orders" / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (domain_model / "__init__.py").write_text("", encoding="utf-8")

    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-015"].outcome is Outcome.FAIL


def test_given_an_entrypoint_importing_infrastructure__when_checked__then_arch_009_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    (src / "sales" / "__init__.py").parent.mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")

    orders = src / "sales" / "orders"
    (orders / "domain" / "model").mkdir(parents=True)
    (orders / "__init__.py").write_text("", encoding="utf-8")
    (orders / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (orders / "domain" / "model" / "__init__.py").write_text("", encoding="utf-8")
    (orders / "infrastructure").mkdir(parents=True)
    (orders / "infrastructure" / "__init__.py").write_text("class Repo: ...\n", encoding="utf-8")

    entrypoints = src / "sales" / "entrypoints"
    entrypoints.mkdir(parents=True)
    (entrypoints / "__init__.py").write_text("", encoding="utf-8")
    (entrypoints / "http.py").write_text(
        "from sales.orders.infrastructure import Repo\n", encoding="utf-8"
    )

    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ("sales",)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-009"].outcome is Outcome.FAIL


def test_given_an_entrypoint_importing_a_sibling__when_checked__then_arch_011_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    orders = src / "sales" / "orders"
    (orders / "domain" / "model").mkdir(parents=True)
    (src / "sales" / "__init__.py").write_text("", encoding="utf-8")
    (orders / "__init__.py").write_text("", encoding="utf-8")
    (orders / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (orders / "domain" / "model" / "__init__.py").write_text("", encoding="utf-8")

    entrypoints = src / "sales" / "entrypoints"
    entrypoints.mkdir(parents=True)
    (entrypoints / "__init__.py").write_text("", encoding="utf-8")
    (entrypoints / "http.py").write_text("value = 1\n", encoding="utf-8")
    # Deliberate ARCH-011 violation: one entrypoint module imports its sibling.
    (entrypoints / "cli.py").write_text(
        "from sales.entrypoints.http import value\n", encoding="utf-8"
    )

    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ("sales",)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in ImportContractsCheck().run(layout, catalog)}
    assert reports["ARCH-011"].outcome is Outcome.FAIL
