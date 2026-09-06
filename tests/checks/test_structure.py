from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.checks.structure import StructureCheck
from arch_standard.rules.catalog import Catalog

FIX = Path(__file__).parent.parent / "fixtures"
RULES = Path(__file__).parent.parent.parent / "rules"


def _reports(root: Path) -> dict[str, CheckReport]:
    return {
        r.rule_id: r for r in StructureCheck().run(ProjectLayout.detect(root), Catalog.load(RULES))
    }


def test_given_the_modular_fixture__when_checked__then_structure_rules_pass() -> None:
    reports = _reports(FIX / "modular_project")
    for rid in ("ARCH-047", "ARCH-048", "ARCH-051"):
        assert reports[rid].outcome is Outcome.PASS, rid


def test_given_a_context_level_application_dir__when_checked__then_arch_048_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    (root / "src/sales/entrypoints").mkdir(parents=True)
    (root / "src/sales/application").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-048"].outcome is Outcome.FAIL


def test_given_a_service_in_shared__when_checked__then_arch_047_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    (root / "src/sales/shared/helpers.py").write_text(
        "class UserService:\n    pass\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-047"].outcome is Outcome.FAIL


def test_given_a_reporting_method_on_a_repository_port__when_checked__then_arch_051_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (model / "ports.py").write_text(
        "from typing import Protocol\n"
        "class OrderRepository(Protocol):\n"
        "    def find_overdue_report(self) -> list[dict]: ...\n",
        encoding="utf-8",
    )
    assert _reports(root)["ARCH-051"].outcome is Outcome.FAIL
