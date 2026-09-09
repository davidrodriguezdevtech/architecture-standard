from __future__ import annotations

import py_compile
from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_application_and_infrastructure_files_compile(
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

    service_path = dest / "src/sales/orders/application/order_service.py"
    repository_path = dest / "src/sales/orders/infrastructure/order_repository.py"
    py_compile.compile(str(service_path), doraise=True)
    py_compile.compile(str(repository_path), doraise=True)

    service_py = service_path.read_text(encoding="utf-8")
    assert "class CreateOrder:" in service_py
    assert "class OrderService:" in service_py
    assert "def create_order(" in service_py
    assert "command: CreateOrder" in service_py
    assert "-> OrderId:" in service_py

    repository_py = repository_path.read_text(encoding="utf-8")
    assert "class InMemoryOrderRepository:" in repository_py
    assert "Uuid7IdGenerator" in repository_py
