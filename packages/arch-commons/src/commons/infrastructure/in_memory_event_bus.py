from __future__ import annotations

from collections.abc import Iterable

from commons.types.events import DomainEvent


class InMemoryEventBus:
    """No real broker wired yet -- records what was published, for tests and
    for template projects before a broker exists."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def publish_all(self, events: Iterable[DomainEvent]) -> None:
        self.published.extend(events)
