"""Explicit human completion commands; no agent memory-write endpoint."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import CommandInput, DispatchView
from novel_os.domain.enums import Authority
from novel_os.domain.memory import (
    CommittedMemory,
    MemoryCommitBatch,
    MemoryConflict,
    MemoryRequest,
    MemoryType,
)
from novel_os.domain.workflow import EventCommand
from novel_os.memory.schemas import MemoryCandidate
from novel_os.services.memory_commit import MemoryCommitService
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-memory"])


class RequestCompletion(CommandInput):
    chapter_version_id: UUID


class ConfirmMemory(CommandInput):
    proposal_id: UUID
    selected_candidate_ids: list[str] = Field(max_length=40)


class DiscardMemory(CommandInput):
    request_id: UUID


class NormalizedMemoryCandidate(MemoryCandidate):
    subject_id: UUID | None
    normalized_subject: dict | None
    conflict_status: MemoryConflict
    conflict_reason: str
    authority_level: Authority
    previous_entry_id: UUID | None
    previous_statement: str | None


class MemoryProposalView(BaseModel):
    id: UUID
    request_id: UUID
    task_id: UUID
    agent_run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    raw_output: dict
    candidates: list[NormalizedMemoryCandidate]
    created_at: datetime


class MemoryHistoryView(BaseModel):
    request: MemoryRequest
    proposal: MemoryProposalView | None
    status: Literal["EXTRACTING", "PROPOSED", "STALE", "CANCELLED", "COMMITTED"]
    batch: MemoryCommitBatch | None
    entries: list[CommittedMemory]


def dispatch(workflow_id, event, body, session, context):
    payload = body.model_dump(mode="json", exclude={"event_id", "expected_state_version"})
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type=event,
                expected_state_version=body.expected_state_version,
                payload=payload,
            ),
            context,
        )
    )


@router.post("/workflows/{workflow_id}/completion", response_model=DispatchView)
def complete(workflow_id: UUID, body: RequestCompletion, session: DbSession, context: Context):
    return dispatch(workflow_id, "REQUEST_COMPLETION", body, session, context)


@router.post("/workflows/{workflow_id}/memory/confirm", response_model=DispatchView)
def confirm(workflow_id: UUID, body: ConfirmMemory, session: DbSession, context: Context):
    return dispatch(workflow_id, "CONFIRM_MEMORY", body, session, context)


@router.post("/workflows/{workflow_id}/memory/discard", response_model=DispatchView)
def discard(workflow_id: UUID, body: DiscardMemory, session: DbSession, context: Context):
    return dispatch(workflow_id, "DISCARD_MEMORY", body, session, context)


@router.get("/workflows/{workflow_id}/memory", response_model=list[MemoryHistoryView])
def history(workflow_id: UUID, session: DbSession, limit: Limit = 50, offset: Offset = 0):
    return MemoryCommitService(session).history(workflow_id, limit, offset)


@router.get("/projects/{project_id}/memory", response_model=list[CommittedMemory])
def memories(
    project_id: UUID,
    session: DbSession,
    subject_id: UUID | None = None,
    memory_type: MemoryType | None = None,
    historical: bool = False,
    limit: Limit = 100,
    offset: Offset = 0,
):
    return MemoryCommitService(session).memories(
        project_id,
        subject_id=subject_id,
        memory_type=memory_type,
        historical=historical,
        limit=limit,
        offset=offset,
    )
