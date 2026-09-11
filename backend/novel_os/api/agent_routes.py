from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter

from novel_os.api.agent_schemas import AgentRunView, AgentTaskView
from novel_os.api.core_routes import DbSession, Limit, Offset
from novel_os.services.agent_queries import AgentQueries

router = APIRouter(tags=["agent-execution"])


@router.get("/agent-tasks/{task_id}", response_model=AgentTaskView)
def get_task(task_id: UUID, session: DbSession):
    return asdict(AgentQueries(session).get(task_id))


@router.get("/agent-tasks/{task_id}/runs", response_model=list[AgentRunView])
def get_runs(task_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [asdict(run) for run in AgentQueries(session).runs(task_id, limit, offset)]


@router.get("/workflows/{workflow_id}/agent-tasks", response_model=list[AgentTaskView])
def get_workflow_tasks(
    workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0
):
    return [asdict(task) for task in AgentQueries(session).tasks(workflow_id, limit, offset)]
