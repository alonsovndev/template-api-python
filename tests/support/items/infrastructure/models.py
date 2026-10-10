from uuid import UUID

from sqlalchemy import CheckConstraint, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ExampleBase(DeclarativeBase):
    pass


class ItemRecord(ExampleBase):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="ck_items_name_not_blank"),)

    identifier: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
