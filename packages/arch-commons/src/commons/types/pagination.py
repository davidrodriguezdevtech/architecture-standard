from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page[T]:
    items: tuple[T, ...]
    total: int
