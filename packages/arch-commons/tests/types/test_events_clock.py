from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def test_given_a_frozen_dataclass_with_occurred_at__when_checked__then_is_a_domain_event() -> None:
    from commons.types.events import DomainEvent

    @dataclass(frozen=True)
    class WidgetCreated:
        widget_id: str
        occurred_at: datetime

    event = WidgetCreated(widget_id="w-1", occurred_at=datetime.now(UTC))
    assert isinstance(event, DomainEvent)


def test_given_an_object_without_occurred_at__when_checked__then_is_not_a_domain_event() -> None:
    from commons.types.events import DomainEvent

    assert not isinstance(object(), DomainEvent)


def test_given_a_clock_implementation__when_now_called__then_returns_a_datetime() -> None:
    from commons.types.clock import Clock

    class FixedClock(Clock):
        def now(self) -> datetime:
            return datetime(2026, 1, 1, tzinfo=UTC)

    clock: Clock = FixedClock()
    assert clock.now() == datetime(2026, 1, 1, tzinfo=UTC)
