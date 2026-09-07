from __future__ import annotations

from collections.abc import Iterable

from commons.types.events import DomainEvent


class InMemoryUnitOfWork:
    """Dict-backed UnitOfWork for tests and template projects with no real
    store yet. Repositories call ``track()`` explicitly on every load and
    store -- there is no session to infer it from."""

    def __init__(self) -> None:
        self._tracked: dict[int, object] = {}
        self._committed = False

    def __enter__(self) -> InMemoryUnitOfWork:
        self._committed = False
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._tracked.clear()

    def track(self, aggregate: object) -> None:
        self._tracked[id(aggregate)] = aggregate

    def collect_new_events(self) -> Iterable[DomainEvent]:
        events: list[DomainEvent] = []
        for aggregate in self._tracked.values():
            pending = getattr(aggregate, "pending_events", None)
            if not pending:
                continue
            events.extend(pending)
            clear = getattr(aggregate, "clear_pending_events", None)
            if clear is not None:
                clear()
        return events
