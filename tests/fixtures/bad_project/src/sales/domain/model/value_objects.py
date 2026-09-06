from __future__ import annotations

from dataclasses import dataclass


@dataclass  # ARCH-031: not frozen, no __post_init__
class Email:
    value: str
