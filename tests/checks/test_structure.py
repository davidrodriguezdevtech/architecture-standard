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


def test_given_a_pricing_service_in_shared_services_file__when_checked__then_arch_047_passes(
    tmp_path: Path,
) -> None:
    # C2: <context>/shared/services.py is the documented home for domain
    # services spanning aggregates; a non-mutating *Service class there is
    # exactly the pattern the standard names it for.
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    (root / "src/sales/shared/services.py").write_text(
        "class PricingService:\n    def quote(self, order): return order\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-047"].outcome is Outcome.PASS


def test_given_a_service_named_class_outside_services_py__when_checked__then_arch_047_fails(
    tmp_path: Path,
) -> None:
    # The name-suffix carve-out is narrow to services.py; every other file in
    # shared/ keeps the full *Service/*Repository ban.
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    (root / "src/sales/shared/ids.py").write_text(
        "class PricingService:\n    def quote(self, order): return order\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-047"].outcome is Outcome.FAIL


def test_given_a_mutating_class_in_shared_services_file__when_checked__then_arch_047_fails(
    tmp_path: Path,
) -> None:
    # The mutation check still applies inside services.py: a stateful "service"
    # hiding an aggregate is still wrong there.
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    (root / "src/sales/shared/services.py").write_text(
        "class PricingPolicy:\n    def bump(self):\n        self.n = 1\n", encoding="utf-8"
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


def test_given_a_repository_method_returning_its_own_aggregate__when_checked__then_arch_051_passes(
    tmp_path: Path,
) -> None:
    # C1: `list[Order]` on OrderRepository inside the orders module is
    # legitimate query-by-identity-adjacent retrieval, not a reporting query.
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (model / "ports.py").write_text(
        "from typing import Protocol\n"
        "from sales.orders.domain.model.order import Order\n"
        "class OrderRepository(Protocol):\n"
        "    def list_for_customer(self, cid: str) -> list[Order]: ...\n",
        encoding="utf-8",
    )
    assert _reports(root)["ARCH-051"].outcome is Outcome.PASS


def test_given_a_repository_method_returning_a_report_row_type__when_checked__then_arch_051_fails(
    tmp_path: Path,
) -> None:
    # C1: the element type differs from the module's aggregate (Order), so this
    # must stay FAIL even though it is a resolvable, non-dict element type.
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (model / "ports.py").write_text(
        "from typing import Protocol\n"
        "class OrderRepository(Protocol):\n"
        "    def list_for_customer(self, cid: str) -> list[SomeReportRow]: ...\n",
        encoding="utf-8",
    )
    assert _reports(root)["ARCH-051"].outcome is Outcome.FAIL
