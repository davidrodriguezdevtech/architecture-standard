from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class DomainEvent(Protocol):
    """The minimal structural shape ``UnitOfWork.collect_new_events`` needs
    (spec Section 7.2). Concrete events (frozen, past-tense, ARCH-023) live in
    each aggregate module's own domain/model/events.py, never here.

    ``occurred_at`` is declared read-only: a plain attribute annotation would
    demand a *settable* variable, which a frozen event (ARCH-023) can never
    offer, so the standard's own Protocol would reject the standard's own
    events."""

    @property
    def occurred_at(self) -> datetime: ...
