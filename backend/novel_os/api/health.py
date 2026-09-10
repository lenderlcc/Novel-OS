from typing import Annotated

from fastapi import APIRouter, Depends

from novel_os.api.dependencies import get_health_service
from novel_os.api.schemas import DatabaseHealthResponse, ErrorResponse, HealthResponse
from novel_os.services.health import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/db", response_model=DatabaseHealthResponse, responses={503: {"model": ErrorResponse}})
def database_health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> DatabaseHealthResponse:
    service.check_database()
    return DatabaseHealthResponse()
