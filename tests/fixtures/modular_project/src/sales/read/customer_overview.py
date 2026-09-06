from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerOverview:
    user_id: str
    order_count: int


def load_customer_overview(user_id: str) -> CustomerOverview:
    return CustomerOverview(user_id=user_id, order_count=0)
