from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.checks.structure import StructureCheck
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

FIX = Path(__file__).parent.parent / "fixtures"
RULES = packaged_rules_dir()


def _reports(root: Path) -> dict[str, CheckReport]:
    return {
        r.rule_id: r for r in StructureCheck().run(ProjectLayout.detect(root), Catalog.load(RULES))
    }


def test_given_the_modular_fixture__when_checked__then_structure_rules_pass() -> None:
    reports = _reports(FIX / "modular_project")
    for rid in ("ARCH-037", "ARCH-047", "ARCH-048", "ARCH-051", "ARCH-054", "ARCH-055"):
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


def test_given_a_legacy_infrastructure_layer__when_checked__then_arch_048_fails_with_rename() -> (
    None
):
    # The 0.2.0 clean break: `adapters/` is the only name for the outbound-adapter
    # layer. A module still on the pre-0.2.0 `infrastructure/` name simply
    # disappears from every layer contract, so without this check the whole
    # project passed silently (the spec's "fails the normal structure checks"
    # was false). ARCH-048 is the catalog's layer-package placement rule, so it
    # carries the finding -- loudly, with the rename in the message.
    report = _reports(FIX / "legacy_infrastructure_project")["ARCH-048"]
    assert report.outcome is Outcome.FAIL
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule_id == "ARCH-048"
    assert "adapters/" in finding.message
    assert "sales/orders" in finding.message.replace("\\", "/")


def test_given_an_adapters_layer__when_checked__then_arch_048_passes() -> None:
    # The mirror of the test above: the migrated shape must stay clean, so the
    # legacy-name finding cannot be a blanket FAIL for every module.
    assert _reports(FIX / "good_project")["ARCH-048"].outcome is Outcome.PASS


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


def test_given_an_async_reporting_method_on_a_repository_port__when_checked__then_arch_051_fails(
    tmp_path: Path,
) -> None:
    # I6: ast.AsyncFunctionDef is not a subclass of ast.FunctionDef, so an
    # `async def` query method was silently invisible to ARCH-051 before —
    # a very common shape in modern async repositories.
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (model / "ports.py").write_text(
        "from typing import Protocol\n"
        "class OrderRepository(Protocol):\n"
        "    async def find_by_customer(self, cid: str) -> list[dict]: ...\n",
        encoding="utf-8",
    )
    assert _reports(root)["ARCH-051"].outcome is Outcome.FAIL


def test_given_an_async_mutating_method_in_shared__when_checked__then_arch_047_fails(
    tmp_path: Path,
) -> None:
    # I6: an async method mutating self was invisible to ARCH-047's mutation
    # check before.
    root = tmp_path / "p"
    (root / "src/sales/shared").mkdir(parents=True)
    (root / "src/sales/users/domain/model").mkdir(parents=True)
    (root / "src/sales/users/domain/model/user.py").write_text(
        "class User: pass\n", encoding="utf-8"
    )
    (root / "src/sales/shared/helpers.py").write_text(
        "class Counter:\n    async def bump(self):\n        self.n = 1\n", encoding="utf-8"
    )
    assert _reports(root)["ARCH-047"].outcome is Outcome.FAIL


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


def test_given_entrypoints_without_providers__when_checked__then_arch_037_fails(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src" / "sales"
    (src / "entrypoints").mkdir(parents=True)
    (src / "entrypoints" / "http.py").write_text("handler = 1\n", encoding="utf-8")
    (src / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.FAIL


def test_given_entrypoints_with_providers__when_checked__then_arch_037_passes(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src" / "sales"
    (src / "entrypoints").mkdir(parents=True)
    (src / "entrypoints" / "providers.py").write_text("svc = 1\n", encoding="utf-8")
    (src / "orders" / "domain").mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.PASS


def test_given_no_entrypoints__when_checked__then_arch_037_skips(tmp_path: Path) -> None:
    src = tmp_path / "src" / "sales" / "orders" / "domain"
    src.mkdir(parents=True)
    layout = ProjectLayout.detect(tmp_path)
    catalog = Catalog.load(packaged_rules_dir())
    reports = {r.rule_id: r for r in StructureCheck().run(layout, catalog)}
    assert reports["ARCH-037"].outcome is Outcome.SKIP


def test_given_a_domain_services_file__when_checked__then_arch_054_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (root / "src/sales/orders/domain/services.py").write_text(
        "class PricingCalculator: pass\n", encoding="utf-8"
    )
    report = _reports(root)["ARCH-054"]
    assert report.outcome is Outcome.WARN
    assert "services.py" in report.findings[0].message


def test_given_a_correctly_named_single_domain_service__when_checked__then_arch_054_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    services = root / "src/sales/orders/domain/services"
    services.mkdir(parents=True)
    (services / "order.py").write_text("class PricingCalculator: pass\n", encoding="utf-8")
    assert _reports(root)["ARCH-054"].outcome is Outcome.PASS


def test_given_a_misnamed_single_domain_service__when_checked__then_arch_054_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    services = root / "src/sales/orders/domain/services"
    services.mkdir(parents=True)
    (services / "pricing.py").write_text("class PricingCalculator: pass\n", encoding="utf-8")
    report = _reports(root)["ARCH-054"]
    assert report.outcome is Outcome.WARN
    assert "order.py" in report.findings[0].message


def test_given_two_descriptively_named_domain_services__when_checked__then_arch_054_passes(
    tmp_path: Path,
) -> None:
    # 2+ services are exempt from the aggregate-name check -- each keeps its own
    # descriptive name.
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    services = root / "src/sales/orders/domain/services"
    services.mkdir(parents=True)
    (services / "pricing.py").write_text("class PricingCalculator: pass\n", encoding="utf-8")
    (services / "discounts.py").write_text("class DiscountPolicy: pass\n", encoding="utf-8")
    assert _reports(root)["ARCH-054"].outcome is Outcome.PASS


def test_given_a_camel_case_aggregate_name__when_checked__then_arch_054_expects_snake_case(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/accounting/po_lines/domain/model"
    model.mkdir(parents=True)
    (model / "aggregate.py").write_text("class PoLine: pass\n", encoding="utf-8")
    services = root / "src/accounting/po_lines/domain/services"
    services.mkdir(parents=True)
    (services / "po_line.py").write_text("class Validator: pass\n", encoding="utf-8")
    assert _reports(root)["ARCH-054"].outcome is Outcome.PASS


def test_given_a_package_dir_with_no_init_py__when_checked__then_arch_055_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    report = _reports(root)["ARCH-055"]
    assert report.outcome is Outcome.WARN
    assert len(report.findings) > 0


def test_given_init_py_at_every_level__when_checked__then_arch_055_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    for d in (
        root / "src/sales",
        root / "src/sales/orders",
        root / "src/sales/orders/domain",
        model,
    ):
        (d / "__init__.py").write_text("", encoding="utf-8")
    assert _reports(root)["ARCH-055"].outcome is Outcome.PASS


def test_given_a_non_python_directory__when_checked__then_arch_055_ignores_it(
    tmp_path: Path,
) -> None:
    # A directory with no .py files anywhere inside it is not a package and
    # is not expected to carry an __init__.py.
    root = tmp_path / "p"
    model = root / "src/sales/orders/domain/model"
    model.mkdir(parents=True)
    (model / "order.py").write_text("class Order: pass\n", encoding="utf-8")
    (root / "src/sales/orders/static").mkdir(parents=True)
    (root / "src/sales/orders/static" / "notes.txt").write_text("x", encoding="utf-8")
    report = _reports(root)["ARCH-055"]
    assert not any("static" in f.path for f in report.findings)
