from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session, sessionmaker

from commons.types.events import DomainEvent


class SqlAlchemyUnitOfWork:
    """Reference UnitOfWork backed by a SQLAlchemy Session (spec Section 7.2).

    Events are captured once during ``commit()`` (before session close) and cached
    in ``_collected_events``. ``track()`` is a no-op: the session's own identity
    map already knows every object added to or loaded through it, eliminating the
    need for explicit tracking. The session's new, dirty, and identity_map
    snapshots are scanned at commit time to drain pending events.
    """

    def __init__(self, session_factory: sessionmaker) -> None:  # type: ignore[type-arg]
        self.session: Session = session_factory()
        self._committed = False
        self._collected_events: list[DomainEvent] = []

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._committed = False
        self._collected_events = []
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._committed:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()
        self._committed = True
        self._collect_and_clear_events()

    def rollback(self) -> None:
        self.session.rollback()

    def track(self, aggregate: object) -> None:
        """No-op: the session's identity map tracks membership implicitly."""

    def _collect_and_clear_events(self) -> None:
        """Collect events from tracked aggregates and clear them."""
        seen_ids: set[int] = set()
        candidates: list[object] = []
        for aggregate in self.session.new:
            if id(aggregate) not in seen_ids:
                candidates.append(aggregate)
                seen_ids.add(id(aggregate))
        for aggregate in self.session.dirty:
            if id(aggregate) not in seen_ids:
                candidates.append(aggregate)
                seen_ids.add(id(aggregate))
        for aggregate in self.session.identity_map.values():
            if id(aggregate) not in seen_ids:
                candidates.append(aggregate)
                seen_ids.add(id(aggregate))
        for aggregate in candidates:
            pending = getattr(aggregate, "pending_events", None)
            if not pending:
                continue
            self._collected_events.extend(pending)
            clear = getattr(aggregate, "clear_pending_events", None)
            if clear is not None:
                clear()

    def collect_new_events(self) -> Iterable[DomainEvent]:
        """Return events captured during the last ``commit()``.

        A copy, so a caller mutating the result cannot corrupt UoW state."""
        return list(self._collected_events)
