from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.quality_schemas import QualityBindingView
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import CommandInput, DispatchView
from novel_os.domain.workflow import EventCommand
from novel_os.revision.schemas import RevisionMetadata, RevisionPlanOutput
from novel_os.services.revision_results import RevisionResultService
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-revision"])


class RequestRevision(CommandInput):
    source_review_id: UUID
    expected_draft_version: int = Field(strict=True, gt=0)


class RevisionRequestView(BaseModel):
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    source_chapter_version_id: UUID
    source_review_id: UUID
    source_binding_id: UUID
    source_context_package_id: UUID
    contract: dict
    created_at: datetime


class RevisionEvidenceView(BaseModel):
    id: UUID
    request_id: UUID
    task_id: UUID
    run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    created_at: datetime


class RevisionPlanView(RevisionEvidenceView):
    body: RevisionPlanOutput


class RevisionMetadataView(RevisionMetadata):
    content_hash: str | None


class RevisionResultView(RevisionEvidenceView):
    revision_plan_id: UUID
    chapter_version_id: UUID | None
    body: RevisionMetadataView


class RevisionView(BaseModel):
    request: RevisionRequestView
    source_binding: QualityBindingView
    plan: RevisionPlanView | None
    result: RevisionResultView | None


@router.post("/workflows/{workflow_id}/revision", response_model=DispatchView)
def request_revision(
    workflow_id: UUID, body: RequestRevision, session: DbSession, context: Context
):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type="REQUEST_REVISION",
                expected_state_version=body.expected_state_version,
                payload={
                    "source_review_id": str(body.source_review_id),
                    "expected_draft_version": body.expected_draft_version,
                    "reason": body.reason,
                },
            ),
            context,
        )
    )


@router.get("/workflows/{workflow_id}/revisions", response_model=list[RevisionView])
def history(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return RevisionResultService(session).history(workflow_id, limit, offset)
