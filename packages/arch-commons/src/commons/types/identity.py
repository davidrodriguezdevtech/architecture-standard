from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityId:
    """Base for every project's typed aggregate IDs, e.g. ``class OrderId(EntityId): pass``."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("EntityId value must not be empty")

    def __str__(self) -> str:
        return self.value
