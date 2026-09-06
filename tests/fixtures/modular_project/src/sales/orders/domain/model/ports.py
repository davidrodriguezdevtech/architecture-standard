from __future__ import annotations

from typing import Protocol

from sales.orders.domain.model.order import Order
from sales.shared.ids import OrderId


class OrderRepository(Protocol):
    def get(self, order_id: OrderId) -> Order: ...
    def add(self, order: Order) -> None: ...
