from __future__ import annotations

from sales.orders.application.order import OrderService


def find_order(service: OrderService, order_id: str) -> object:
    return service.find_order(order_id)
