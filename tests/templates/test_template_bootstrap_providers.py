from __future__ import annotations

from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_bootstrap_and_providers_reference_order_service(
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

    providers = (dest / "src" / "sales" / "entrypoints" / "providers.py").read_text(
        encoding="utf-8"
    )
    # ARCH-017 forbids any module outside bootstrap/ (other than main.py) from
    # importing it, so providers.py receives the wired service as an argument
    # instead of building or importing the container itself.
    assert "def order_service(" in providers
    assert "service: OrderService" in providers
    assert "-> OrderService:" in providers
    assert "from bootstrap import build_container" not in providers
