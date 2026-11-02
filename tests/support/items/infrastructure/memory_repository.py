from uuid import UUID

from tests.support.items.domain.item import DuplicateItemError, Item


class MemoryItemRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, Item] = {}

    async def add(self, item: Item) -> None:
        if item.identifier in self._items:
            raise DuplicateItemError("Item already exists")
        self._items[item.identifier] = item

    async def get(self, identifier: UUID) -> Item | None:
        return self._items.get(identifier)
