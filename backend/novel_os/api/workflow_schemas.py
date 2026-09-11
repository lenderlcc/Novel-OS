from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from novel_os.domain.workflow import (
    ChapterState,
    GateDecision,
    GateStatus,
    GateType,
    WorkflowStatus,
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateWorkflow(Input):
    event_id: UUID
    project_id: UUID
    chapter_id: UUID
    definition_id: str = Field(default="chapter-production", pattern=r"^[a-z][a-z0-9-]{0,79}$")
    definition_version: int = Field(default=1, strict=True, ge=1)


class CommandInput(Input):
    event_id: UUID
    expected_state_version: int = Field(strict=True, ge=1)
    reason: str = Field(default="User command", min_length=1, max_length=2000)


class EventInput(CommandInput):
    event_type: Literal["USER_SUBMITTED", "BLOCK", "PAUSE", "RESUME", "CANCEL"]


class GateInput(CommandInput):
    expected_artifact_version: int = Field(strict=True, ge=1)
    decision: GateDecision


class FakeInput(Input):
    event_id: UUID
    expected_state_version: int = Field(strict=True, ge=1)
    origin_state: ChapterState
    outcome: Literal[
        "success", "review_failure", "technical_failure", "fatal_failure", "replan"
    ] = "success"


class WorkflowView(BaseModel):
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_definition_id: str
    workflow_definition_version: int
    current_state: ChapterState
    status: WorkflowStatus
    state_version: int
    retry_count: int
    state_retry_count: int
    revision_count: int
    planning_iteration_count: int
    plan_version: int | None
    draft_version: int | None
    resume_state: ChapterState | None
    resume_status: WorkflowStatus | None
    block_reason: str | None
    blocked_guard: str | None
    simulation: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class DispatchView(BaseModel):
    workflow: WorkflowView
    outcome: str
    duplicate: bool
    error_code: str | None


class GateView(BaseModel):
    id: UUID
    workflow_id: UUID
    gate_type: GateType
    status: GateStatus
    artifact_id: UUID
    artifact_version: int
    opened_state_version: int
    decision_event_id: UUID | None
    decided_by: str | None
    decision: GateDecision | None
    reason: str | None
    created_at: datetime
    decided_at: datetime | None


class TransitionView(BaseModel):
    id: UUID
    workflow_id: UUID
    event_id: UUID
    from_state: ChapterState | None
    to_state: ChapterState
    from_status: WorkflowStatus | None
    to_status: WorkflowStatus
    from_version: int
    to_version: int
    guards: list[str]
    reason: str
    audit_record_id: UUID
    created_at: datetime
