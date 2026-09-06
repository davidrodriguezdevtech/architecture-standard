from __future__ import annotations

from sales.domain.model.aggregates import Order


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._store: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        self._store[order.id] = order

    def get(self, order_id: str) -> Order | None:
        return self._store.get(order_id)
