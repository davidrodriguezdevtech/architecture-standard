from __future__ import annotations

from collections.abc import Iterable


def test_given_a_unit_of_work__when_used_as_context_manager__then_works() -> None:
    from commons.types.events import DomainEvent
    from commons.types.unit_of_work import UnitOfWork

    class Recording(UnitOfWork):
        def __init__(self) -> None:
            self.committed = False
            self.tracked: list[object] = []

        def __enter__(self) -> Recording:
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            self.committed = False

        def track(self, aggregate: object) -> None:
            self.tracked.append(aggregate)

        def collect_new_events(self) -> Iterable[DomainEvent]:
            return []

    uow: UnitOfWork = Recording()
    with uow:
        uow.track(object())
        uow.commit()
    assert list(uow.collect_new_events()) == []
