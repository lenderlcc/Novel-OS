from uuid import UUID

from fastapi import APIRouter

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.planning_schemas import CreatePlanningWorkflow
from novel_os.api.quality_schemas import QualityReviewView, RequestReview
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import DispatchView
from novel_os.domain.workflow import EventCommand
from novel_os.services.quality_results import QualityResultService
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-quality"])


@router.post("/workflows/chapter-quality", response_model=DispatchView, status_code=201)
def create(body: CreatePlanningWorkflow, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).create(
            body.project_id,
            body.chapter_id,
            body.event_id,
            context,
            "chapter-planning",
            3,
            raw_requirement=body.raw_requirement,
        )
    )


@router.get(
    "/projects/{project_id}/chapters/{chapter_id}/quality-reviews",
    response_model=list[QualityReviewView],
)
def history(
    project_id: UUID, chapter_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return QualityResultService(session).history(project_id, chapter_id, limit, offset)


@router.post("/workflows/{workflow_id}/quality-review", response_model=DispatchView)
def request_review(workflow_id: UUID, body: RequestReview, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type="REQUEST_REVIEW",
                expected_state_version=body.expected_state_version,
                payload={
                    "expected_draft_version": body.expected_draft_version,
                    "reason": body.reason,
                },
            ),
            context,
        )
    )
