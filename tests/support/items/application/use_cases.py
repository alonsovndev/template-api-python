from dataclasses import dataclass
from uuid import UUID

from tests.support.items.domain.item import Item
from tests.support.items.domain.repository import ItemRepository


@dataclass(frozen=True)
class CreateItemCommand:
    identifier: UUID
    name: str


@dataclass(frozen=True)
class ItemResult:
    identifier: UUID
    name: str


class CreateItem:
    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateItemCommand) -> ItemResult:
        item = Item(identifier=command.identifier, name=command.name)
        await self._repository.add(item)
        return ItemResult(identifier=item.identifier, name=item.name)


class GetItem:
    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    async def execute(self, identifier: UUID) -> ItemResult | None:
        item = await self._repository.get(identifier)
        return ItemResult(identifier=item.identifier, name=item.name) if item is not None else None
