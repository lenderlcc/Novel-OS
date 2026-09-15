"""Writing task bindings and generation evidence

Revision ID: 0009_writing_agent
Revises: 0008_requirement_planning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_writing_agent"
down_revision: str | Sequence[str] | None = "0008_requirement_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "writing_task_bindings",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("expected_draft_version", sa.Integer(), nullable=False),
        sa.Column("profile_json", sa.Text(), nullable=False),
        sa.Column("source_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(source_snapshots) = 'array'",
            name=op.f("ck_writing_task_bindings_snapshot_shape"),
        ),
        sa.CheckConstraint(
            "plan_version > 0 AND expected_draft_version >= 0",
            name=op.f("ck_writing_task_bindings_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_writing_task_bindings_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["chapter_plans.id"],
            name=op.f("fk_writing_task_bindings_plan_id_chapter_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["agent_tasks.task_id"],
            name=op.f("fk_writing_task_bindings_task_id_agent_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
            name=op.f("fk_writing_task_bindings_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("task_id", name=op.f("pk_writing_task_bindings")),
    )
    op.create_table(
        "writing_generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("agent_task_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("context_package_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column("chapter_version_id", sa.Uuid(), nullable=True),
        sa.Column("model_profile", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("check_status", sa.String(length=20), nullable=False),
        sa.Column("check_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(check_status = 'PASS' AND chapter_version_id IS NOT NULL) OR "
            "(check_status = 'BLOCKED' AND chapter_version_id IS NULL)",
            name=op.f("ck_writing_generations_check_relation"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object' AND jsonb_typeof(check_codes) = 'array'",
            name=op.f("ck_writing_generations_metadata_shape"),
        ),
        sa.CheckConstraint("plan_version > 0", name=op.f("ck_writing_generations_plan_version")),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.run_id"],
            name=op.f("fk_writing_generations_agent_run_id_agent_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_task_id"],
            ["writing_task_bindings.task_id"],
            name=op.f("fk_writing_generations_agent_task_id_writing_task_bindings"),
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["creative_briefs.id"],
            name=op.f("fk_writing_generations_brief_id_creative_briefs"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_writing_generations_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_version_id"],
            ["chapter_versions.id"],
            name=op.f("fk_writing_generations_chapter_version_id_chapter_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["context_package_id"],
            ["context_packages.context_package_id"],
            name=op.f("fk_writing_generations_context_package_id_context_packages"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["chapter_plans.id"],
            name=op.f("fk_writing_generations_plan_id_chapter_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_lineage_id"],
            ["prompt_lineages.lineage_id"],
            name=op.f("fk_writing_generations_prompt_lineage_id_prompt_lineages"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
            name=op.f("fk_writing_generations_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_writing_generations")),
        sa.UniqueConstraint("agent_run_id", name=op.f("uq_writing_generations_agent_run_id")),
        sa.UniqueConstraint("agent_task_id", name=op.f("uq_writing_generations_agent_task_id")),
        sa.UniqueConstraint(
            "chapter_version_id", name=op.f("uq_writing_generations_chapter_version_id")
        ),
    )
    op.create_index(
        op.f("ix_writing_generations_workflow_id"),
        "writing_generations",
        ["workflow_id"],
        unique=False,
    )

    guards()


def downgrade() -> None:
    for table in ("writing_generations", "writing_task_bindings"):
        op.execute(f"DROP TRIGGER writing_evidence_guard ON {table}")
    op.execute("DROP FUNCTION guard_writing_evidence()")
    op.drop_index(op.f("ix_writing_generations_workflow_id"), table_name="writing_generations")
    op.drop_table("writing_generations")
    op.drop_table("writing_task_bindings")


def guards():
    op.execute("""
    CREATE FUNCTION guard_writing_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE t agent_tasks; b writing_task_bindings;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Writing evidence is immutable' USING ERRCODE='23514';
        END IF;
        IF TG_TABLE_NAME = 'writing_task_bindings' THEN
            SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
        ELSE
            SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.agent_task_id;
        END IF;
        IF t.task_id IS NULL OR t.task_type <> 'WRITE_CHAPTER' OR t.agent_id <> 'A04_WRITING'
           OR t.workflow_state <> 'C07_WRITING'
           OR (t.project_id,t.target_ref,t.workflow_instance_id) IS DISTINCT FROM
              (NEW.project_id,NEW.chapter_id,NEW.workflow_id)
           OR NOT EXISTS (SELECT 1 FROM workflow_instances w WHERE w.id=NEW.workflow_id
               AND w.chapter_id=NEW.chapter_id AND w.project_id=NEW.project_id
               AND w.workflow_definition_id='chapter-planning' AND w.workflow_definition_version=2
               AND NOT w.simulation AND w.current_state='C07_WRITING'
               AND w.state_version=t.workflow_state_version AND w.status='WAITING_AGENT')
           OR NOT EXISTS (SELECT 1 FROM chapter_plans p JOIN chapters c ON c.id=p.chapter_id
               WHERE p.id=NEW.plan_id AND p.version=NEW.plan_version
               AND p.chapter_id=NEW.chapter_id AND p.project_id=NEW.project_id
               AND p.approved_at IS NOT NULL AND p.status IN ('APPROVED','LOCKED')
               AND c.approved_plan_version=p.version) THEN
            RAISE EXCEPTION 'Writing task Plan binding mismatch' USING ERRCODE='23514';
        END IF;
        IF TG_TABLE_NAME = 'writing_generations' THEN
            SELECT * INTO b FROM writing_task_bindings WHERE task_id=NEW.agent_task_id;
            IF (b.plan_id,b.plan_version) IS DISTINCT FROM (NEW.plan_id,NEW.plan_version)
               OR NOT EXISTS (SELECT 1 FROM agent_runs WHERE run_id=NEW.agent_run_id
                    AND task_id=NEW.agent_task_id AND status='RUNNING')
               OR NOT EXISTS (SELECT 1 FROM prompt_lineages WHERE lineage_id=NEW.prompt_lineage_id
                    AND agent_run_id=NEW.agent_run_id AND task_id=NEW.agent_task_id
                    AND output_schema_id='chapter-writing-result' AND output_schema_version=1
                    AND model_profile_id=NEW.model_profile
                    AND model_profile->>'provider'=NEW.provider
                    AND model_profile->>'model'=NEW.model)
               OR NOT EXISTS (SELECT 1 FROM context_packages
                    WHERE context_package_id=NEW.context_package_id
                    AND agent_run_id=NEW.agent_run_id AND task_id=NEW.agent_task_id
                    AND profile_id='CP-005' AND build_status='READY')
               OR NOT EXISTS (SELECT 1 FROM plan_generations WHERE plan_id=NEW.plan_id
                    AND brief_id=NEW.brief_id AND workflow_id=NEW.workflow_id)
               OR NEW.metadata ?| ARRAY['content','status','authority_level',
                    'approved_at','version',
                    'next_state','event','next_event','quality_pass','system_actor']
               OR NEW.metadata->>'chapter_id' IS DISTINCT FROM NEW.chapter_id::text
               OR NEW.metadata->>'plan_id' IS DISTINCT FROM NEW.plan_id::text
               OR NEW.metadata->>'plan_version' IS DISTINCT FROM NEW.plan_version::text
            THEN
                RAISE EXCEPTION 'Writing lineage mismatch' USING ERRCODE='23514';
            END IF;
            IF NEW.check_status='PASS' AND (NEW.check_codes <> '[]'::jsonb OR NOT EXISTS
                (SELECT 1 FROM chapter_versions v JOIN chapters c ON c.id=v.chapter_id
                 WHERE v.id=NEW.chapter_version_id AND v.chapter_id=NEW.chapter_id
                   AND v.project_id=NEW.project_id AND v.version=b.expected_draft_version+1
                   AND c.current_version=v.version AND v.status='DRAFT'
                   AND v.authority_level='A7_AI_INFERENCE' AND v.source='AGENT'
                   AND v.approved_at IS NULL AND NOT v.locked
                   AND length(btrim(v.content))>0
                   AND encode(sha256(convert_to(v.content,'UTF8')), 'hex')=NEW.content_hash)) THEN
                RAISE EXCEPTION 'Writing Draft relation mismatch' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    """)
    for table in ("writing_task_bindings", "writing_generations"):
        op.execute(
            f"CREATE TRIGGER writing_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION guard_writing_evidence()"
        )
