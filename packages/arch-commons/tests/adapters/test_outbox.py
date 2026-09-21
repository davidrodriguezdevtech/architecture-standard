from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = sa.create_engine("sqlite:///:memory:")
    from commons.adapters.outbox import outbox_table

    outbox_table.metadata.create_all(engine)
    return Session(engine)


def test_given_recorded_message__when_drained__then_published_and_marked() -> None:
    from commons.adapters.outbox import drain, record

    session = _session()
    record(
        session,
        event_type="OrderCreated",
        payload='{"order_id": "o-1"}',
        occurred_at=datetime.now(UTC),
        message_id="m-1",
    )
    session.commit()

    published: list[tuple[str, str]] = []

    def collect_event(event_type: str, payload: str) -> None:
        published.append((event_type, payload))

    count = drain(session, publish=collect_event)

    assert count == 1
    assert published == [("OrderCreated", '{"order_id": "o-1"}')]


def test_given_already_drained_message__when_drained_again__then_not_republished() -> None:
    from commons.adapters.outbox import drain, record

    session = _session()
    record(
        session,
        event_type="OrderCreated",
        payload="{}",
        occurred_at=datetime.now(UTC),
        message_id="m-1",
    )
    session.commit()
    drain(session, publish=lambda *_: None)

    second_count = drain(session, publish=lambda *_: None)
    assert second_count == 0
