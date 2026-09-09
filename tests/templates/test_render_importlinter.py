from __future__ import annotations

from pathlib import Path

from arch_standard.cli import main


def test_given_a_plain_project__when_render_importlinter__then_writes_a_dot_importlinter(
    tmp_path: Path,
) -> None:
    for rel in [
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")

    exit_code = main(["render-importlinter", str(tmp_path)])
    assert exit_code == 0

    ini = (tmp_path / ".importlinter").read_text(encoding="utf-8")
    assert "[importlinter]" in ini
    assert "ARCH-layers-sales-orders" in ini
