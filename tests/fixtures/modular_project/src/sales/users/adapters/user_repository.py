from __future__ import annotations

from commons.ids import UserId
from sales.users.domain.model.aggregate import User
from sales.users.domain.model.ports import UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._store: dict[str, User] = {}

    def get(self, user_id: UserId) -> User:
        return self._store[user_id.value]

    def add(self, user: User) -> None:
        self._store[user.id.value] = user
