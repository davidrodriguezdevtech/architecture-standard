from __future__ import annotations

from sales.orders.application.order_service import OrderService
from sales.orders.domain.model.ports import OrderRepository
from sales.users.application.user_service import UserService
from sales.users.domain.model.ports import UserRepository


def order_service(orders: OrderRepository) -> OrderService:
    """Wire OrderService from the repository singleton the bootstrap container built.

    entrypoints/cli.py and entrypoints/http.py get their wired OrderService
    from this module only, never by constructing it themselves.
    """
    return OrderService(orders)


def user_service(users: UserRepository) -> UserService:
    """Wire UserService from the repository singleton the bootstrap container built.

    entrypoints/http.py gets its wired UserService from this module only,
    never by constructing it directly.
    """
    return UserService(users)
