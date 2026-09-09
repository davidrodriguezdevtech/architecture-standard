from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from commons.infrastructure.in_memory_event_bus import InMemoryEventBus
from commons.infrastructure.in_memory_unit_of_work import InMemoryUnitOfWork
from commons.infrastructure.system_clock import SystemClock
from commons.infrastructure.uuid7_id_generator import Uuid7IdGenerator


@dataclass
class _Widget:
    id: str
    pending_events: list[object] = field(default_factory=list)

    def clear_pending_events(self) -> None:
        self.pending_events.clear()


def test_given_committed_uow__when_collect_new_events__then_returns_tracked_pending_events() -> (
    None
):  # noqa: E501
    widget = _Widget(id="w-1")
    widget.pending_events.append("WidgetCreated")
    uow = InMemoryUnitOfWork()
    with uow:
        uow.track(widget)
        uow.commit()
    # plain strings stand in for events here; only pass-through behavior is under test
    assert list(uow.collect_new_events()) == ["WidgetCreated"]  # type: ignore[comparison-overlap]


def test_given_uncommitted_uow__when_exit__then_rollback_clears_tracked() -> None:
    widget = _Widget(id="w-1")
    widget.pending_events.append("WidgetCreated")
    uow = InMemoryUnitOfWork()
    with uow:
        uow.track(widget)
        # no commit() -- __exit__ must roll back
    assert list(uow.collect_new_events()) == []


def test_given_in_memory_event_bus__when_publish_all__then_records_events() -> None:
    bus = InMemoryEventBus()
    # plain strings stand in for events here; the bus only records what it is handed
    bus.publish_all(["WidgetCreated"])  # type: ignore[list-item]
    assert bus.published == ["WidgetCreated"]  # type: ignore[comparison-overlap]


def test_given_system_clock__when_now__then_returns_a_timezone_aware_datetime() -> None:
    now = SystemClock().now()
    assert isinstance(now, datetime)
    assert now.tzinfo is UTC


def test_given_uuid7_id_generator__when_new_id__then_returns_a_valid_version_7_uuid() -> None:  # noqa: E501
    generator = Uuid7IdGenerator()
    new_id = generator.new_id()
    parsed = uuid.UUID(new_id)
    assert parsed.version == 7


def test_given_uuid7_id_generator__when_called_twice__then_ids_differ() -> None:
    generator = Uuid7IdGenerator()
    assert generator.new_id() != generator.new_id()
