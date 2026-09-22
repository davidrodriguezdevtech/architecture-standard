from __future__ import annotations

from sales.orders.domain.model.aggregate import Order
from sales.orders.domain.model.ports import OrderRepository
from sales.shared.ids import OrderId


class OrderService:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    def create_order(self, order_id: str) -> None:
        self._orders.add(Order(id=OrderId(order_id)))
