from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from commons.types.events import DomainEvent


class EventBus(Protocol):
    def publish_all(self, events: Iterable[DomainEvent]) -> None: ...
