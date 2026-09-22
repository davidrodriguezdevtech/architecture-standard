from __future__ import annotations

from abc import ABC, abstractmethod

from commons.ids import UserId
from sales.users.domain.model.aggregate import User


class UserRepository(ABC):
    @abstractmethod
    def get(self, user_id: UserId) -> User: ...
    @abstractmethod
    def add(self, user: User) -> None: ...
