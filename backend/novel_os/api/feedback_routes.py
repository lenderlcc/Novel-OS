from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import CommandInput, DispatchView
from novel_os.domain.workflow import EventCommand
from novel_os.feedback.schemas import FeedbackInterpretationOutput
from novel_os.services.feedback_results import FeedbackResultService
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["human-feedback"])


class SubmitFeedback(CommandInput):
    source_chapter_version_id: UUID
    raw_feedback: str = Field(min_length=1, max_length=12000)
    reply_to_feedback_id: UUID | None = None


class DiscardFeedback(CommandInput):
    feedback_id: UUID


class FeedbackView(BaseModel):
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    source_chapter_version_id: UUID
    source_draft_version: int
    source_state_version: int
    source_review_id: UUID | None
    raw_feedback: str
    reply_to_feedback_id: UUID | None
    source: str
    status: str
    return_state: str
    authority_snapshot: dict
    created_at: datetime


class InterpretationView(BaseModel):
    id: UUID
    feedback_id: UUID
    task_id: UUID
    run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    body: FeedbackInterpretationOutput
    created_at: datetime


class FeedbackHistoryView(BaseModel):
    feedback: FeedbackView
    interpretation: InterpretationView | None


@router.post("/workflows/{workflow_id}/feedback", response_model=DispatchView)
def submit(workflow_id: UUID, body: SubmitFeedback, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type="REQUEST_FEEDBACK",
                expected_state_version=body.expected_state_version,
                payload={
                    "source_chapter_version_id": str(body.source_chapter_version_id),
                    "raw_feedback": body.raw_feedback,
                    "reply_to_feedback_id": str(body.reply_to_feedback_id)
                    if body.reply_to_feedback_id
                    else None,
                    "reason": body.reason,
                },
            ),
            context,
        )
    )


@router.post("/workflows/{workflow_id}/feedback/discard", response_model=DispatchView)
def discard(workflow_id: UUID, body: DiscardFeedback, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type="DISCARD_FEEDBACK",
                expected_state_version=body.expected_state_version,
                payload={"feedback_id": str(body.feedback_id), "reason": body.reason},
            ),
            context,
        )
    )


@router.get("/workflows/{workflow_id}/feedback", response_model=list[FeedbackHistoryView])
def history(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return FeedbackResultService(session).history(workflow_id, limit, offset)
