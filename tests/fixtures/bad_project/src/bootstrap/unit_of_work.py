from __future__ import annotations

from commons.adapters.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork


class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork):  # ARCH-059: adapter defined
    """Wrong: an adapter implementation defined in bootstrap/ instead of
    commons/adapters/ or a module's own adapters/."""
