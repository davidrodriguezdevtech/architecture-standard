from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sales.domain.model.events import OrderPlaced
from sales.domain.model.value_objects import Money


@dataclass
class Order:
    order_id: str
    total: Money
    events: list[OrderPlaced] = field(default_factory=list)

    def place(self, occurred_at: datetime) -> None:
        self.events.append(OrderPlaced(order_id=self.order_id, occurred_at=occurred_at))
