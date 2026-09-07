from __future__ import annotations

import pytest


def test_given_domain_error__when_raised__then_it_is_an_exception() -> None:
    from commons.types.errors import DomainError

    with pytest.raises(DomainError):
        raise DomainError("insufficient credit")


def test_given_application_error__when_raised__then_it_is_distinct_from_domain_error() -> None:
    from commons.types.errors import ApplicationError, DomainError

    assert not issubclass(ApplicationError, DomainError)
    assert not issubclass(DomainError, ApplicationError)
