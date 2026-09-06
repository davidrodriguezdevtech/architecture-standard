from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemReserved:
    item_id: str
