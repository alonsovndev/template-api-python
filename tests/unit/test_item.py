from uuid import UUID

import pytest

from tests.support.items.application.use_cases import (
    CreateItem,
    CreateItemCommand,
    GetItem,
    ItemResult,
)
from tests.support.items.domain.item import Item
from tests.support.items.infrastructure.memory_repository import MemoryItemRepository

ITEM_IDENTIFIER = UUID("c434c22d-cce4-4b2b-81bd-8b4fb012e534")


@pytest.mark.parametrize("name", ["", "   ", "a" * 101])
def test_item_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError, match="Item name"):
        Item(identifier=ITEM_IDENTIFIER, name=name)


async def test_use_cases_work_without_framework_or_database() -> None:
    repository = MemoryItemRepository()
    created = await CreateItem(repository).execute(CreateItemCommand(ITEM_IDENTIFIER, "Example"))
    assert created == ItemResult(ITEM_IDENTIFIER, "Example")
    assert await GetItem(repository).execute(ITEM_IDENTIFIER) == created


async def test_memory_repository_instances_do_not_share_state() -> None:
    first = MemoryItemRepository()
    second = MemoryItemRepository()
    await first.add(Item(ITEM_IDENTIFIER, "Example"))
    assert await second.get(ITEM_IDENTIFIER) is None
