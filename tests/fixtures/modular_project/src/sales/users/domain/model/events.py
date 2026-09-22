from __future__ import annotations

import dataclasses
from datetime import datetime

from commons.ids import UserId


@dataclasses.dataclass(frozen=True)
class UserRegistered:
    user_id: UserId
    occurred_at: datetime
