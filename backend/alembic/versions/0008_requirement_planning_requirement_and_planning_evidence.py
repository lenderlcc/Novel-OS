"""Requirement and planning evidence

Revision ID: 0008_requirement_planning
Revises: 0007_context_engine
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_requirement_planning"
down_revision: str | Sequence[str] | None = "0007_context_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_workflow_instances_simulation_only"), "workflow_instances", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_workflow_instances_supported_execution"),
        "workflow_instances",
        "simulation OR workflow_definition_id = 'chapter-planning'",
    )

    op.create_table(
        "creative_briefs",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_requirement", sa.Text(), nullable=False),
        sa.Column("input_event_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("context_package_id", sa.Uuid(), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(body) = 'object' AND jsonb_typeof(source_versions) = 'array'",
            name=op.f("ck_creative_briefs_json_shapes"),
        ),
        sa.CheckConstraint(
            "status IN ('READY', 'NEEDS_HUMAN', 'SUPERSEDED')",
            name=op.f("ck_creative_briefs_brief_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_creative_briefs_positive_version")),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.run_id"],
            name=op.f("fk_creative_briefs_agent_run_id_agent_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_creative_briefs_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["context_package_id"],
            ["context_packages.context_package_id"],
            name=op.f("fk_creative_briefs_context_package_id_context_packages"),
        ),
        sa.ForeignKeyConstraint(
            ["input_event_id"],
            ["workflow_events.event_id"],
            name=op.f("fk_creative_briefs_input_event_id_workflow_events"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_lineage_id"],
            ["prompt_lineages.lineage_id"],
            name=op.f("fk_creative_briefs_prompt_lineage_id_prompt_lineages"),
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["creative_briefs.id"],
            name=op.f("fk_creative_briefs_supersedes_id_creative_briefs"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
            name=op.f("fk_creative_briefs_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_briefs")),
        sa.UniqueConstraint("agent_run_id", name=op.f("uq_creative_briefs_agent_run_id")),
        sa.UniqueConstraint("workflow_id", "version", name=op.f("uq_creative_briefs_workflow_id")),
    )
    op.create_index(
        op.f("ix_creative_briefs_workflow_id"), "creative_briefs", ["workflow_id"], unique=False
    )
    op.create_table(
        "plan_generations",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("planning_iteration", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("context_package_id", sa.Uuid(), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(body) = 'object' AND jsonb_typeof(source_versions) = 'array'",
            name=op.f("ck_plan_generations_json_shapes"),
        ),
        sa.CheckConstraint(
            "planning_iteration > 0", name=op.f("ck_plan_generations_positive_iteration")
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.run_id"],
            name=op.f("fk_plan_generations_agent_run_id_agent_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["creative_briefs.id"],
            name=op.f("fk_plan_generations_brief_id_creative_briefs"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_plan_generations_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["context_package_id"],
            ["context_packages.context_package_id"],
            name=op.f("fk_plan_generations_context_package_id_context_packages"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["chapter_plans.id"],
            name=op.f("fk_plan_generations_plan_id_chapter_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_lineage_id"],
            ["prompt_lineages.lineage_id"],
            name=op.f("fk_plan_generations_prompt_lineage_id_prompt_lineages"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
            name=op.f("fk_plan_generations_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_generations")),
        sa.UniqueConstraint("agent_run_id", name=op.f("uq_plan_generations_agent_run_id")),
        sa.UniqueConstraint("plan_id", name=op.f("uq_plan_generations_plan_id")),
    )
    op.create_index(
        op.f("ix_plan_generations_workflow_id"), "plan_generations", ["workflow_id"], unique=False
    )
    op.create_table(
        "plan_review_reports",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.String(length=24), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("context_package_id", sa.Uuid(), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(body) = 'object' AND jsonb_typeof(source_versions) = 'array'",
            name=op.f("ck_plan_review_reports_json_shapes"),
        ),
        sa.CheckConstraint(
            "verdict IN ('PASS', 'PASS_WITH_WARNINGS', 'FAIL')",
            name=op.f("ck_plan_review_reports_review_verdict"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.run_id"],
            name=op.f("fk_plan_review_reports_agent_run_id_agent_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"],
            ["creative_briefs.id"],
            name=op.f("fk_plan_review_reports_brief_id_creative_briefs"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name=op.f("fk_plan_review_reports_chapter_id_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["context_package_id"],
            ["context_packages.context_package_id"],
            name=op.f("fk_plan_review_reports_context_package_id_context_packages"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plan_generations.plan_id"],
            name=op.f("fk_plan_review_reports_plan_id_plan_generations"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_lineage_id"],
            ["prompt_lineages.lineage_id"],
            name=op.f("fk_plan_review_reports_prompt_lineage_id_prompt_lineages"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
            name=op.f("fk_plan_review_reports_workflow_id_workflow_instances"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_review_reports")),
        sa.UniqueConstraint("agent_run_id", name=op.f("uq_plan_review_reports_agent_run_id")),
    )
    op.create_index(
        op.f("ix_plan_review_reports_plan_id"), "plan_review_reports", ["plan_id"], unique=False
    )
    op.create_index(
        op.f("ix_plan_review_reports_workflow_id"),
        "plan_review_reports",
        ["workflow_id"],
        unique=False,
    )
    install_guards()


def downgrade() -> None:
    op.execute("DROP TRIGGER planning_plan_immutable ON chapter_plans")
    op.execute("DROP TRIGGER planning_workflow_binding ON workflow_instances")
    op.drop_constraint(
        op.f("ck_workflow_instances_supported_execution"), "workflow_instances", type_="check"
    )
    # Preserve business history; legacy new writes remain simulation-only.
    op.execute(
        "ALTER TABLE workflow_instances ADD CONSTRAINT ck_workflow_instances_simulation_only "
        "CHECK (simulation) NOT VALID"
    )

    op.drop_index(op.f("ix_plan_review_reports_workflow_id"), table_name="plan_review_reports")
    op.drop_index(op.f("ix_plan_review_reports_plan_id"), table_name="plan_review_reports")
    op.drop_table("plan_review_reports")
    op.drop_index(op.f("ix_plan_generations_workflow_id"), table_name="plan_generations")
    op.drop_table("plan_generations")
    op.drop_index(op.f("ix_creative_briefs_workflow_id"), table_name="creative_briefs")
    op.drop_table("creative_briefs")
    op.execute("DROP FUNCTION guard_planning_evidence(); DROP FUNCTION guard_planning_workflow();")


def install_guards():
    op.execute("""
    CREATE FUNCTION guard_planning_workflow() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM workflow_definitions d WHERE d.id = NEW.workflow_definition_id
            AND d.version = NEW.workflow_definition_version AND (d.body->>'simulation')::boolean =
            NEW.simulation) THEN
            RAISE EXCEPTION 'Workflow definition mode mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER planning_workflow_binding BEFORE INSERT ON workflow_instances
        FOR EACH ROW EXECUTE FUNCTION guard_planning_workflow();
    CREATE FUNCTION guard_planning_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE task_record agent_tasks; expected_type text;
    BEGIN
        IF TG_TABLE_NAME = 'chapter_plans' THEN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Plans cannot be deleted' USING ERRCODE='23514';
            END IF;
            IF EXISTS (SELECT 1 FROM plan_generations WHERE plan_id = OLD.id)
              AND (TG_OP = 'DELETE' OR (to_jsonb(OLD) -
            ARRAY['status','authority_level','locked','updated_at','approved_at','approved_by'])
                   IS DISTINCT FROM (to_jsonb(NEW) -
            ARRAY['status','authority_level','locked','updated_at','approved_at','approved_by']))
            THEN
                RAISE EXCEPTION 'Generated plan content is immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END IF;
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Planning evidence cannot be deleted' USING ERRCODE='23514';
        END IF;
        IF TG_OP = 'UPDATE' THEN
            IF TG_TABLE_NAME = 'creative_briefs' AND (to_jsonb(OLD) - 'status') = (to_jsonb(NEW) -
            'status')
                AND to_jsonb(NEW)->>'status' = 'SUPERSEDED' THEN RETURN NEW; END IF;
            RAISE EXCEPTION 'Planning evidence is immutable' USING ERRCODE='23514';
        END IF;
        SELECT t.* INTO task_record FROM agent_tasks t JOIN agent_runs r ON r.task_id=t.task_id
            WHERE r.run_id=NEW.agent_run_id;
        expected_type := CASE TG_TABLE_NAME WHEN 'creative_briefs' THEN 'PARSE_CHAPTER_REQUIREMENT'
                         WHEN 'plan_generations' THEN 'PLAN_CHAPTER' ELSE 'REVIEW_CHAPTER_PLAN' END;
        IF task_record.task_id IS NULL OR task_record.task_type <> expected_type
           OR (task_record.project_id,task_record.target_ref,task_record.workflow_instance_id)
              IS DISTINCT FROM (NEW.project_id,NEW.chapter_id,NEW.workflow_id)
           OR NOT EXISTS (SELECT 1 FROM prompt_lineages WHERE lineage_id=NEW.prompt_lineage_id AND
            agent_run_id=NEW.agent_run_id)
           OR NOT EXISTS (SELECT 1 FROM context_packages WHERE
            context_package_id=NEW.context_package_id AND agent_run_id=NEW.agent_run_id AND
            build_status='READY') THEN
            RAISE EXCEPTION 'Planning lineage binding mismatch' USING ERRCODE='23514';
        END IF;
        IF TG_TABLE_NAME = 'creative_briefs' THEN
            IF NOT EXISTS (SELECT 1 FROM workflow_events WHERE event_id=NEW.input_event_id AND
            workflow_id=NEW.workflow_id AND actor_type='USER') THEN
                RAISE EXCEPTION 'Brief input binding mismatch' USING ERRCODE='23514';
            END IF;
        ELSE
            IF NOT EXISTS (SELECT 1 FROM creative_briefs WHERE id=NEW.brief_id AND
            project_id=NEW.project_id
                AND chapter_id=NEW.chapter_id AND workflow_id=NEW.workflow_id AND status='READY')
               OR NOT EXISTS (SELECT 1 FROM chapter_plans WHERE id=NEW.plan_id AND
            project_id=NEW.project_id AND chapter_id=NEW.chapter_id) THEN
                RAISE EXCEPTION 'Plan brief binding mismatch' USING ERRCODE='23514';
            END IF;
            IF TG_TABLE_NAME = 'plan_review_reports' AND NOT EXISTS
                (SELECT 1 FROM plan_generations WHERE plan_id=NEW.plan_id AND
            brief_id=NEW.brief_id AND workflow_id=NEW.workflow_id) THEN
                RAISE EXCEPTION 'Review generation binding mismatch' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER planning_plan_immutable BEFORE UPDATE OR DELETE ON chapter_plans
        FOR EACH ROW EXECUTE FUNCTION guard_planning_evidence();
    """)
    for table in ("creative_briefs", "plan_generations", "plan_review_reports"):
        op.execute(
            f"CREATE TRIGGER planning_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION guard_planning_evidence()"
        )
