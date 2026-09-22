from __future__ import annotations

from dataclasses import dataclass

from sales.orders.domain.model.aggregate import Order
from sales.orders.domain.model.ports import OrderRepository
from sales.shared.ids import OrderId, UserId


@dataclass(frozen=True)
class CreateOrder:
    order_id: str
    user_id: str
    amount: float


class OrderService:
    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    def create_order(self, command: CreateOrder) -> None:
        self._orders.add(Order(id=OrderId(command.order_id), user_id=UserId(command.user_id), amount=command.amount))
