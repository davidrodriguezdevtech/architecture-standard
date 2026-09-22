from __future__ import annotations

from sales.orders.application.order import OrderService
from sales.orders.domain.model.ports import OrderRepository


def order_service(orders: OrderRepository) -> OrderService:
    """Wire OrderService from the repository singleton the bootstrap container built.

    ARCH-017 forbids any context module from importing bootstrap/ directly, so
    this provider does not import it either -- main.py, outside any context,
    builds the container and passes its singletons/factories in as arguments.
    entrypoints/web/order.py and entrypoints/cli.py get their wired OrderService
    from this module only, never by constructing it themselves.
    """
    return OrderService(orders)
