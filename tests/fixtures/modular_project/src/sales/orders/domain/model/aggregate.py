from __future__ import annotations

from dataclasses import dataclass

from commons.ids import OrderId, UserId


@dataclass
class Order:
    id: OrderId
    user_id: UserId
    amount: float

    def add_amount(self, amount: float) -> None:
        self.amount += amount
