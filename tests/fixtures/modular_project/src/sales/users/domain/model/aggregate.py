from __future__ import annotations

from dataclasses import dataclass, field

from sales.shared.ids import UserId


@dataclass
class User:
    id: UserId
    _emails: list[str] = field(default_factory=list)

    def add_email(self, email: str) -> None:
        self._emails.append(email)
