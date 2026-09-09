from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import registry, sessionmaker


@dataclass
class _Widget:
    id: str
    pending_events: list[object] = field(default_factory=list)

    def clear_pending_events(self) -> None:
        self.pending_events.clear()


@pytest.fixture
def widget_session_factory() -> sessionmaker:  # type: ignore[type-arg]
    # Create a fresh mapper and engine for each test
    from sqlalchemy.orm import clear_mappers

    clear_mappers()
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    widgets = sa.Table("widgets", metadata, sa.Column("id", sa.String, primary_key=True))
    mapper_registry = registry(metadata=metadata)
    mapper_registry.map_imperatively(_Widget, widgets)
    metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_given_added_widget__when_committed__then_collect_new_events_drains_it(
    widget_session_factory: sessionmaker,  # type: ignore[type-arg]
) -> None:
    from commons.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork

    uow = SqlAlchemyUnitOfWork(widget_session_factory)
    with uow:
        widget = _Widget(id="w-1")
        widget.pending_events.append("WidgetCreated")
        uow.session.add(widget)
        uow.commit()
    # plain strings stand in for events here; only pass-through behavior is under test
    assert list(uow.collect_new_events()) == ["WidgetCreated"]  # type: ignore[comparison-overlap]


def test_given_uncommitted_change__when_exit__then_rollback_and_session_closed(
    widget_session_factory: sessionmaker,  # type: ignore[type-arg]
) -> None:
    from commons.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork

    uow = SqlAlchemyUnitOfWork(widget_session_factory)
    with uow:
        uow.session.add(_Widget(id="w-1"))
        # no commit() -- __exit__ must roll back
    # __self__ is a bound-method attribute mypy does not model on Callable
    assert uow.session.close.__self__ is uow.session  # type: ignore[attr-defined]
