from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.items.domain.item import DuplicateItemError, Item
from tests.support.items.infrastructure.models import ItemRecord


class PostgreSQLItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: Item) -> None:
        self._session.add(ItemRecord(identifier=item.identifier, name=item.name))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise DuplicateItemError("Item already exists") from None
            raise

    async def get(self, identifier: UUID) -> Item | None:
        record = await self._session.get(ItemRecord, identifier)
        return Item(identifier=record.identifier, name=record.name) if record is not None else None
