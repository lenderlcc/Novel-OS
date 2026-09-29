"""Immutable human feedback and A02 interpretation, reusing Revision persistence."""

import runpy
from pathlib import Path

from alembic import op

revision = "0014_human_feedback"
down_revision = "0013_revision_fidelity"
branch_labels = None
depends_on = None


def previous(name):
    return runpy.run_path(str(Path(__file__).with_name(name)))


def upgrade():
    op.execute(TABLES)
    op.execute(
        "ALTER TABLE workflow_instances ADD COLUMN human_feedback_id UUID "
        "CONSTRAINT fk_workflow_instances_human_feedback_id_human_feedback "
        "REFERENCES human_feedback(id)"
    )
    op.execute(
        "ALTER TABLE revision_requests ALTER COLUMN source_review_id DROP NOT "
        "NULL, ALTER COLUMN source_binding_id DROP NOT NULL, ADD COLUMN "
        "source_feedback_id UUID CONSTRAINT "
        "fk_revision_requests_source_feedback_id_human_feedback REFERENCES "
        "human_feedback(id), ADD CONSTRAINT "
        "uq_revision_requests_source_feedback_id UNIQUE(source_feedback_id)"
    )
    op.execute(
        previous("0012_targeted_revision.py")["WORKFLOW_GUARD"].format(
            revision_field=",'revision_request_id','human_feedback_id'"
        )
    )
    op.execute(FEEDBACK_GUARDS)
    op.execute(REVISION_GUARD)
    for table in ("human_feedback", "human_feedback_interpretations"):
        op.execute(
            f"CREATE TRIGGER feedback_relations BEFORE INSERT ON {table} FOR "
            f"EACH ROW EXECUTE FUNCTION novel_feedback_relations()"
        )
        op.execute(
            f"CREATE TRIGGER feedback_immutable BEFORE UPDATE OR DELETE ON "
            f"{table} FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable()"
        )


def downgrade():
    # Refuse data loss: rollback is safe before human feedback has been recorded.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM human_feedback) THEN RAISE "
        "EXCEPTION 'Export human feedback before downgrade; immutable history "
        "cannot be discarded'; END IF; END $$"
    )
    op.execute(previous("0013_revision_fidelity.py")["GUARD"])
    op.execute(
        previous("0012_targeted_revision.py")["WORKFLOW_GUARD"].format(
            revision_field=",'revision_request_id'"
        )
    )
    op.execute("DROP TRIGGER feedback_workflow_binding ON workflow_instances")
    op.execute("DROP FUNCTION novel_feedback_workflow_binding()")
    op.execute("ALTER TABLE workflow_instances DROP COLUMN human_feedback_id")
    op.execute(
        "ALTER TABLE revision_requests DROP COLUMN source_feedback_id, ALTER "
        "COLUMN source_review_id SET NOT NULL, ALTER COLUMN source_binding_id "
        "SET NOT NULL"
    )
    op.drop_table("human_feedback_interpretations")
    op.drop_table("human_feedback")
    op.execute("DROP FUNCTION novel_feedback_relations()")


