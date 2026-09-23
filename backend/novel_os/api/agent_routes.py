from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Request

from novel_os.api.agent_schemas import AgentExecutionConfigView, AgentRunView, AgentTaskView
from novel_os.api.core_routes import DbSession, Limit, Offset
from novel_os.api.prompt_schemas import PromptLineageView
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.services.agent_queries import AgentQueries
from novel_os.services.prompt_lineages import PromptLineageService

router = APIRouter(tags=["agent-execution"])


@router.get("/agent-execution/config", response_model=AgentExecutionConfigView)
def execution_config(request: Request):
    # Public execution policy only; never serialize Settings or imply worker liveness.
    settings = request.app.state.settings
    profile = ModelProfileRegistry().get(settings.agent_model_profile)
    return AgentExecutionConfigView(
        model_profile=profile.profile_id,
        provider=profile.provider,
        model=profile.model,
        task_types=settings.agent_task_types,
        max_attempts=settings.agent_max_attempts,
    )


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


@router.get("/agent-runs/{run_id}/prompt-lineage", response_model=PromptLineageView)
def get_prompt_lineage(run_id: UUID, session: DbSession):
    return asdict(PromptLineageService(session).get(run_id))
