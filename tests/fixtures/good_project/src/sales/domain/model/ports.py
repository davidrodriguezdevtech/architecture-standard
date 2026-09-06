from __future__ import annotations

from typing import Protocol

from sales.domain.model.aggregates import Order


class OrderRepository(Protocol):
    def add(self, order: Order) -> None: ...

    def get(self, order_id: str) -> Order | None: ...
