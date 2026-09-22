from __future__ import annotations

from commons.adapters.unit_of_work import ScopedSqlAlchemyUnitOfWork


def build_uow() -> ScopedSqlAlchemyUnitOfWork:
    """Wiring only: constructs an instance of an adapter defined in
    commons/adapters/, does not define the class itself (ARCH-059)."""
    return ScopedSqlAlchemyUnitOfWork(session_factory=None)
