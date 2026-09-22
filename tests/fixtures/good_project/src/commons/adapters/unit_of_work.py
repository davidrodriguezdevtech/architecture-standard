from __future__ import annotations

from commons.adapters.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork


class ScopedSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork):
    """A project-owned, request-scoped variant -- shared across every context,
    not (yet) proposed upstream. Lives in commons/adapters/, not bootstrap/."""
