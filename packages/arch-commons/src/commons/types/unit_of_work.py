from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from commons.types.events import DomainEvent


class UnitOfWork(ABC):
    """Store-agnostic — owns the transaction and domain-event collection,
    says nothing about a specific database (spec Section 7.2)."""

    @abstractmethod
    def __enter__(self) -> UnitOfWork: ...
    @abstractmethod
    def __exit__(self, *exc: object) -> None: ...
    @abstractmethod
    def commit(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
    @abstractmethod
    def track(self, aggregate: object) -> None: ...
    @abstractmethod
    def collect_new_events(self) -> Iterable[DomainEvent]: ...
