"""Workflow values and persisted records; no framework or persistence dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now
from novel_os.domain.enums import ActorType


class ChapterState(StrEnum):
    C00_CREATED = "C00_CREATED"
    C01_REQUIREMENT_INTAKE = "C01_REQUIREMENT_INTAKE"
    C02_CONTEXT_ASSEMBLY = "C02_CONTEXT_ASSEMBLY"
    C03_REQUIREMENT_READY = "C03_REQUIREMENT_READY"
    C04_CHAPTER_PLANNING = "C04_CHAPTER_PLANNING"
    C05_PLAN_REVIEW = "C05_PLAN_REVIEW"
    C06_PLAN_APPROVAL = "C06_PLAN_APPROVAL"
    C07_WRITING = "C07_WRITING"
    C08_DETERMINISTIC_CHECK = "C08_DETERMINISTIC_CHECK"
    C09_INTERNAL_REVIEW = "C09_INTERNAL_REVIEW"
    C10_REVISION = "C10_REVISION"
    C11_INTERNAL_PASS = "C11_INTERNAL_PASS"
    C12_USER_REVIEW = "C12_USER_REVIEW"
    C13_USER_FEEDBACK_DIAGNOSIS = "C13_USER_FEEDBACK_DIAGNOSIS"
    C14_MEMORY_PREPARATION = "C14_MEMORY_PREPARATION"
    C15_MEMORY_COMMIT = "C15_MEMORY_COMMIT"
    C16_COMPLETED = "C16_COMPLETED"
    C90_BLOCKED = "C90_BLOCKED"
    C91_FAILED = "C91_FAILED"
    C92_CANCELLED = "C92_CANCELLED"


class WorkflowStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_AGENT = "WAITING_AGENT"
    WAITING_HUMAN = "WAITING_HUMAN"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GateType(StrEnum):
    PLAN_APPROVAL = "PLAN_APPROVAL"
    CHAPTER_ACCEPTANCE = "CHAPTER_ACCEPTANCE"


class GateStatus(StrEnum):
    CREATED = "CREATED"
    WAITING = "WAITING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class GateDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    REQUEST_ALTERNATIVE = "REQUEST_ALTERNATIVE"
    CANCEL = "CANCEL"


TERMINAL_STATES = frozenset(
    {ChapterState.C16_COMPLETED, ChapterState.C91_FAILED, ChapterState.C92_CANCELLED}
)
GATE_STATES = {
    ChapterState.C06_PLAN_APPROVAL: GateType.PLAN_APPROVAL,
    ChapterState.C12_USER_REVIEW: GateType.CHAPTER_ACCEPTANCE,
}


@dataclass(frozen=True, kw_only=True)
class WorkflowDefinition:
    id: str
    version: int
    body: dict
    digest: str
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class WorkflowInstance:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    chapter_id: UUID
    workflow_definition_id: str
    workflow_definition_version: int
    current_state: ChapterState = ChapterState.C00_CREATED
    status: WorkflowStatus = WorkflowStatus.CREATED
    state_version: int = 1
    retry_count: int = 0
    state_retry_count: int = 0
    revision_count: int = 0
    planning_iteration_count: int = 0
    plan_version: int | None = None
    draft_version: int | None = None
    resume_state: ChapterState | None = None
    resume_status: WorkflowStatus | None = None
    resume_new_stage: bool = False
    block_reason: str | None = None
    blocked_guard: str | None = None
    simulation: bool = True
    created_by: str
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class WorkflowEvent:
    event_id: UUID
    workflow_id: UUID
    event_type: str
    expected_state_version: int
    origin_state: ChapterState | None
    actor_type: ActorType
    actor_id: str
    request_id: str
    fingerprint: str
    payload: dict
    result: dict
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class WorkflowTransition:
    id: UUID = field(default_factory=uuid4)
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
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class HumanGate:
    id: UUID = field(default_factory=uuid4)
    workflow_id: UUID
    gate_type: GateType
    status: GateStatus = GateStatus.WAITING
    artifact_id: UUID
    artifact_version: int
    opened_state_version: int
    decision_event_id: UUID | None = None
    decided_by: str | None = None
    decision: GateDecision | None = None
    reason: str | None = None
    created_at: datetime = field(default_factory=now)
    decided_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class EventCommand:
    event_id: UUID
    event_type: str
    expected_state_version: int
    origin_state: ChapterState | None = None
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchResult:
    workflow: dict
    outcome: str = "APPLIED"
    duplicate: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class GuardFailure:
    code: str
    message: str
    guard: str
    recovery_state: ChapterState | None = None
