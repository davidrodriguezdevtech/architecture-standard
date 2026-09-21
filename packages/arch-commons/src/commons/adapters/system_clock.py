from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """The one place allowed to call ``datetime.now()`` -- domain/application
    never do (spec Section 5.1, ARCH-004); they take a ``Clock`` port instead."""

    def now(self) -> datetime:
        return datetime.now(UTC)
