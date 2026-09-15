"""Read-only context inspection. No model credentials or raw internal configuration."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from novel_os.api.core_routes import DbSession
from novel_os.domain.context import ContextPackage, ContextStatus
from novel_os.services.context import ContextService


class ContextInspection(BaseModel):
    package: ContextPackage
    freshness: ContextStatus
    error_code: str | None


router = APIRouter(tags=["context"])


@router.get("/context-packages/{context_package_id}", response_model=ContextInspection)
def get_context_package(context_package_id: UUID, session: DbSession):
    return ContextService(session).inspect(package_id=context_package_id)


@router.get("/agent-tasks/{task_id}/context", response_model=ContextInspection)
def get_task_context(task_id: UUID, session: DbSession):
    return ContextService(session).inspect(task_id=task_id)
