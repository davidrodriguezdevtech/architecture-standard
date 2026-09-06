from __future__ import annotations

from dataclasses import dataclass

from commons.types.envelope import EventEnvelope  # noqa: F401


@dataclass(frozen=True)
class OrderPlacedPublished:
    order_id: str
