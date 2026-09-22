from __future__ import annotations

from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_bootstrap_references_order_service(
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

    bootstrap = (dest / "src" / "bootstrap" / "__init__.py").read_text(encoding="utf-8")
    assert "from sales.orders.application.order import" in bootstrap
    assert "OrderService" in bootstrap
    assert "InMemoryUnitOfWork" in bootstrap and "SystemClock" in bootstrap

    # There is no providers.py: an entrypoint owns its own wiring getter,
    # configured by main.py at startup (ARCH-009/017) -- nothing for the
    # template to scaffold until a real entrypoint file exists.
    assert not (dest / "src" / "sales" / "entrypoints" / "providers.py").exists()