TABLES = r"""

CREATE TABLE human_feedback (
	id UUID NOT NULL,
	project_id UUID NOT NULL,
	chapter_id UUID NOT NULL,
	workflow_id UUID NOT NULL,
	source_chapter_version_id UUID NOT NULL,
	source_state_version INTEGER NOT NULL,
	source_draft_version INTEGER NOT NULL,
	source_review_id UUID,
	raw_feedback TEXT NOT NULL,
	return_state TEXT NOT NULL,
	profile_json TEXT NOT NULL,
	authority_snapshot JSONB NOT NULL,
	source TEXT NOT NULL,
	status TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_human_feedback PRIMARY KEY (id),
        CONSTRAINT fk_human_feedback_chapter_id_chapters FOREIGN KEY(chapter_id, project_id)
        REFERENCES chapters (id, project_id),
        CONSTRAINT fk_human_feedback_workflow_id_workflow_instances FOREIGN KEY(workflow_id,
        project_id) REFERENCES workflow_instances (id, project_id),
        CONSTRAINT ck_human_feedback_user_feedback_source CHECK (source = 'USER' AND status =
        'RECORDED'),
	CONSTRAINT ck_human_feedback_feedback_draft_version CHECK (source_draft_version > 0),
        CONSTRAINT ck_human_feedback_feedback_nonempty CHECK (length(btrim(raw_feedback)) > 0
        AND length(raw_feedback) <= 12000),
        CONSTRAINT fk_human_feedback_source_chapter_version_id_chapter_versions FOREIGN
        KEY(source_chapter_version_id) REFERENCES chapter_versions (id),
        CONSTRAINT fk_human_feedback_source_review_id_chapter_quality_reviews FOREIGN
        KEY(source_review_id) REFERENCES chapter_quality_reviews (id)
)

;

CREATE TABLE human_feedback_interpretations (
	id UUID NOT NULL,
	feedback_id UUID NOT NULL,
	task_id UUID NOT NULL,
	run_id UUID NOT NULL,
	prompt_lineage_id UUID NOT NULL,
	context_package_id UUID NOT NULL,
	body JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_human_feedback_interpretations PRIMARY KEY (id),
	CONSTRAINT uq_human_feedback_interpretations_feedback_id UNIQUE (feedback_id),
        CONSTRAINT fk_human_feedback_interpretations_feedback_id_human_feedback FOREIGN
        KEY(feedback_id) REFERENCES human_feedback (id),
	CONSTRAINT uq_human_feedback_interpretations_task_id UNIQUE (task_id),
        CONSTRAINT fk_human_feedback_interpretations_task_id_agent_tasks FOREIGN KEY(task_id)
        REFERENCES agent_tasks (task_id),
	CONSTRAINT uq_human_feedback_interpretations_run_id UNIQUE (run_id),
        CONSTRAINT fk_human_feedback_interpretations_run_id_agent_runs FOREIGN KEY(run_id)
        REFERENCES agent_runs (run_id),
        CONSTRAINT fk_human_feedback_interpretations_prompt_lineage_id_pro_41ba FOREIGN
        KEY(prompt_lineage_id) REFERENCES prompt_lineages (lineage_id),
        CONSTRAINT fk_human_feedback_interpretations_context_package_id_co_d019 FOREIGN
        KEY(context_package_id) REFERENCES context_packages (context_package_id)
)

;
"""

FEEDBACK_GUARDS = r"""

CREATE FUNCTION novel_feedback_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE f human_feedback; t agent_tasks;
BEGIN
    IF TG_TABLE_NAME='human_feedback' THEN
        IF NOT EXISTS (
            SELECT 1 FROM workflow_instances w JOIN chapters c ON c.id=w.chapter_id
            JOIN chapter_versions v ON v.chapter_id=c.id AND v.version=c.current_version
            WHERE w.id=NEW.workflow_id AND
        (w.project_id,w.chapter_id)=(NEW.project_id,NEW.chapter_id)
            AND v.id=NEW.source_chapter_version_id AND v.version=NEW.source_draft_version
            AND w.state_version=NEW.source_state_version
            AND w.current_state=NEW.return_state AND w.current_state IN
        ('C10_REVISION','C11_INTERNAL_PASS')
            AND w.status='WAITING_HUMAN' AND w.revision_request_id IS NULL AND
        w.human_feedback_id IS NULL
        ) OR (NEW.source_review_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM chapter_quality_reviews q WHERE q.id=NEW.source_review_id
            AND
        (q.project_id,q.chapter_id,q.chapter_version_id)=(NEW.project_id,NEW.chapter_id,NEW.source_chapter_version_id)
        )) THEN RAISE EXCEPTION 'Feedback source mismatch' USING ERRCODE='23514'; END IF;
    ELSE
        SELECT * INTO f FROM human_feedback WHERE id=NEW.feedback_id;
        SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
        IF f.id IS NULL OR t.task_id IS NULL OR t.task_type <> 'INTERPRET_CHAPTER_FEEDBACK'
           OR t.agent_id <> 'A02_REQUIREMENT' OR t.workflow_state <> 'C13_USER_FEEDBACK_DIAGNOSIS'
           OR (t.project_id,t.target_ref,t.workflow_instance_id) IS DISTINCT FROM
        (f.project_id,f.chapter_id,f.workflow_id)
           OR NOT EXISTS (SELECT 1 FROM workflow_instances w WHERE w.id=f.workflow_id
               AND w.human_feedback_id=f.id AND w.current_state='C13_USER_FEEDBACK_DIAGNOSIS'
               AND w.state_version=t.workflow_state_version AND w.status='WAITING_AGENT')
           OR NOT EXISTS (SELECT 1 FROM agent_runs r WHERE r.run_id=NEW.run_id AND
        r.task_id=t.task_id AND r.status='RUNNING')
           OR NOT EXISTS (SELECT 1 FROM prompt_lineages p WHERE
        p.lineage_id=NEW.prompt_lineage_id AND p.agent_run_id=NEW.run_id AND
        p.task_id=t.task_id)
           OR NOT EXISTS (SELECT 1 FROM context_packages c WHERE
        c.context_package_id=NEW.context_package_id AND c.agent_run_id=NEW.run_id AND
        c.task_id=t.task_id AND c.profile_id='CP-008' AND c.build_status='READY')
           OR NEW.body->>'feedback_id' IS DISTINCT FROM f.id::text
           OR NEW.body->>'source_chapter_version_id' IS DISTINCT FROM
        f.source_chapter_version_id::text
        THEN RAISE EXCEPTION 'Feedback interpretation lineage mismatch' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION novel_feedback_workflow_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.human_feedback_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM human_feedback f WHERE f.id=NEW.human_feedback_id
        AND (f.workflow_id,f.project_id,f.chapter_id)=(NEW.id,NEW.project_id,NEW.chapter_id)
    ) THEN RAISE EXCEPTION 'Feedback workflow scope mismatch' USING ERRCODE='23514'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER feedback_workflow_binding BEFORE INSERT OR UPDATE ON workflow_instances
FOR EACH ROW EXECUTE FUNCTION novel_feedback_workflow_binding();

"""

