from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.domain.agents import AgentId, ResultStatus, RunStatus, TaskStatus
from novel_os.domain.workflow import ChapterState
from novel_os.models.core import enum_type


class AgentTaskModel(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_instance_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
        ),
        ForeignKeyConstraint(["target_ref", "project_id"], ["chapters.id", "chapters.project_id"]),
        ForeignKeyConstraint(
            ["result_ref", "task_id"],
            ["agent_runs.run_id", "agent_runs.task_id"],
            name="fk_agent_tasks_result_run",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "workflow_instance_id",
            "workflow_state_version",
            "task_type",
            name="uq_agent_tasks_logical_stage",
        ),
        CheckConstraint("version > 0 AND workflow_state_version > 0", name="positive_versions"),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts "
            "AND max_attempts BETWEEN 1 AND 10",
            name="attempt_budget",
        ),
        CheckConstraint("priority BETWEEN -100 AND 100", name="priority_range"),
        CheckConstraint(
            "(status IN ('CLAIMED','RUNNING')) = (lease_owner IS NOT NULL "
            "AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND heartbeat_at IS NOT NULL)",
            name="lease_required",
        ),
        Index("ix_agent_tasks_claim", "status", "priority", "available_at", "lease_expires_at"),
    )
    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    workflow_instance_id: Mapped[UUID] = mapped_column(index=True)
    workflow_state: Mapped[ChapterState] = mapped_column(enum_type(ChapterState))
    workflow_state_version: Mapped[int]
    agent_id: Mapped[AgentId] = mapped_column(enum_type(AgentId))
    task_type: Mapped[str] = mapped_column(String(80))
    objective: Mapped[str] = mapped_column(Text)
    target_ref: Mapped[UUID]
    requirements: Mapped[list] = mapped_column(JSONB)
    constraints: Mapped[list] = mapped_column(JSONB)
    capabilities: Mapped[list] = mapped_column(JSONB)
    expected_output_schema: Mapped[str] = mapped_column(String(80))
    status: Mapped[TaskStatus] = mapped_column(enum_type(TaskStatus))
    priority: Mapped[int]
    attempt_count: Mapped[int]
    max_attempts: Mapped[int]
    version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    result_ref: Mapped[UUID | None]
    result_metadata: Mapped[dict] = mapped_column(JSONB)


class AgentRunModel(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number"),
        UniqueConstraint("run_id", "task_id"),
        UniqueConstraint("lease_token"),
        CheckConstraint("attempt_number > 0", name="positive_attempt"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="nonnegative_duration"),
        CheckConstraint(
            "(status IN ('CLAIMED','RUNNING')) = (finished_at IS NULL)", name="terminal_timestamp"
        ),
    )
    run_id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), index=True)
    attempt_number: Mapped[int]
    worker_id: Mapped[str] = mapped_column(String(128))
    lease_token: Mapped[UUID]
    status: Mapped[RunStatus] = mapped_column(enum_type(RunStatus))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None]
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    input_metadata: Mapped[dict] = mapped_column(JSONB)
    output_metadata: Mapped[dict] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_status: Mapped[ResultStatus | None] = mapped_column(enum_type(ResultStatus))
    disposition: Mapped[str | None] = mapped_column(String(40))
