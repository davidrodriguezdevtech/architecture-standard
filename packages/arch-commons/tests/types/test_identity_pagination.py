from __future__ import annotations

import pytest


def test_given_entity_id__when_constructed_with_value__then_str_returns_it() -> None:
    from commons.types.identity import EntityId

    entity_id = EntityId(value="ord-1")
    assert str(entity_id) == "ord-1"


def test_given_entity_id__when_constructed_empty__then_raises() -> None:
    from commons.types.identity import EntityId

    with pytest.raises(ValueError):
        EntityId(value="")


def test_given_entity_id__when_constructed__then_it_is_frozen() -> None:
    from commons.types.identity import EntityId

    entity_id = EntityId(value="ord-1")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        entity_id.value = "ord-2"  # type: ignore[misc]


def test_given_page__when_constructed__then_holds_items_and_total() -> None:
    from commons.types.pagination import Page

    page: Page[int] = Page(items=(1, 2, 3), total=10)
    assert page.items == (1, 2, 3)
    assert page.total == 10
