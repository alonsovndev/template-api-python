from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Item:
    identifier: UUID
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 100:
            raise ValueError("Item name must contain 1 to 100 characters and cannot be blank")


class DuplicateItemError(ValueError):
    pass
