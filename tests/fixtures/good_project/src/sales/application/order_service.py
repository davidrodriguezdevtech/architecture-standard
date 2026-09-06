from __future__ import annotations

from sales.domain.model.aggregates import Order
from sales.domain.model.ports import OrderRepository
from sales.domain.model.value_objects import Money


class OrderService:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    def create_order(self, order_id: str) -> None:
        self._orders.add(Order(order_id=order_id, total=Money(amount=0, currency="USD")))

    def find_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
