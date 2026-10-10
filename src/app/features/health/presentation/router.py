from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.container import get_readiness_use_case
from app.features.health.application.check_readiness import CheckReadiness
from app.features.health.presentation.schemas import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}
)
async def ready(
    use_case: Annotated[CheckReadiness, Depends(get_readiness_use_case)],
    response: Response,
) -> ReadinessResponse:
    is_ready = await use_case.execute()
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(status="ready" if is_ready else "not_ready")
