from __future__ import annotations

from sales.orders.domain.model.aggregate import Order
from sales.orders.domain.model.ports import OrderRepository
from commons.ids import OrderId


class OrderService:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    def create_order(self, order_id: str) -> None:
        self._orders.add(Order(id=OrderId(order_id)))

    def add_line(self, order_id: str, sku: str) -> None:
        order = self._orders.get(OrderId(order_id))
        if order is not None:
            order.add_line(sku)

    def find_order(self, order_id: str) -> Order | None:
        return self._orders.get(OrderId(order_id))
