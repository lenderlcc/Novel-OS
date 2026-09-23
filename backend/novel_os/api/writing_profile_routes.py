from uuid import UUID

from fastapi import APIRouter

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.writing_profile_schemas import (
    WritingProfileApprove,
    WritingProfileCreate,
    WritingProfileState,
    WritingProfileView,
    view,
)
from novel_os.services.writing_profiles import WritingProfileService

router = APIRouter(prefix="/projects/{project_id}/writing-profile", tags=["writing-profile"])


@router.get("", response_model=WritingProfileState)
def state(project_id: UUID, session: DbSession):
    current, approved = WritingProfileService(session).state(project_id)
    return WritingProfileState(
        current_profile_version=current.version if current else None,
        approved_profile_version=approved.version if approved else None,
        current=view(current),
        approved=view(approved),
    )


@router.get("/approved", response_model=WritingProfileView | None)
def approved(project_id: UUID, session: DbSession):
    return view(WritingProfileService(session).state(project_id)[1])


@router.get("/versions", response_model=list[WritingProfileView])
def versions(project_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [view(row) for row in WritingProfileService(session).versions(project_id, limit, offset)]


@router.post("/drafts", response_model=WritingProfileView, status_code=201)
def create(project_id: UUID, body: WritingProfileCreate, session: DbSession, context: Context):
    return view(
        WritingProfileService(session).create_draft(
            project_id,
            body.preferences.model_dump(mode="json"),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/approve", response_model=WritingProfileView)
def approve(project_id: UUID, body: WritingProfileApprove, session: DbSession, context: Context):
    return view(
        WritingProfileService(session).approve(
            project_id, body.expected_version, context, body.reason
        )
    )
