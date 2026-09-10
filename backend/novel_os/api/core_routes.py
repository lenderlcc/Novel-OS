from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from novel_os.api import core_schemas as dto
from novel_os.api.dependencies import get_session
from novel_os.domain.core import CommandContext, ObjectRef
from novel_os.services.core_base import CoreService
from novel_os.services.locks import LockService
from novel_os.services.projects import ChapterService, ProjectService
from novel_os.services.versioning import (
    ChapterVersionService,
    DecisionService,
    PlanningService,
    RequirementService,
)

router = APIRouter(prefix="/projects", tags=["core-domain"])
DbSession = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def command_context(request: Request) -> CommandContext:
    # Trusted single-user local control plane. Actor claims are never read from HTTP.
    return CommandContext(request_id=request.state.request_id, actor_id="local-user")


Context = Annotated[CommandContext, Depends(command_context)]


@router.post("", response_model=dto.ProjectView, status_code=201)
def create_project(body: dto.ProjectInput, session: DbSession, context: Context):
    return dto.view(ProjectService(session).create(dto.payload(body), context))


@router.get("", response_model=list[dto.ProjectView])
def list_projects(session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [dto.view(item) for item in ProjectService(session).list(limit, offset)]


@router.get("/{project_id}", response_model=dto.ProjectView)
def get_project(project_id: UUID, session: DbSession):
    return dto.view(ProjectService(session).get(project_id))


@router.patch("/{project_id}", response_model=dto.ProjectView)
def update_project(project_id: UUID, body: dto.ProjectUpdate, session: DbSession, context: Context):
    return dto.view(
        ProjectService(session).update(
            project_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.delete("/{project_id}", response_model=dto.ProjectView)
def archive_project(
    project_id: UUID, body: dto.VersionCommand, session: DbSession, context: Context
):
    return dto.view(
        ProjectService(session).archive(
            project_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/{project_id}/chapters", response_model=dto.ChapterView, status_code=201)
def create_chapter(project_id: UUID, body: dto.ChapterInput, session: DbSession, context: Context):
    return dto.view(ChapterService(session).create(project_id, dto.payload(body), context))


@router.get("/{project_id}/chapters", response_model=list[dto.ChapterView])
def list_chapters(project_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [dto.view(item) for item in ChapterService(session).list(project_id, limit, offset)]


@router.get("/{project_id}/chapters/{chapter_id}", response_model=dto.ChapterView)
def get_chapter(project_id: UUID, chapter_id: UUID, session: DbSession):
    return dto.view(ChapterService(session).get(project_id, chapter_id))


@router.post("/{project_id}/requirements", response_model=dto.RequirementView, status_code=201)
def create_requirement(
    project_id: UUID, body: dto.RequirementInput, session: DbSession, context: Context
):
    return dto.view(RequirementService(session).create(project_id, dto.payload(body), context))


@router.get("/{project_id}/requirements", response_model=list[dto.RequirementView])
def list_requirements(
    project_id: UUID,
    session: DbSession,
    limit: Limit = 100,
    offset: Offset = 0,
    effective: bool = False,
):
    return [
        dto.view(item)
        for item in RequirementService(session).list(
            project_id,
            limit=limit,
            offset=offset,
            effective=effective,
        )
    ]


@router.get("/{project_id}/requirements/{logical_id}", response_model=dto.RequirementView)
def get_requirement(project_id: UUID, logical_id: UUID, session: DbSession):
    return dto.view(RequirementService(session).get(project_id, logical_id))


@router.get(
    "/{project_id}/requirements/{logical_id}/versions", response_model=list[dto.RequirementView]
)
def list_requirement_versions(
    project_id: UUID, logical_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        dto.view(item)
        for item in RequirementService(session).list(project_id, logical_id, limit, offset)
    ]


@router.get(
    "/{project_id}/requirements/{logical_id}/versions/{version}", response_model=dto.RequirementView
)
def get_requirement_version(project_id: UUID, logical_id: UUID, version: int, session: DbSession):
    return dto.view(RequirementService(session).get(project_id, logical_id, version))


@router.post("/{project_id}/requirements/{logical_id}/approve", response_model=dto.RequirementView)
def approve_requirement(
    project_id: UUID,
    logical_id: UUID,
    body: dto.VersionCommand,
    session: DbSession,
    context: Context,
):
    return dto.view(
        RequirementService(session).approve(
            project_id,
            logical_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.patch("/{project_id}/requirements/{logical_id}", response_model=dto.RequirementView)
def edit_requirement(
    project_id: UUID,
    logical_id: UUID,
    body: dto.RequirementRevision,
    session: DbSession,
    context: Context,
):
    return dto.view(
        RequirementService(session).revise(
            project_id,
            logical_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
            direct_edit=True,
        )
    )


@router.post(
    "/{project_id}/requirements/{logical_id}/supersede",
    response_model=dto.RequirementView,
    status_code=201,
)
def revise_requirement(
    project_id: UUID,
    logical_id: UUID,
    body: dto.RequirementRevision,
    session: DbSession,
    context: Context,
):
    return dto.view(
        RequirementService(session).revise(
            project_id,
            logical_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/{project_id}/decisions", response_model=dto.DecisionView, status_code=201)
def create_decision(
    project_id: UUID, body: dto.DecisionInput, session: DbSession, context: Context
):
    return dto.view(DecisionService(session).create(project_id, dto.payload(body), context))


@router.get("/{project_id}/decisions", response_model=list[dto.DecisionView])
def list_decisions(
    project_id: UUID,
    session: DbSession,
    limit: Limit = 100,
    offset: Offset = 0,
    effective: bool = False,
):
    return [
        dto.view(item)
        for item in DecisionService(session).list(
            project_id,
            limit=limit,
            offset=offset,
            effective=effective,
        )
    ]


@router.get("/{project_id}/decisions/{logical_id}", response_model=dto.DecisionView)
def get_decision(project_id: UUID, logical_id: UUID, session: DbSession):
    return dto.view(DecisionService(session).get(project_id, logical_id))


@router.get("/{project_id}/decisions/{logical_id}/versions", response_model=list[dto.DecisionView])
def list_decision_versions(
    project_id: UUID, logical_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        dto.view(item)
        for item in DecisionService(session).list(project_id, logical_id, limit, offset)
    ]


@router.get(
    "/{project_id}/decisions/{logical_id}/versions/{version}", response_model=dto.DecisionView
)
def get_decision_version(project_id: UUID, logical_id: UUID, version: int, session: DbSession):
    return dto.view(DecisionService(session).get(project_id, logical_id, version))


@router.post("/{project_id}/decisions/{logical_id}/approve", response_model=dto.DecisionView)
def approve_decision(
    project_id: UUID,
    logical_id: UUID,
    body: dto.VersionCommand,
    session: DbSession,
    context: Context,
):
    return dto.view(
        DecisionService(session).approve(
            project_id,
            logical_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.patch("/{project_id}/decisions/{logical_id}", response_model=dto.DecisionView)
def edit_decision(
    project_id: UUID,
    logical_id: UUID,
    body: dto.DecisionRevision,
    session: DbSession,
    context: Context,
):
    return dto.view(
        DecisionService(session).revise(
            project_id,
            logical_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
            direct_edit=True,
        )
    )


@router.post(
    "/{project_id}/decisions/{logical_id}/versions",
    response_model=dto.DecisionView,
    status_code=201,
)
def revise_decision(
    project_id: UUID,
    logical_id: UUID,
    body: dto.DecisionRevision,
    session: DbSession,
    context: Context,
):
    return dto.view(
        DecisionService(session).revise(
            project_id,
            logical_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post(
    "/{project_id}/chapters/{chapter_id}/plans", response_model=dto.PlanView, status_code=201
)
def create_plan(
    project_id: UUID, chapter_id: UUID, body: dto.PlanCreate, session: DbSession, context: Context
):
    return dto.view(
        PlanningService(session).create_version(
            project_id,
            chapter_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.get("/{project_id}/chapters/{chapter_id}/plans", response_model=list[dto.PlanView])
def list_plans(
    project_id: UUID, chapter_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        dto.view(item)
        for item in PlanningService(session).list(project_id, chapter_id, limit, offset)
    ]


@router.get("/{project_id}/chapters/{chapter_id}/plans/{version}", response_model=dto.PlanView)
def get_plan(project_id: UUID, chapter_id: UUID, version: int, session: DbSession):
    return dto.view(PlanningService(session).get(project_id, chapter_id, version))


@router.post("/{project_id}/chapters/{chapter_id}/plans/approve", response_model=dto.PlanView)
def approve_plan(
    project_id: UUID,
    chapter_id: UUID,
    body: dto.VersionCommand,
    session: DbSession,
    context: Context,
):
    return dto.view(
        PlanningService(session).approve(
            project_id,
            chapter_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post(
    "/{project_id}/chapters/{chapter_id}/versions",
    response_model=dto.ChapterVersionView,
    status_code=201,
)
def create_chapter_version(
    project_id: UUID,
    chapter_id: UUID,
    body: dto.ChapterVersionCreate,
    session: DbSession,
    context: Context,
):
    return dto.view(
        ChapterVersionService(session).create_version(
            project_id,
            chapter_id,
            dto.payload(body),
            body.expected_version,
            context,
            body.change_reason,
        )
    )


@router.get(
    "/{project_id}/chapters/{chapter_id}/versions", response_model=list[dto.ChapterVersionView]
)
def list_chapter_versions(
    project_id: UUID, chapter_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        dto.view(item)
        for item in ChapterVersionService(session).list(project_id, chapter_id, limit, offset)
    ]


@router.get(
    "/{project_id}/chapters/{chapter_id}/versions/{version}", response_model=dto.ChapterVersionView
)
def get_chapter_version(project_id: UUID, chapter_id: UUID, version: int, session: DbSession):
    return dto.view(ChapterVersionService(session).get(project_id, chapter_id, version))


@router.post(
    "/{project_id}/chapters/{chapter_id}/versions/approve", response_model=dto.ChapterVersionView
)
def approve_chapter_version(
    project_id: UUID,
    chapter_id: UUID,
    body: dto.VersionCommand,
    session: DbSession,
    context: Context,
):
    return dto.view(
        ChapterVersionService(session).approve(
            project_id,
            chapter_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/{project_id}/locks", response_model=dto.LockView, status_code=201)
def lock_object(project_id: UUID, body: dto.LockInput, session: DbSession, context: Context):
    return dto.view(
        LockService(session).create(
            project_id,
            ObjectRef(body.target_type, body.target_id),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/{project_id}/locks/{lock_id}/release", response_model=dto.LockView)
def release_lock(
    project_id: UUID, lock_id: UUID, body: dto.VersionCommand, session: DbSession, context: Context
):
    return dto.view(
        LockService(session).release(
            project_id,
            lock_id,
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.get("/{project_id}/locks", response_model=list[dto.LockView])
def list_locks(project_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [dto.view(item) for item in LockService(session).list(project_id, limit, offset)]


@router.get("/{project_id}/audit", response_model=list[dto.AuditView])
def list_audit(project_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [dto.view(item) for item in CoreService(session).list_audit(project_id, limit, offset)]
