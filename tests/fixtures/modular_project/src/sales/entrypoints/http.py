from __future__ import annotations

from sales.read.customer_overview import load_customer_overview
from sales.users.application.user_service import RegisterUser, UserService


def register(service: UserService, user_id: str) -> None:
    service.register_user(RegisterUser(user_id=user_id))


def overview(user_id: str) -> object:
    return load_customer_overview(user_id)
