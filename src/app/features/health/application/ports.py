from typing import Protocol


class ReadinessProbe(Protocol):
    async def is_ready(self) -> bool: ...
