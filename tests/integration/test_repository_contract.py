from uuid import UUID

import pytest

from tests.support.items.domain.item import DuplicateItemError, Item
from tests.support.items.domain.repository import ItemRepository

ITEM_IDENTIFIER = UUID("c434c22d-cce4-4b2b-81bd-8b4fb012e534")


async def test_repository_round_trips_domain_values(item_repository: ItemRepository) -> None:
    item = Item(ITEM_IDENTIFIER, "Repository example")
    await item_repository.add(item)
    assert await item_repository.get(ITEM_IDENTIFIER) == item


async def test_repository_returns_none_for_missing_identifier(
    item_repository: ItemRepository,
) -> None:
    assert await item_repository.get(ITEM_IDENTIFIER) is None


async def test_repository_rejects_duplicate_identifiers(item_repository: ItemRepository) -> None:
    await item_repository.add(Item(ITEM_IDENTIFIER, "First"))
    with pytest.raises(DuplicateItemError):
        await item_repository.add(Item(ITEM_IDENTIFIER, "Second"))
