from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase  # ARCH-003


class Base(DeclarativeBase):
    pass


class OrderRow(Base):  # ARCH-028
    pass
