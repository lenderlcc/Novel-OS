"""chapter workflow engine

Revision ID: 0003_workflow_engine
Revises: 0002_core_domain
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_workflow_engine"
down_revision: str | Sequence[str] | None = "0002_core_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_workflow_definitions_positive_version")),
        sa.PrimaryKeyConstraint("id", "version", name=op.f("pk_workflow_definitions")),
    )
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_id", sa.String(length=80), nullable=False),
        sa.Column("workflow_definition_version", sa.Integer(), nullable=False),
        sa.Column(
            "current_state",
            sa.Enum(
                "C00_CREATED",
                "C01_REQUIREMENT_INTAKE",
                "C02_CONTEXT_ASSEMBLY",
                "C03_REQUIREMENT_READY",
                "C04_CHAPTER_PLANNING",
                "C05_PLAN_REVIEW",
                "C06_PLAN_APPROVAL",
                "C07_WRITING",
                "C08_DETERMINISTIC_CHECK",
                "C09_INTERNAL_REVIEW",
                "C10_REVISION",
                "C11_INTERNAL_PASS",
                "C12_USER_REVIEW",
                "C13_USER_FEEDBACK_DIAGNOSIS",
                "C14_MEMORY_PREPARATION",
                "C15_MEMORY_COMMIT",
                "C16_COMPLETED",
                "C90_BLOCKED",
                "C91_FAILED",
                "C92_CANCELLED",
                name="current_state_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_AGENT",
                "WAITING_HUMAN",
                "PAUSED",
                "BLOCKED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="status_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("state_retry_count", sa.Integer(), nullable=False),
        sa.Column("revision_count", sa.Integer(), nullable=False),
        sa.Column("planning_iteration_count", sa.Integer(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=True),
        sa.Column("draft_version", sa.Integer(), nullable=True),
        sa.Column(
            "resume_state",
            sa.Enum(
                "C00_CREATED",
                "C01_REQUIREMENT_INTAKE",
                "C02_CONTEXT_ASSEMBLY",
                "C03_REQUIREMENT_READY",
                "C04_CHAPTER_PLANNING",
                "C05_PLAN_REVIEW",
                "C06_PLAN_APPROVAL",
                "C07_WRITING",
                "C08_DETERMINISTIC_CHECK",
                "C09_INTERNAL_REVIEW",
                "C10_REVISION",
                "C11_INTERNAL_PASS",
                "C12_USER_REVIEW",
                "C13_USER_FEEDBACK_DIAGNOSIS",
                "C14_MEMORY_PREPARATION",
                "C15_MEMORY_COMMIT",
                "C16_COMPLETED",
                "C90_BLOCKED",
                "C91_FAILED",
                "C92_CANCELLED",
                name="resume_state_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "resume_status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_AGENT",
                "WAITING_HUMAN",
                "PAUSED",
                "BLOCKED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="resume_status_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("blocked_guard", sa.String(length=40), nullable=True),
        sa.Column("simulation", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(current_state = 'C16_COMPLETED') = (status = 'COMPLETED') "
            "AND (current_state = 'C91_FAILED') = (status = 'FAILED') "
            "AND (current_state = 'C92_CANCELLED') = (status = 'CANCELLED') "
            "AND (current_state = 'C90_BLOCKED') = (status = 'BLOCKED')",
            name=op.f("ck_workflow_instances_state_status_consistency"),
        ),
        sa.CheckConstraint(
            "retry_count >= 0 AND state_retry_count >= 0 AND revision_count >= 0 "
            "AND planning_iteration_count >= 0",
            name=op.f("ck_workflow_instances_nonnegative_counters"),
        ),
        sa.CheckConstraint("simulation", name=op.f("ck_workflow_instances_simulation_only")),
        sa.CheckConstraint(
            "state_version > 0", name=op.f("ck_workflow_instances_positive_state_version")
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_workflow_instances_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_workflow_instances_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_id", "workflow_definition_version"],
            ["workflow_definitions.id", "workflow_definitions.version"],
            name=op.f("fk_workflow_instances_workflow_definition_id_workflow_definitions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_instances")),
    )
    op.create_index(
        op.f("ix_workflow_instances_project_id"), "workflow_instances", ["project_id"], unique=False
    )
    op.create_index(
        "uq_workflow_active_chapter",
        "workflow_instances",
        ["chapter_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')"),
    )
    op.create_table(
        "workflow_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("expected_state_version", sa.Integer(), nullable=False),
        sa.Column(
            "origin_state",
            sa.Enum(
                "C00_CREATED",
                "C01_REQUIREMENT_INTAKE",
                "C02_CONTEXT_ASSEMBLY",
                "C03_REQUIREMENT_READY",
                "C04_CHAPTER_PLANNING",
                "C05_PLAN_REVIEW",
                "C06_PLAN_APPROVAL",
                "C07_WRITING",
                "C08_DETERMINISTIC_CHECK",
                "C09_INTERNAL_REVIEW",
                "C10_REVISION",
                "C11_INTERNAL_PASS",
                "C12_USER_REVIEW",
                "C13_USER_FEEDBACK_DIAGNOSIS",
                "C14_MEMORY_PREPARATION",
                "C15_MEMORY_COMMIT",
                "C16_COMPLETED",
                "C90_BLOCKED",
                "C91_FAILED",
                "C92_CANCELLED",
                name="chapterstate",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "actor_type",
            sa.Enum(
                "USER",
                "AGENT",
                "SYSTEM",
                name="actortype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_instances.id"],
            name=op.f("fk_workflow_events_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_workflow_events")),
        sa.UniqueConstraint("event_id", "workflow_id", name=op.f("uq_workflow_events_event_id")),
    )
    op.create_index(
        op.f("ix_workflow_events_workflow_id"), "workflow_events", ["workflow_id"], unique=False
    )
    op.create_table(
        "human_gates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column(
            "gate_type",
            sa.Enum(
                "PLAN_APPROVAL",
                "CHAPTER_ACCEPTANCE",
                name="gatetype",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "WAITING",
                "APPROVED",
                "REJECTED",
                "MODIFIED",
                "CANCELLED",
                "STALE",
                name="gatestatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("opened_state_version", sa.Integer(), nullable=False),
        sa.Column("decision_event_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.String(length=128), nullable=True),
        sa.Column(
            "decision",
            sa.Enum(
                "APPROVE",
                "REJECT",
                "MODIFY",
                "REQUEST_ALTERNATIVE",
                "CANCEL",
                name="gatedecision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "artifact_version > 0 AND opened_state_version > 0",
            name=op.f("ck_human_gates_positive_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["decision_event_id", "workflow_id"],
            ["workflow_events.event_id", "workflow_events.workflow_id"],
            name=op.f("fk_human_gates_decision_event_id_workflow_events"),
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_instances.id"],
            name=op.f("fk_human_gates_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_human_gates")),
        sa.UniqueConstraint(
            "workflow_id", "opened_state_version", name=op.f("uq_human_gates_workflow_id")
        ),
    )
    op.create_index(
        op.f("ix_human_gates_workflow_id"), "human_gates", ["workflow_id"], unique=False
    )
    op.create_index(
        "uq_human_gate_waiting",
        "human_gates",
        ["workflow_id"],
        unique=True,
        postgresql_where=sa.text("status = 'WAITING'"),
    )
    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_state",
            sa.Enum(
                "C00_CREATED",
                "C01_REQUIREMENT_INTAKE",
                "C02_CONTEXT_ASSEMBLY",
                "C03_REQUIREMENT_READY",
                "C04_CHAPTER_PLANNING",
                "C05_PLAN_REVIEW",
                "C06_PLAN_APPROVAL",
                "C07_WRITING",
                "C08_DETERMINISTIC_CHECK",
                "C09_INTERNAL_REVIEW",
                "C10_REVISION",
                "C11_INTERNAL_PASS",
                "C12_USER_REVIEW",
                "C13_USER_FEEDBACK_DIAGNOSIS",
                "C14_MEMORY_PREPARATION",
                "C15_MEMORY_COMMIT",
                "C16_COMPLETED",
                "C90_BLOCKED",
                "C91_FAILED",
                "C92_CANCELLED",
                name="from_state_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_state",
            sa.Enum(
                "C00_CREATED",
                "C01_REQUIREMENT_INTAKE",
                "C02_CONTEXT_ASSEMBLY",
                "C03_REQUIREMENT_READY",
                "C04_CHAPTER_PLANNING",
                "C05_PLAN_REVIEW",
                "C06_PLAN_APPROVAL",
                "C07_WRITING",
                "C08_DETERMINISTIC_CHECK",
                "C09_INTERNAL_REVIEW",
                "C10_REVISION",
                "C11_INTERNAL_PASS",
                "C12_USER_REVIEW",
                "C13_USER_FEEDBACK_DIAGNOSIS",
                "C14_MEMORY_PREPARATION",
                "C15_MEMORY_COMMIT",
                "C16_COMPLETED",
                "C90_BLOCKED",
                "C91_FAILED",
                "C92_CANCELLED",
                name="to_state_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_AGENT",
                "WAITING_HUMAN",
                "PAUSED",
                "BLOCKED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="from_status_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_AGENT",
                "WAITING_HUMAN",
                "PAUSED",
                "BLOCKED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="to_status_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("from_version", sa.Integer(), nullable=False),
        sa.Column("to_version", sa.Integer(), nullable=False),
        sa.Column("guards", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("audit_record_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "to_version = from_version + 1", name=op.f("ck_workflow_transitions_successor_version")
        ),
        sa.ForeignKeyConstraint(
            ["audit_record_id"],
            ["audit_records.id"],
            name=op.f("fk_workflow_transitions_audit_record_id_audit_records"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id", "workflow_id"],
            ["workflow_events.event_id", "workflow_events.workflow_id"],
            name=op.f("fk_workflow_transitions_event_id_workflow_events"),
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_instances.id"],
            name=op.f("fk_workflow_transitions_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transitions")),
        sa.UniqueConstraint(
            "audit_record_id", name=op.f("uq_workflow_transitions_audit_record_id")
        ),
        sa.UniqueConstraint("event_id", name=op.f("uq_workflow_transitions_event_id")),
        sa.UniqueConstraint(
            "workflow_id", "to_version", name=op.f("uq_workflow_transitions_workflow_id")
        ),
    )
    op.create_index(
        op.f("ix_workflow_transitions_workflow_id"),
        "workflow_transitions",
        ["workflow_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_workflow_instances_chapter_id_chapter_plans",
        "workflow_instances",
        "chapter_plans",
        ["chapter_id", "plan_version"],
        ["chapter_id", "version"],
    )
    op.create_foreign_key(
        "fk_workflow_instances_draft_version",
        "workflow_instances",
        "chapter_versions",
        ["chapter_id", "draft_version"],
        ["chapter_id", "version"],
    )
    install_guards()


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_transitions_workflow_id"), table_name="workflow_transitions")
    op.drop_table("workflow_transitions")
    op.drop_index(
        "uq_human_gate_waiting",
        table_name="human_gates",
        postgresql_where=sa.text("status = 'WAITING'"),
    )
    op.drop_index(op.f("ix_human_gates_workflow_id"), table_name="human_gates")
    op.drop_table("human_gates")
    op.drop_index(op.f("ix_workflow_events_workflow_id"), table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index(
        "uq_workflow_active_chapter",
        table_name="workflow_instances",
        postgresql_where=sa.text("status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')"),
    )
    op.drop_index(op.f("ix_workflow_instances_project_id"), table_name="workflow_instances")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_definitions")
    op.execute("DROP FUNCTION novel_guard_workflow()")


def install_guards() -> None:
    op.execute("""
    CREATE FUNCTION novel_guard_workflow() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Workflow records cannot be deleted' USING ERRCODE = '23514';
      END IF;
      IF TG_TABLE_NAME IN ('workflow_definitions', 'workflow_events', 'workflow_transitions') THEN
        RAISE EXCEPTION 'Workflow history is immutable' USING ERRCODE = '23514';
      END IF;
      IF TG_TABLE_NAME = 'workflow_instances' THEN
        IF (to_jsonb(OLD) - ARRAY['current_state','status','state_version','retry_count',
            'state_retry_count','revision_count','planning_iteration_count','plan_version',
            'draft_version','resume_state','resume_status','block_reason','blocked_guard','updated_at'])
          IS DISTINCT FROM
           (to_jsonb(NEW) - ARRAY['current_state','status','state_version','retry_count',
            'state_retry_count','revision_count','planning_iteration_count','plan_version',
            'draft_version','resume_state','resume_status','block_reason','blocked_guard','updated_at'])
          OR NEW.state_version != OLD.state_version + 1
          OR OLD.current_state IN ('C16_COMPLETED','C91_FAILED','C92_CANCELLED') THEN
          RAISE EXCEPTION 'Invalid workflow update' USING ERRCODE = '23514';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'human_gates' THEN
        IF OLD.status NOT IN ('CREATED','WAITING') OR
           (to_jsonb(OLD) - ARRAY['status','decision_event_id','decided_by',
                                'decision','reason','decided_at'])
           IS DISTINCT FROM
           (to_jsonb(NEW) - ARRAY['status','decision_event_id','decided_by',
                                'decision','reason','decided_at']) THEN
          RAISE EXCEPTION 'Human gate binding and decisions are immutable' USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    """)
    for table in (
        "workflow_definitions",
        "workflow_instances",
        "workflow_events",
        "workflow_transitions",
        "human_gates",
    ):
        op.execute(
            f"CREATE TRIGGER guard_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION novel_guard_workflow()"
        )
