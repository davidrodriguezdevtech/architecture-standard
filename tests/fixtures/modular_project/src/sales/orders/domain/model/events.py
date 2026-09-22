from __future__ import annotations

import dataclasses
from datetime import datetime

from commons.ids import OrderId, UserId


@dataclasses.dataclass(frozen=True)
class OrderCreated:
    order_id: OrderId
    user_id: UserId
    occurred_at: datetime
