from typing import Protocol
from uuid import UUID

from tests.support.items.domain.item import Item


class ItemRepository(Protocol):
    async def add(self, item: Item) -> None: ...

    async def get(self, identifier: UUID) -> Item | None: ...
