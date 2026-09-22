from __future__ import annotations

import py_compile
from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT

_DOMAIN_MODEL = "src/sales/orders/domain/model"


def test_given_defaults__when_copied__then_domain_layer_files_compile_and_have_expected_names(
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

    for filename in ("aggregate.py", "exceptions.py", "events.py", "ports.py"):
        path = dest / _DOMAIN_MODEL / filename
        py_compile.compile(str(path), doraise=True)

    order_py = (dest / _DOMAIN_MODEL / "aggregate.py").read_text(encoding="utf-8")
    assert "class OrderId(EntityId):" in order_py
    assert "class Order:" in order_py
    assert "def create(" in order_py

    exceptions_py = (dest / _DOMAIN_MODEL / "exceptions.py").read_text(encoding="utf-8")
    assert "class OrderNotFound(DomainError):" in exceptions_py

    events_py = (dest / _DOMAIN_MODEL / "events.py").read_text(encoding="utf-8")
    assert "class OrderCreated:" in events_py

    ports_py = (dest / _DOMAIN_MODEL / "ports.py").read_text(encoding="utf-8")
    assert "class OrderRepository(Protocol):" in ports_py