REVISION_GUARD = r"""

CREATE OR REPLACE FUNCTION novel_revision_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r revision_requests; t agent_tasks; expected_task text; expected_agent text;
BEGIN
    IF TG_TABLE_NAME='revision_requests' THEN
        IF NEW.source_feedback_id IS NOT NULL THEN
            IF NEW.source_binding_id IS NOT NULL OR NOT EXISTS (
                SELECT 1 FROM human_feedback f
                JOIN human_feedback_interpretations i ON i.feedback_id=f.id
                WHERE f.id=NEW.source_feedback_id
                AND (f.project_id,f.chapter_id,f.workflow_id,f.source_chapter_version_id)
                    =(NEW.project_id,NEW.chapter_id,NEW.workflow_id,NEW.source_chapter_version_id)
                AND i.context_package_id=NEW.source_context_package_id
                AND i.body->>'action'='REVISION'
                AND NEW.contract->>'source_feedback_id'=f.id::text
                AND NEW.contract->'interpretation'=i.body
                AND ((NEW.contract->>'revision_source'='HUMAN_FEEDBACK' AND NEW.source_review_id
        IS NULL
                      AND i.body->'supporting_review_issue_ids'='[]'::jsonb)
                  OR (NEW.contract->>'revision_source'='BOTH' AND
        NEW.source_review_id=f.source_review_id
                      AND jsonb_array_length(i.body->'supporting_review_issue_ids')>0))
            ) THEN RAISE EXCEPTION 'Human revision source mismatch' USING ERRCODE='23514'; END IF;
        ELSE
            IF NEW.contract->>'source_feedback_id' IS NOT NULL OR
               coalesce(NEW.contract->>'revision_source','AI_REVIEW') <> 'AI_REVIEW' THEN
                RAISE EXCEPTION 'Revision source type mismatch' USING ERRCODE='23514';
            END IF;
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
        END IF;
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
            OR NEW.body->>'source_feedback_id' IS DISTINCT FROM r.source_feedback_id::text
            OR coalesce(NEW.body->>'revision_source','AI_REVIEW') IS DISTINCT FROM
        coalesce(r.contract->>'revision_source','AI_REVIEW')
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
                AND (NEW.body->'fidelity'->>'source_review_id') IS NOT DISTINCT FROM
        r.source_review_id::text
                AND (NEW.body->'fidelity'->>'source_feedback_id') IS NOT DISTINCT FROM
        r.source_feedback_id::text
                AND
        coalesce(NEW.body->'fidelity'->>'revision_source','AI_REVIEW')=coalesce(r.contract->>'revision_source','AI_REVIEW')
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
