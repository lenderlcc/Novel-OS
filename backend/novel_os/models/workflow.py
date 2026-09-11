from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.domain.enums import ActorType
from novel_os.domain.workflow import (
    ChapterState,
    GateDecision,
    GateStatus,
    GateType,
    WorkflowStatus,
)
from novel_os.models.core import enum_type


class WorkflowDefinitionModel(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (CheckConstraint("version > 0", name="positive_version"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowInstanceModel(Base):
    __tablename__ = "workflow_instances"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_workflow_instances_id_project"),
        ForeignKeyConstraint(["chapter_id", "project_id"], ["chapters.id", "chapters.project_id"]),
        ForeignKeyConstraint(
            ["workflow_definition_id", "workflow_definition_version"],
            ["workflow_definitions.id", "workflow_definitions.version"],
        ),
        ForeignKeyConstraint(
            ["chapter_id", "plan_version"], ["chapter_plans.chapter_id", "chapter_plans.version"]
        ),
        ForeignKeyConstraint(
            ["chapter_id", "draft_version"],
            ["chapter_versions.chapter_id", "chapter_versions.version"],
            name="fk_workflow_instances_draft_version",
        ),
        CheckConstraint("state_version > 0", name="positive_state_version"),
        CheckConstraint(
            "retry_count >= 0 AND state_retry_count >= 0 AND revision_count >= 0 "
            "AND planning_iteration_count >= 0",
            name="nonnegative_counters",
        ),
        CheckConstraint("simulation", name="simulation_only"),
        CheckConstraint(
            "NOT resume_new_stage OR status = 'BLOCKED'", name="recovery_requires_blocked"
        ),
        CheckConstraint(
            "(current_state = 'C16_COMPLETED') = (status = 'COMPLETED') "
            "AND (current_state = 'C91_FAILED') = (status = 'FAILED') "
            "AND (current_state = 'C92_CANCELLED') = (status = 'CANCELLED') "
            "AND (current_state = 'C90_BLOCKED') = (status = 'BLOCKED')",
            name="state_status_consistency",
        ),
        Index(
            "uq_workflow_active_chapter",
            "chapter_id",
            unique=True,
            postgresql_where=text("status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_id: Mapped[UUID]
    workflow_definition_id: Mapped[str] = mapped_column(String(80))
    workflow_definition_version: Mapped[int]
    current_state: Mapped[ChapterState] = mapped_column(
        Enum(ChapterState, native_enum=False, create_constraint=True, name="current_state_enum")
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, create_constraint=True, name="status_enum")
    )
    state_version: Mapped[int]
    retry_count: Mapped[int]
    state_retry_count: Mapped[int]
    revision_count: Mapped[int]
    planning_iteration_count: Mapped[int]
    plan_version: Mapped[int | None]
    draft_version: Mapped[int | None]
    resume_state: Mapped[ChapterState | None] = mapped_column(
        Enum(ChapterState, native_enum=False, create_constraint=True, name="resume_state_enum")
    )
    resume_status: Mapped[WorkflowStatus | None] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, create_constraint=True, name="resume_status_enum")
    )
    resume_new_stage: Mapped[bool] = mapped_column(server_default=text("false"))
    block_reason: Mapped[str | None] = mapped_column(Text)
    blocked_guard: Mapped[str | None] = mapped_column(String(40))
    simulation: Mapped[bool]
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowEventModel(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (UniqueConstraint("event_id", "workflow_id"),)
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_instances.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    expected_state_version: Mapped[int]
    origin_state: Mapped[ChapterState | None] = mapped_column(enum_type(ChapterState))
    actor_type: Mapped[ActorType] = mapped_column(enum_type(ActorType))
    actor_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowTransitionModel(Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "workflow_id"],
            ["workflow_events.event_id", "workflow_events.workflow_id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint("workflow_id", "to_version"),
        UniqueConstraint("event_id"),
        CheckConstraint("to_version = from_version + 1", name="successor_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_instances.id"), index=True)
    event_id: Mapped[UUID]
    from_state: Mapped[ChapterState | None] = mapped_column(
        Enum(ChapterState, native_enum=False, create_constraint=True, name="from_state_enum")
    )
    to_state: Mapped[ChapterState] = mapped_column(
        Enum(ChapterState, native_enum=False, create_constraint=True, name="to_state_enum")
    )
    from_status: Mapped[WorkflowStatus | None] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, create_constraint=True, name="from_status_enum")
    )
    to_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, native_enum=False, create_constraint=True, name="to_status_enum")
    )
    from_version: Mapped[int]
    to_version: Mapped[int]
    guards: Mapped[list] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    audit_record_id: Mapped[UUID] = mapped_column(ForeignKey("audit_records.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HumanGateModel(Base):
    __tablename__ = "human_gates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["decision_event_id", "workflow_id"],
            ["workflow_events.event_id", "workflow_events.workflow_id"],
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint("workflow_id", "opened_state_version"),
        CheckConstraint(
            "artifact_version > 0 AND opened_state_version > 0", name="positive_versions"
        ),
        Index(
            "uq_human_gate_waiting",
            "workflow_id",
            unique=True,
            postgresql_where=text("status = 'WAITING'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_instances.id"), index=True)
    gate_type: Mapped[GateType] = mapped_column(enum_type(GateType))
    status: Mapped[GateStatus] = mapped_column(enum_type(GateStatus))
    artifact_id: Mapped[UUID]
    artifact_version: Mapped[int]
    opened_state_version: Mapped[int]
    decision_event_id: Mapped[UUID | None]
    decided_by: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[GateDecision | None] = mapped_column(enum_type(GateDecision))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
