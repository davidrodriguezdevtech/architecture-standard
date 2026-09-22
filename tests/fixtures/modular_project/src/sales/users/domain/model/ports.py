from __future__ import annotations

from typing import Protocol

from sales.shared.ids import UserId
from sales.users.domain.model.aggregate import User


class UserRepository(Protocol):
    def get(self, user_id: UserId) -> User: ...
    def add(self, user: User) -> None: ...
