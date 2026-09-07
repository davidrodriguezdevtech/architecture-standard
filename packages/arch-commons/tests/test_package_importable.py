from __future__ import annotations


def test_given_arch_commons_installed__when_imported__then_succeeds() -> None:
    import commons

    assert commons is not None
