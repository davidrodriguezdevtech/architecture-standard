from __future__ import annotations


class DomainError(Exception):
    """Base for expected business errors raised by domain/ and application/ (ARCH-032)."""


class ApplicationError(Exception):
    """Base for application-layer errors that are not business-rule violations."""
