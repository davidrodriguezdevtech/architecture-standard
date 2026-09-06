from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderPlaced:
    order_id: str
    occurred_at: datetime
