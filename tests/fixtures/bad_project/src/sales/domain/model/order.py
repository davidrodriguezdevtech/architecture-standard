from __future__ import annotations

from sales.infrastructure.order_repository import PostgresOrderRepository  # ARCH-001 violation


class Order:
    repository_type = PostgresOrderRepository
