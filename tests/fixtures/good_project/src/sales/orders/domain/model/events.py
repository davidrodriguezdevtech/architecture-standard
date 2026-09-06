from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderPlaced:
    order_id: str
    occurred_at: datetime


@dataclasses.dataclass(frozen=True)
class OrderCancelled:
    order_id: str
    occurred_at: datetime
