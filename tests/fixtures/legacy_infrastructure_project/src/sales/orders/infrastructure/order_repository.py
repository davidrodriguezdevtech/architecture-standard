from __future__ import annotations

from sales.orders.domain.model.aggregate import Order
from sales.shared.ids import OrderId


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        self._store[order.id.value] = order

    def get(self, order_id: OrderId) -> Order | None:
        return self._store.get(order_id.value)
