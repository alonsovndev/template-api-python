from app.features.health.application.ports import ReadinessProbe


class CheckReadiness:
    def __init__(self, probe: ReadinessProbe) -> None:
        self._probe = probe

    async def execute(self) -> bool:
        return await self._probe.is_ready()
