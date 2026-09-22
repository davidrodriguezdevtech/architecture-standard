from __future__ import annotations

from dataclasses import dataclass, field

from commons.ids import OrderId


@dataclass
class Order:
    id: OrderId
    _lines: list[str] = field(default_factory=list)

    def add_line(self, sku: str) -> None:
        self._lines.append(sku)
