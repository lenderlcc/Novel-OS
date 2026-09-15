from uuid import UUID

from fastapi import APIRouter

from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import DispatchView
from novel_os.api.writing_schemas import RegenerateDraft, WritingGenerationView
from novel_os.domain.workflow import EventCommand
from novel_os.services.writing_results import WritingResultService
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-writing"])


@router.get("/workflows/{workflow_id}/writing/history", response_model=list[WritingGenerationView])
def history(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return WritingResultService(session).history(workflow_id, limit, offset)


@router.post("/workflows/{workflow_id}/writing/regenerate", response_model=DispatchView)
def regenerate(workflow_id: UUID, body: RegenerateDraft, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type="REGENERATE_DRAFT",
                expected_state_version=body.expected_state_version,
                payload={
                    "expected_draft_version": body.expected_draft_version,
                    "reason": body.reason,
                },
            ),
            context,
        )
    )
