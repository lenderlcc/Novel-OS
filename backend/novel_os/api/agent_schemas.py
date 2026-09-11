from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from novel_os.domain.agents import AgentId, ResultStatus, RunStatus, TaskStatus
from novel_os.domain.workflow import ChapterState


class AgentTaskView(BaseModel):
    task_id: UUID
    project_id: UUID
    workflow_instance_id: UUID
    workflow_state: ChapterState
    workflow_state_version: int
    agent_id: AgentId
    task_type: str
    objective: str
    target_ref: UUID
    requirements: list[str]
    constraints: list[str]
    capabilities: list[str]
    expected_output_schema: str
    status: TaskStatus
    priority: int
    version: int
    attempt_count: int
    max_attempts: int
    created_at: datetime
    available_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    result_ref: UUID | None
    result_metadata: dict


class AgentRunView(BaseModel):
    run_id: UUID
    task_id: UUID
    attempt_number: int
    worker_id: str
    status: RunStatus
    claimed_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    provider: str
    model: str
    input_metadata: dict
    output_metadata: dict
    error_code: str | None
    error_message: str | None
    result_status: ResultStatus | None
    disposition: str | None
