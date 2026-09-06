from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EventEnvelope:
    correlation_id: str
    causation_id: str
    occurred_at: datetime
    event_type: str
    event_version: int
    payload: dict[str, object]
