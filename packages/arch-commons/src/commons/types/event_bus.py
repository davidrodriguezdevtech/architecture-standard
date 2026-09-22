from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from commons.types.events import DomainEvent


class EventBus(ABC):
    @abstractmethod
    def publish_all(self, events: Iterable[DomainEvent]) -> None: ...
