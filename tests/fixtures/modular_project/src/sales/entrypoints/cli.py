from __future__ import annotations

from sales.orders.application.order_service import CreateOrder, OrderService


def create(service: OrderService, order_id: str) -> None:
    service.create_order(CreateOrder(order_id=order_id))
