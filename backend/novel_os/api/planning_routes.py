from uuid import UUID

from fastapi import APIRouter

from novel_os.api import planning_schemas as dto
from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.api.workflow_routes import response
from novel_os.api.workflow_schemas import DispatchView
from novel_os.services.planning_queries import PlanningQueries
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-planning"])


@router.post("/workflows/chapter-planning", response_model=DispatchView, status_code=201)
def create(body: dto.CreatePlanningWorkflow, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).create(
            body.project_id,
            body.chapter_id,
            body.event_id,
            context,
            "chapter-planning",
            1,
            raw_requirement=body.raw_requirement,
        )
    )


@router.post("/workflows/chapter-writing", response_model=DispatchView, status_code=201)
def create_writing(body: dto.CreatePlanningWorkflow, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).create(
            body.project_id,
            body.chapter_id,
            body.event_id,
            context,
            "chapter-planning",
            2,
            raw_requirement=body.raw_requirement,
        )
    )


@router.post("/workflows/{workflow_id}/requirement", response_model=DispatchView)
def correct(workflow_id: UUID, body: dto.CorrectRequirement, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).correct_requirement(
            workflow_id,
            body.event_id,
            body.expected_state_version,
            body.expected_brief_version,
            body.raw_requirement,
            context,
        )
    )


@router.get("/workflows/{workflow_id}/creative-brief", response_model=dto.BriefView)
def current_brief(workflow_id: UUID, session: DbSession):
    return PlanningQueries(session).brief(workflow_id)


@router.get(
    "/workflows/{workflow_id}/creative-brief/versions/{version}", response_model=dto.BriefView
)
def brief_version(workflow_id: UUID, version: int, session: DbSession):
    return PlanningQueries(session).brief(workflow_id, version)


@router.get("/workflows/{workflow_id}/planning/plan", response_model=dto.PlanningView)
def current_plan(workflow_id: UUID, session: DbSession):
    return PlanningQueries(session).plan(workflow_id)


@router.get(
    "/workflows/{workflow_id}/planning/plan/versions/{version}", response_model=dto.PlanningView
)
def plan_version(workflow_id: UUID, version: int, session: DbSession):
    return PlanningQueries(session).plan(workflow_id, version)


@router.get("/workflows/{workflow_id}/planning/review", response_model=dto.ReviewView)
def current_review(workflow_id: UUID, session: DbSession):
    return PlanningQueries(session).review(workflow_id)


@router.get("/workflows/{workflow_id}/planning/history", response_model=dto.HistoryView)
def history(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return PlanningQueries(session).history(workflow_id, limit, offset)


@router.get("/workflows/{workflow_id}/planning/metrics", response_model=dto.MetricsView)
def metrics(workflow_id: UUID, session: DbSession):
    return PlanningQueries(session).metrics(workflow_id)
