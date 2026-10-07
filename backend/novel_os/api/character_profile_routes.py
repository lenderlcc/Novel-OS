from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Request

from novel_os.api.agent_schemas import AgentTaskView
from novel_os.api.character_profile_schemas import (
    CharacterProfileApprove,
    CharacterProfileCreate,
    CharacterProfileInterpret,
    CharacterProfileState,
    CharacterProfileView,
    CharacterSubjectInput,
    CharacterSubjectView,
    subject_view,
    view,
)
from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.services.agent_queries import AgentQueries
from novel_os.services.character_profiles import CharacterProfileService

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["character-profile"])


@router.get("", response_model=list[CharacterSubjectView])
def characters(project_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [
        subject_view(subject)
        for subject in CharacterProfileService(session).characters(project_id, limit, offset)
    ]


@router.post("", response_model=CharacterSubjectView, status_code=201)
def create_character(
    project_id: UUID, body: CharacterSubjectInput, session: DbSession, context: Context
):
    return subject_view(
        CharacterProfileService(session).create_character(
            project_id, body.name, body.aliases, context, body.reason
        )
    )


@router.get("/{character_id}/behavior-profile", response_model=CharacterProfileState)
def state(project_id: UUID, character_id: UUID, session: DbSession):
    current, approved = CharacterProfileService(session).state(project_id, character_id)
    return CharacterProfileState(
        current_profile_version=current.version if current else None,
        approved_profile_version=approved.version if approved else None,
        current=view(current),
        approved=view(approved),
    )


@router.get("/{character_id}/behavior-profile/approved", response_model=CharacterProfileView | None)
def approved(project_id: UUID, character_id: UUID, session: DbSession):
    return view(CharacterProfileService(session).state(project_id, character_id)[1])


@router.get("/{character_id}/behavior-profile/versions", response_model=list[CharacterProfileView])
def versions(
    project_id: UUID, character_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        view(row)
        for row in CharacterProfileService(session).versions(
            project_id, character_id, limit, offset
        )
    ]


@router.post(
    "/{character_id}/behavior-profile/drafts", response_model=CharacterProfileView, status_code=201
)
def create(
    project_id: UUID,
    character_id: UUID,
    body: CharacterProfileCreate,
    session: DbSession,
    context: Context,
):
    return view(
        CharacterProfileService(session).create_draft(
            project_id,
            character_id,
            body.profile.model_dump(mode="json"),
            body.expected_version,
            context,
            body.reason,
        )
    )


@router.post("/{character_id}/behavior-profile/approve", response_model=CharacterProfileView)
def approve(
    project_id: UUID,
    character_id: UUID,
    body: CharacterProfileApprove,
    session: DbSession,
    context: Context,
):
    return view(
        CharacterProfileService(session).approve(
            project_id, character_id, body.expected_version, context, body.reason
        )
    )


@router.post(
    "/{character_id}/behavior-profile/interpret",
    response_model=CharacterProfileView,
    status_code=201,
)
def interpret(
    project_id: UUID,
    character_id: UUID,
    body: CharacterProfileInterpret,
    request: Request,
    session: DbSession,
    context: Context,
):
    from novel_os.runtime_factory import build_agent_runtime
    from novel_os.services.character_profile_interpretation import (
        CharacterProfileInterpretationService,
    )

    return view(
        CharacterProfileInterpretationService(
            session, build_agent_runtime(request.app.state.settings)
        ).interpret(project_id, character_id, body.text, body.expected_version, context)
    )


@router.get("/{character_id}/behavior-profile/interpretations", response_model=list[AgentTaskView])
def interpretations(
    project_id: UUID, character_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [
        asdict(task)
        for task in AgentQueries(session).character_reports(project_id, character_id, limit, offset)
    ]
