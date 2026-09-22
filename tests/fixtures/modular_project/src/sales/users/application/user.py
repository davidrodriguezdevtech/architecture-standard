from __future__ import annotations

from dataclasses import dataclass

from sales.shared.ids import UserId
from sales.users.domain.model.ports import UserRepository
from sales.users.domain.model.aggregate import User


@dataclass(frozen=True)
class RegisterUser:
    user_id: str


class UserService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def register_user(self, command: RegisterUser) -> None:
        self._users.add(User(id=UserId(command.user_id)))
