from __future__ import annotations

from dataclasses import dataclass, field

from sales.orders.adapters.order_repository import (  # ARCH-001 violation
    PostgresOrderRepository,
)


@dataclass
class Order:
    id: str
    lines: list[str] = field(default_factory=list)  # ARCH-019: public mutable collection

    repository_type = PostgresOrderRepository
