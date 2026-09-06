from __future__ import annotations

from typing import Protocol

from sales.orders.domain.model.order import Order
from sales.shared.ids import OrderId


class OrderRepository(Protocol):
    def add(self, order: Order) -> None: ...

    def get(self, order_id: OrderId) -> Order | None: ...
