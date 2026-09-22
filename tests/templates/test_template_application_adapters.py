from __future__ import annotations

import py_compile
import re
from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_application_and_adapters_files_compile(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    service_path = dest / "src/sales/orders/application/order.py"
    repository_path = dest / "src/sales/orders/adapters/order_repository.py"
    py_compile.compile(str(service_path), doraise=True)
    py_compile.compile(str(repository_path), doraise=True)

    service_py = service_path.read_text(encoding="utf-8")
    assert "class CreateOrder:" in service_py
    assert "class OrderService:" in service_py
    assert "def create_order(" in service_py
    assert "command: CreateOrder" in service_py
    assert "-> OrderId:" in service_py

    repository_py = repository_path.read_text(encoding="utf-8")
    assert "class InMemoryOrderRepository(OrderRepository):" in repository_py
    assert "Uuid7IdGenerator" in repository_py


_OLD_LAYER = re.compile(r"\.infrastructure\b|\binfrastructure/")


def test_given_the_template_tree__when_scanned__then_no_infrastructure_layer_remains() -> None:
    offenders: list[str] = []
    for path in TEMPLATE_ROOT.rglob("*"):
        relative = path.relative_to(TEMPLATE_ROOT)
        if "infrastructure" in relative.parts:
            offenders.append(f"path: {relative}")
        if path.is_file() and _OLD_LAYER.search(path.read_text(encoding="utf-8")):
            offenders.append(f"content: {relative}")
    assert offenders == []
