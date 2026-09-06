from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import Outcome, ProjectLayout
from arch_standard.checks.context_graph import ContextGraphCheck, find_cycle
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _report(root: Path):  # type: ignore[no-untyped-def]
    return ContextGraphCheck().run(ProjectLayout.detect(root), Catalog.load(RULES))[0]


def test_given_an_acyclic_graph__when_searching__then_no_cycle() -> None:
    assert find_cycle({"a": ["b"], "b": []}) is None


def test_given_a_cyclic_graph__when_searching__then_the_cycle_is_returned() -> None:
    cycle = find_cycle({"a": ["b"], "b": ["a"]})
    assert cycle is not None
    assert set(cycle) == {"a", "b"}


def test_given_a_diamond_shaped_graph__when_searching__then_no_cycle() -> None:
    """a->b, a->c, b->d, c->d converges but is acyclic; must not false-positive."""
    graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    assert find_cycle(graph) is None


def test_given_the_modular_fixture__when_checked__then_arch_050_passes() -> None:
    assert _report(FIX / "modular_project").outcome is Outcome.PASS


def test_given_two_contexts_and_no_manifest__when_checked__then_arch_050_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert any("contexts.toml" in f.message for f in r.findings)


def test_given_a_cyclic_manifest__when_checked__then_arch_050_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    (root / "contexts.toml").write_text(
        '[contexts.sales]\ndepends_on = ["billing"]\n[contexts.billing]\ndepends_on = ["sales"]\n',
        encoding="utf-8",
    )
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert any("cycle" in f.message.lower() for f in r.findings)


def test_given_one_context_and_no_manifest__when_checked__then_arch_050_skips(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    (root / "src/sales/entrypoints").mkdir(parents=True)
    assert _report(root).outcome is Outcome.SKIP


def test_given_a_syntactically_invalid_manifest__when_checked__then_arch_050_fails_without_crashing(
    tmp_path: Path,
) -> None:
    # I5: a TOML syntax error must not raise out of ContextGraphCheck.run and
    # abort the whole check invocation — it must FAIL ARCH-050 with the parse
    # error in the message.
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    (root / "contexts.toml").write_text("[contexts.sales\ndepends_on = [\n", encoding="utf-8")
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert r.findings
    assert "could not be parsed" in r.findings[0].message


def test_given_a_wrong_shaped_manifest_entry__when_checked__then_arch_050_fails_without_crashing(
    tmp_path: Path,
) -> None:
    # I5: a wrong-shaped entry (a plain string instead of a table) raises
    # AttributeError from ``cfg.get(...)`` inside _load_manifest — must FAIL,
    # not crash the run.
    root = tmp_path / "p"
    for ctx in ("sales", "billing"):
        (root / f"src/{ctx}/entrypoints").mkdir(parents=True)
    (root / "contexts.toml").write_text('[contexts]\nsales = "nope"\n', encoding="utf-8")
    r = _report(root)
    assert r.outcome is Outcome.FAIL
    assert r.findings
    assert "could not be parsed" in r.findings[0].message


def test_given_a_malformed_manifest__when_checked_via_cli__then_other_rules_still_report(
    tmp_path: Path,
) -> None:
    # I5, critically: the malformed manifest must not abort Report.collect —
    # unrelated rules must still appear in the same arch-standard check run.
    from arch_standard.checks import all_checks
    from arch_standard.checks.base import ProjectLayout
    from arch_standard.report import Report

    root = tmp_path / "p"
    (root / "src/sales/orders/domain/model").mkdir(parents=True)
    (root / "src/sales/orders/domain/model/order.py").write_text(
        "class Order: pass\n", encoding="utf-8"
    )
    (root / "src/billing/invoices/domain/model").mkdir(parents=True)
    (root / "src/billing/invoices/domain/model/invoice.py").write_text(
        "class Invoice: pass\n", encoding="utf-8"
    )
    (root / "contexts.toml").write_text("not even close to toml [[[", encoding="utf-8")

    layout = ProjectLayout.detect(root)
    catalog = Catalog.load(RULES)
    report = Report.collect(layout, catalog, all_checks())
    by_id = {r.rule_id: r for r in report.reports}
    assert by_id["ARCH-050"].outcome is Outcome.FAIL
    # Unrelated rules (e.g. ARCH-049, one-aggregate-per-module) still ran.
    assert "ARCH-049" in by_id
