"""Execution records and capabilities; independent of web, ORM and model providers."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now
from novel_os.domain.workflow import ChapterState


class AgentId(StrEnum):
    A01_ORCHESTRATOR = "A01_ORCHESTRATOR"
    A02_REQUIREMENT = "A02_REQUIREMENT"
    A03_PLANNING = "A03_PLANNING"
    A04_WRITING = "A04_WRITING"
    A05_REVIEW = "A05_REVIEW"
    A06_REVISION = "A06_REVISION"
    A07_MEMORY = "A07_MEMORY"


class Capability(StrEnum):
    REPORT_RESULT = "REPORT_RESULT"
    PROPOSE_PLAN = "PROPOSE_PLAN"
    PROPOSE_DRAFT = "PROPOSE_DRAFT"
    REVIEW = "REVIEW"
    APPROVE = "APPROVE"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    COMMIT_CANON = "COMMIT_CANON"
    SET_WORKFLOW_STATE = "SET_WORKFLOW_STATE"
    DIRECT_DATABASE_WRITE = "DIRECT_DATABASE_WRITE"


FORBIDDEN_CAPABILITIES = frozenset(Capability) - {
    Capability.REPORT_RESULT,
    Capability.PROPOSE_PLAN,
    Capability.PROPOSE_DRAFT,
    Capability.REVIEW,
}


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    CANCELLED = "CANCELLED"


class ResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    FAILED = "FAILED"


class MockScenario(StrEnum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FORMAT_ERROR_ONCE = "FORMAT_ERROR_ONCE"
    MODEL_ERROR_ONCE = "MODEL_ERROR_ONCE"
    ALWAYS_FAIL = "ALWAYS_FAIL"
    AUTHORITY_VIOLATION = "AUTHORITY_VIOLATION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    SLOW_SUCCESS = "SLOW_SUCCESS"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    QUALITY_FAIL = "QUALITY_FAIL"


@dataclass(frozen=True, kw_only=True)
class AgentDefinition:
    agent_id: AgentId
    name: str
    mission: str
    accepted_task_types: tuple[str, ...]
    default_capabilities: frozenset[Capability]
    result_schema: str = "mock-agent-result.v1"
    enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class AgentTask:
    task_id: UUID = field(default_factory=uuid4)
    project_id: UUID
    workflow_instance_id: UUID
    workflow_state: ChapterState
    workflow_state_version: int
    agent_id: AgentId
    task_type: str
    objective: str
    target_ref: UUID
    requirements: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    expected_output_schema: str = "mock-agent-result.v1"
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    attempt_count: int = 0
    max_attempts: int = 3
    version: int = 1
    created_at: datetime = field(default_factory=now)
    available_at: datetime = field(default_factory=now)
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_owner: str | None = None
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    result_ref: UUID | None = None
    result_metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class AgentRun:
    run_id: UUID = field(default_factory=uuid4)
    task_id: UUID
    attempt_number: int
    worker_id: str
    lease_token: UUID
    status: RunStatus = RunStatus.CLAIMED
    claimed_at: datetime = field(default_factory=now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    provider: str = "mock"
    model: str = "mock-v1"
    input_metadata: dict = field(default_factory=dict)
    output_metadata: dict = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    result_status: ResultStatus | None = None
    disposition: str | None = None


@dataclass(frozen=True)
class TaskLease:
    task_id: UUID
    run_id: UUID
    worker_id: str
    token: UUID
    attempt_number: int
