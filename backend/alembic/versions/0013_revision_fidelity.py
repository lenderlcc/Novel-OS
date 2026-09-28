"""Stage immutable A06 candidates before independent A05 fidelity acceptance."""

import runpy
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_revision_fidelity"
down_revision = "0012_targeted_revision"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revision_candidates",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "request_id",
            sa.UUID(),
            sa.ForeignKey("revision_requests.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "task_id", sa.UUID(), sa.ForeignKey("agent_tasks.task_id"), nullable=False, unique=True
        ),
        sa.Column(
            "run_id", sa.UUID(), sa.ForeignKey("agent_runs.run_id"), nullable=False, unique=True
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
        sa.Column(
            "revision_plan_id",
            sa.UUID(),
            sa.ForeignKey("revision_plans.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(GUARD)
    op.execute(
        "CREATE TRIGGER revision_relations BEFORE INSERT ON revision_candidates FOR EACH ROW "
        "EXECUTE FUNCTION novel_revision_relations()"
    )
    op.execute(
        "CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON revision_candidates "
        "FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable()"
    )


def downgrade():
    # Restore the exact preceding version, not a second independently maintained copy.
    previous = runpy.run_path(str(Path(__file__).with_name("0012_targeted_revision.py")))
    guard = (
        previous["GUARDS"]
        .split("CREATE FUNCTION novel_revision_relations()", 1)[1]
        .split("CREATE TRIGGER revision_relations", 1)[0]
    )
    op.execute("CREATE OR REPLACE FUNCTION novel_revision_relations()" + guard)
    op.drop_table("revision_candidates")


GUARD = r"""
CREATE OR REPLACE FUNCTION novel_revision_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r revision_requests; t agent_tasks; expected_task text; expected_agent text;
BEGIN
    IF TG_TABLE_NAME='revision_requests' THEN
        IF NOT EXISTS (
            SELECT 1 FROM chapter_quality_reviews q
            JOIN quality_review_bindings b ON b.id=q.binding_id
            JOIN quality_review_passes p ON p.id=q.narrative_pass_id
            WHERE q.id=NEW.source_review_id AND b.id=NEW.source_binding_id
            AND b.profile_record_id IS NOT NULL
            AND (q.project_id,q.chapter_id,q.chapter_version_id,b.workflow_id)
                =(NEW.project_id,NEW.chapter_id,NEW.source_chapter_version_id,NEW.workflow_id)
            AND p.context_package_id=NEW.source_context_package_id
        ) THEN RAISE EXCEPTION 'Revision source mismatch' USING ERRCODE='23514'; END IF;
    ELSE
        SELECT * INTO r FROM revision_requests WHERE id=NEW.request_id;
        IF r.contract->>'fidelity_version' IS DISTINCT FROM '1' THEN
            RAISE EXCEPTION 'Historical Revision requires a new fidelity request' USING
        ERRCODE='23514';
        END IF;
        SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
        expected_task := CASE WHEN TG_TABLE_NAME='revision_plans' THEN 'PLAN_CHAPTER_REVISION'
        WHEN TG_TABLE_NAME='revision_results' AND r.contract->>'fidelity_version'='1' THEN
        'VALIDATE_REVISION_FIDELITY'
        ELSE 'REVISE_CHAPTER' END;
        expected_agent := CASE WHEN expected_task='VALIDATE_REVISION_FIDELITY' THEN 'A05_REVIEW'
        ELSE 'A06_REVISION' END;
        IF r.id IS NULL OR t.task_id IS NULL OR t.agent_id <> expected_agent
            OR t.task_type <> expected_task OR t.workflow_state <> 'C10_REVISION'
            OR (t.project_id,t.target_ref,t.workflow_instance_id) IS DISTINCT FROM
        (r.project_id,r.chapter_id,r.workflow_id)
            OR NOT EXISTS (SELECT 1 FROM workflow_instances w WHERE w.id=r.workflow_id
                AND w.revision_request_id=r.id AND w.current_state='C10_REVISION'
                AND w.state_version=t.workflow_state_version AND w.status='WAITING_AGENT')
            OR NOT EXISTS (SELECT 1 FROM agent_runs WHERE run_id=NEW.run_id AND
        task_id=t.task_id AND status='RUNNING')
            OR NOT EXISTS (SELECT 1 FROM prompt_lineages WHERE lineage_id=NEW.prompt_lineage_id
        AND agent_run_id=NEW.run_id AND task_id=t.task_id)
            OR NOT EXISTS (SELECT 1 FROM context_packages WHERE
        context_package_id=NEW.context_package_id AND agent_run_id=NEW.run_id AND
        task_id=t.task_id AND profile_id='CP-007' AND build_status='READY')
            OR NEW.body->>'source_chapter_version_id' IS DISTINCT FROM
        r.source_chapter_version_id::text
            OR NEW.body->>'source_review_id' IS DISTINCT FROM r.source_review_id::text
        THEN RAISE EXCEPTION 'Revision execution lineage mismatch' USING ERRCODE='23514'; END
        IF;
        IF TG_TABLE_NAME='revision_candidates' THEN
            IF NOT EXISTS (SELECT 1 FROM revision_plans p WHERE p.id=NEW.revision_plan_id AND
        p.request_id=r.id)
                OR NEW.body->>'revision_plan_id' IS DISTINCT FROM NEW.revision_plan_id::text
                OR (NEW.body->>'content' IS NOT NULL AND
        encode(sha256(convert_to(NEW.body->>'content','UTF8')), 'hex') IS DISTINCT FROM
        NEW.body->>'content_hash')
            THEN RAISE EXCEPTION 'Revision candidate mismatch' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_TABLE_NAME='revision_results' THEN
            IF NOT EXISTS (
                SELECT 1 FROM revision_candidates c WHERE c.id::text=NEW.body->>'candidate_id'
                AND c.request_id=r.id AND c.revision_plan_id=NEW.revision_plan_id
                AND c.body->>'content_hash'=NEW.body->>'content_hash'
                AND NEW.body->'fidelity'->>'candidate_id'=c.id::text
                AND NEW.body->'fidelity'->>'candidate_content_hash'=c.body->>'content_hash'
                AND NEW.body->'fidelity'->>'source_chapter_version_id'
                    =r.source_chapter_version_id::text
                AND NEW.body->'fidelity'->>'revision_plan_id'=NEW.revision_plan_id::text
                AND NEW.body->'fidelity'->>'source_review_id'=r.source_review_id::text
            ) OR (NEW.chapter_version_id IS NOT NULL AND (
                NEW.body->'fidelity'->>'verdict' IS DISTINCT FROM 'PASS'
                OR NEW.body->>'accepted' IS DISTINCT FROM 'true'
                OR NEW.body->'fidelity'->'violations' IS DISTINCT FROM '[]'::jsonb
                OR EXISTS (SELECT 1 FROM jsonb_array_elements(NEW.body->'fidelity'->'checks') c
        WHERE c->>'preserved' IS DISTINCT FROM 'true')
            )) THEN RAISE EXCEPTION 'Revision fidelity acceptance mismatch' USING
        ERRCODE='23514'; END IF;

            IF NOT EXISTS (SELECT 1 FROM revision_plans WHERE id=NEW.revision_plan_id AND
        request_id=r.id)
                OR NEW.body->>'revision_plan_id' IS DISTINCT FROM NEW.revision_plan_id::text
                OR (NEW.chapter_version_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM chapter_versions v JOIN chapters c ON c.id=v.chapter_id
                    JOIN chapter_versions source_draft ON
        source_draft.id=r.source_chapter_version_id
                    WHERE v.id=NEW.chapter_version_id AND v.chapter_id=r.chapter_id AND
        v.project_id=r.project_id
                    AND v.supersedes_id=source_draft.id AND v.parent_version_id=source_draft.id
                    AND v.version=source_draft.version+1
                    AND v.status='DRAFT' AND v.approved_at IS NULL AND NOT v.locked
                    AND v.authority_level='A7_AI_INFERENCE' AND v.source='AGENT'
                    AND c.current_version=v.version AND length(btrim(v.content))>0
                    AND encode(sha256(convert_to(v.content,'UTF8')), 'hex')
                        =NEW.body->>'content_hash'
                ))
            THEN RAISE EXCEPTION 'Revision successor mismatch' USING ERRCODE='23514'; END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
"""
