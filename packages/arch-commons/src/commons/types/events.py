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
    events.

    Deliberately still a Protocol, not an ABC, unlike every other contract in
    ``commons/types/`` (Clock, UnitOfWork, EventBus, IdGenerator). Concrete
    domain events are independent, standalone ``@dataclass(frozen=True)``
    classes defined per aggregate module (ARCH-023) -- they are never written
    against this type and must not inherit from it. An ABC would force every
    event class in every project to explicitly subclass a commons type just to
    satisfy ``UnitOfWork.collect_new_events``'s type hint; a Protocol lets any
    dataclass shaped like this one satisfy it structurally, with zero coupling."""

    @property
    def occurred_at(self) -> datetime: ...
