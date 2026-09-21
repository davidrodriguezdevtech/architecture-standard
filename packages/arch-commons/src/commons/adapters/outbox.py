from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
from sqlalchemy.orm import Session

_metadata = MetaData()

outbox_table = Table(
    "outbox",
    _metadata,
    Column("id", String, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("payload", Text, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("published_at", DateTime, nullable=True),
)


def record(
    session: Session,
    *,
    event_type: str,
    payload: str,
    occurred_at: datetime,
    message_id: str,
) -> None:
    """Insert one outbox row in the CALLER's own open transaction (ARCH-036 --
    delivery-guaranteed integration events are written in the same transaction
    as the aggregate change; a separate process publishes them)."""
    session.execute(
        outbox_table.insert().values(
            id=message_id,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            published_at=None,
        )
    )


def drain(
    session: Session,
    publish: Callable[[str, str], None],
    batch_size: int = 100,
) -> int:
    """Publish unpublished rows oldest-first, marking each on success. Runs in
    a SEPARATE process/transaction from ``record()``."""
    rows = session.execute(
        outbox_table.select()
        .where(outbox_table.c.published_at.is_(None))
        .order_by(outbox_table.c.occurred_at)
        .limit(batch_size)
    ).all()
    count = 0
    for row in rows:
        publish(row.event_type, row.payload)
        session.execute(
            outbox_table.update()
            .where(outbox_table.c.id == row.id)
            .values(published_at=datetime.now(UTC))
        )
        count += 1
    session.commit()
    return count
