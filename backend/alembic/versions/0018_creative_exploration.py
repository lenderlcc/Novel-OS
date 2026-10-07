"""Immutable A03 concept diagnostics and exact selected-concept Plan lineage."""

import runpy
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_creative_exploration"
down_revision = "0017_memory_state_transitions"
branch_labels = None
depends_on = None


def compatibility_guards(*, exploration):
    # Reuse the frozen definitions; only the supported workflow versions change.
    previous = runpy.run_path(str(Path(__file__).with_name("0011_quality_review.py")))
    writing_versions = "IN (2,3,4)" if exploration else "IN (2,3)"
    writing = previous["WRITING_GUARD"].replace(
        "w.workflow_definition_version=2", f"w.workflow_definition_version {writing_versions}"
    )
    quality = previous["QUALITY_RELATIONS"].split("CREATE TRIGGER quality_relations", 1)[0]
    quality = quality.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    if exploration:
        quality = quality.replace(
            "w.workflow_definition_version=3", "w.workflow_definition_version IN (3,4)"
        )
    op.execute(writing)
    op.execute(quality)


def upgrade():
    op.create_table(
        "creative_explorations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("brief_id", sa.UUID(), sa.ForeignKey("creative_briefs.id"), nullable=False),
        sa.Column(
            "agent_run_id",
            sa.UUID(),
            sa.ForeignKey("agent_runs.run_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "prompt_lineage_id",
            sa.UUID(),
            sa.ForeignKey("prompt_lineages.lineage_id"),
            nullable=False,
        ),
        sa.Column(
            "context_package_id",
            sa.UUID(),
            sa.ForeignKey("context_packages.context_package_id"),
            nullable=False,
        ),
        sa.Column("source_versions", postgresql.JSONB(), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"], ["chapters.id", "chapters.project_id"]
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
        ),
        sa.CheckConstraint(
            "jsonb_typeof(body) = 'object' AND jsonb_typeof(source_versions) = 'array'",
            name="json_shapes",
        ),
        sa.CheckConstraint("status IN ('READY', 'BLOCKED')", name="exploration_status"),
        sa.CheckConstraint(EXPLORATION_SHAPE, name="exploration_shape"),
    )
    op.create_index(
        "ix_creative_explorations_workflow_id", "creative_explorations", ["workflow_id"]
    )
    op.add_column(
        "plan_generations", sa.Column("creative_exploration_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "plan_generations", sa.Column("selected_candidate_id", sa.String(40), nullable=True)
    )
    op.create_foreign_key(
        "fk_plan_generations_exploration",
        "plan_generations",
        "creative_explorations",
        ["creative_exploration_id"],
        ["id"],
    )
    op.create_check_constraint(
        "exploration_binding_pair",
        "plan_generations",
        "(creative_exploration_id IS NULL) = (selected_candidate_id IS NULL)",
    )
    op.execute(GUARD)
    op.execute(
        "CREATE TRIGGER exploration_relations BEFORE INSERT ON creative_explorations "
        "FOR EACH ROW EXECUTE FUNCTION novel_exploration_relations()"
    )
    op.execute(
        "CREATE TRIGGER exploration_plan_binding BEFORE INSERT ON plan_generations "
        "FOR EACH ROW EXECUTE FUNCTION novel_exploration_relations()"
    )
    op.execute(
        "CREATE TRIGGER exploration_immutable BEFORE UPDATE OR DELETE ON creative_explorations "
        "FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable()"
    )
    compatibility_guards(exploration=True)


def downgrade():
    compatibility_guards(exploration=False)
    op.execute("DROP TRIGGER exploration_plan_binding ON plan_generations")
    op.drop_constraint(
        op.f("ck_plan_generations_exploration_binding_pair"), "plan_generations", type_="check"
    )
    op.drop_constraint(
        "fk_plan_generations_exploration",
        "plan_generations",
        type_="foreignkey",
    )
    op.drop_column("plan_generations", "selected_candidate_id")
    op.drop_column("plan_generations", "creative_exploration_id")
    op.drop_table("creative_explorations")
    op.execute("DROP FUNCTION novel_exploration_relations()")


EXPLORATION_SHAPE = (
    "body->>'kind' IS NOT DISTINCT FROM 'creative_exploration' "
    "AND body->>'brief_id' IS NOT DISTINCT FROM brief_id::text "
    "AND COALESCE(jsonb_typeof(body->'candidates') = 'array', false) "
    "AND jsonb_array_length(body->'candidates') BETWEEN 1 AND 4 "
    "AND ((status = 'READY' AND body->>'selected_candidate_id' IS NOT NULL "
    "AND body->>'blocked_reason' IS NULL) OR (status = 'BLOCKED' "
    "AND body->>'selected_candidate_id' IS NULL AND body->>'blocked_reason' IS NOT NULL))"
)

GUARD = r"""
CREATE FUNCTION novel_exploration_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE t agent_tasks; e creative_explorations;
BEGIN
    IF TG_TABLE_NAME = 'plan_generations' THEN
        IF NEW.creative_exploration_id IS NULL THEN RETURN NEW; END IF;
        SELECT * INTO e FROM creative_explorations WHERE id=NEW.creative_exploration_id;
        IF e.id IS NULL OR e.status <> 'READY'
            OR (e.project_id,e.chapter_id,e.workflow_id,e.brief_id) IS DISTINCT FROM
               (NEW.project_id,NEW.chapter_id,NEW.workflow_id,NEW.brief_id)
            OR e.body->>'selected_candidate_id' IS DISTINCT FROM NEW.selected_candidate_id
        THEN RAISE EXCEPTION 'Plan selected concept binding mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    SELECT tasks.* INTO t FROM agent_tasks tasks
    JOIN agent_runs runs ON runs.task_id=tasks.task_id WHERE runs.run_id=NEW.agent_run_id;
    IF t.task_id IS NULL OR t.task_type <> 'EXPLORE_CHAPTER_CONCEPTS'
        OR t.agent_id <> 'A03_PLANNING' OR t.workflow_state <> 'C04_CHAPTER_PLANNING'
        OR (t.project_id,t.target_ref,t.workflow_instance_id) IS DISTINCT FROM
           (NEW.project_id,NEW.chapter_id,NEW.workflow_id)
        OR NOT EXISTS (SELECT 1 FROM workflow_instances w WHERE w.id=NEW.workflow_id
            AND w.current_state='C04_CHAPTER_PLANNING' AND w.status='WAITING_AGENT'
            AND w.state_version=t.workflow_state_version AND NOT w.simulation
            AND w.workflow_definition_id='chapter-planning' AND w.workflow_definition_version=4)
        OR NOT EXISTS (SELECT 1 FROM agent_runs runs WHERE runs.run_id=NEW.agent_run_id
            AND runs.task_id=t.task_id AND runs.status='RUNNING')
        OR NOT EXISTS (SELECT 1 FROM prompt_lineages lineage
            WHERE lineage.lineage_id=NEW.prompt_lineage_id
            AND lineage.agent_run_id=NEW.agent_run_id AND lineage.task_id=t.task_id
            AND lineage.output_schema_id || '.v' || lineage.output_schema_version
                =t.expected_output_schema)
        OR NOT EXISTS (SELECT 1 FROM context_packages package
            WHERE package.context_package_id=NEW.context_package_id
            AND package.agent_run_id=NEW.agent_run_id AND package.task_id=t.task_id
            AND package.profile_id='CP-004E' AND package.build_status='READY')
        OR NOT EXISTS (SELECT 1 FROM creative_briefs brief WHERE brief.id=NEW.brief_id
            AND (brief.project_id,brief.chapter_id,brief.workflow_id) =
                (NEW.project_id,NEW.chapter_id,NEW.workflow_id) AND brief.status='READY')
    THEN RAISE EXCEPTION 'Exploration execution lineage mismatch' USING ERRCODE='23514'; END IF;
    IF NEW.status='READY' AND NOT EXISTS (
        SELECT 1 FROM jsonb_array_elements(NEW.body->'candidates') candidate
        WHERE candidate->>'id'=NEW.body->>'selected_candidate_id'
            AND candidate->>'major_change_risk' IN ('LOW','MEDIUM')
            AND candidate->>'authority_fit'='WITHIN_BOUNDS'
    ) THEN RAISE EXCEPTION 'Exploration selected candidate exceeds authority' USING
        ERRCODE='23514'; END IF;
    RETURN NEW;
END $$;
"""
