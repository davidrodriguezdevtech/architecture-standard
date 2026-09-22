from __future__ import annotations

from sales.orders.application.order import OrderService


def create_order(service: OrderService, order_id: str) -> None:
    service.create_order(order_id)


def add_line(service: OrderService, order_id: str, sku: str) -> None:
    service.add_line(order_id, sku)
