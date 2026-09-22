from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime


def test_given_an_event_bus_implementation__when_publish_all_called__then_no_error() -> None:
    from commons.types.event_bus import EventBus
    from commons.types.events import DomainEvent

    @dataclass(frozen=True)
    class Recorded(EventBus):
        published: list[object]

        def publish_all(self, events: Iterable[DomainEvent]) -> None:
            self.published.extend(events)

    published: list[object] = []
    bus: EventBus = Recorded(published=published)

    @dataclass(frozen=True)
    class WidgetCreated:
        occurred_at: datetime

    bus.publish_all([WidgetCreated(occurred_at=datetime.now(UTC))])
    assert len(published) == 1


def test_given_an_id_generator_implementation__when_new_id_called__then_returns_a_string() -> None:
    from commons.types.id_generator import IdGenerator

    class FixedIdGenerator(IdGenerator):
        def new_id(self) -> str:
            return "fixed-id"

    generator: IdGenerator = FixedIdGenerator()
    assert generator.new_id() == "fixed-id"
