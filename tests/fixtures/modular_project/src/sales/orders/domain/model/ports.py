from __future__ import annotations

from abc import ABC, abstractmethod

from sales.orders.domain.model.aggregate import Order
from sales.shared.ids import OrderId


class OrderRepository(ABC):
    @abstractmethod
    def get(self, order_id: OrderId) -> Order: ...
    @abstractmethod
    def add(self, order: Order) -> None: ...
