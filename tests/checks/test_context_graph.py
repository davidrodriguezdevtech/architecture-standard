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
