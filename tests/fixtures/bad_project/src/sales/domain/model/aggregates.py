from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Order:
    id: str
    lines: list[str] = field(default_factory=list)  # ARCH-019: public mutable collection
