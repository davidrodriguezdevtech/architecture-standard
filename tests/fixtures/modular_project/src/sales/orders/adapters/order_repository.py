from __future__ import annotations

from sales.orders.domain.model.aggregate import Order
from sales.orders.domain.model.ports import OrderRepository
from sales.shared.ids import OrderId


class InMemoryOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def get(self, order_id: OrderId) -> Order:
        return self._store[order_id.value]

    def add(self, order: Order) -> None:
        self._store[order.id.value] = order
