"""Immutable exact-version chapter quality review evidence.

Revision ID: 0011_quality_review
Revises: 0010_project_writing_profile
"""

from alembic import op

revision = "0011_quality_review"
down_revision = "0010_project_writing_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        WRITING_GUARD.replace(
            "w.workflow_definition_version=2", "w.workflow_definition_version IN (2,3)"
        )
    )
    op.execute("""
CREATE TABLE quality_review_bindings (
	id UUID NOT NULL,
	project_id UUID NOT NULL,
	chapter_id UUID NOT NULL,
	workflow_id UUID NOT NULL,
	state_version INTEGER NOT NULL,
	chapter_version_id UUID NOT NULL,
	draft_version INTEGER NOT NULL,
	plan_id UUID NOT NULL,
	plan_version INTEGER NOT NULL,
	brief_id UUID NOT NULL,
	profile_record_id UUID,
	profile_version INTEGER,
	profile_hash TEXT,
	profile_json TEXT NOT NULL,
	source_snapshots JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_quality_review_bindings PRIMARY KEY (id),
        CONSTRAINT fk_quality_review_bindings_chapter_id_chapters FOREIGN KEY(chapter_id,
            project_id) REFERENCES chapters (id, project_id),
        CONSTRAINT fk_quality_review_bindings_workflow_id_workflow_instances FOREIGN
            KEY(workflow_id, project_id) REFERENCES workflow_instances (id, project_id),
	CONSTRAINT uq_quality_review_bindings_workflow_id UNIQUE (workflow_id, state_version),
        CONSTRAINT ck_quality_review_bindings_positive_versions CHECK (draft_version > 0 AND
            plan_version > 0 AND state_version > 0),
        CONSTRAINT ck_quality_review_bindings_profile_binding CHECK ((profile_record_id IS
            NULL AND profile_version IS NULL AND profile_hash IS NULL) OR (profile_record_id
            IS NOT NULL AND profile_version > 0 AND profile_hash IS NOT NULL)),
        CONSTRAINT fk_quality_review_bindings_chapter_version_id_chapter_versions FOREIGN
            KEY(chapter_version_id) REFERENCES chapter_versions (id),
        CONSTRAINT fk_quality_review_bindings_plan_id_chapter_plans FOREIGN KEY(plan_id)
            REFERENCES chapter_plans (id),
        CONSTRAINT fk_quality_review_bindings_brief_id_creative_briefs FOREIGN KEY(brief_id)
            REFERENCES creative_briefs (id),
        CONSTRAINT fk_quality_review_bindings_profile_record_id_project_wr_84be FOREIGN
            KEY(profile_record_id) REFERENCES project_writing_profiles (id)
)

;

CREATE TABLE quality_review_passes (
	id UUID NOT NULL,
	binding_id UUID NOT NULL,
	pass_name TEXT NOT NULL,
	task_id UUID NOT NULL,
	run_id UUID NOT NULL,
	prompt_lineage_id UUID NOT NULL,
	context_package_id UUID NOT NULL,
	body JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_quality_review_passes PRIMARY KEY (id),
	CONSTRAINT uq_quality_review_passes_binding_id UNIQUE (binding_id, pass_name),
	CONSTRAINT ck_quality_review_passes_pass_name CHECK (pass_name IN ('COMPLIANCE', 'NARRATIVE')),
        CONSTRAINT fk_quality_review_passes_binding_id_quality_review_bindings FOREIGN
            KEY(binding_id) REFERENCES quality_review_bindings (id),
	CONSTRAINT uq_quality_review_passes_task_id UNIQUE (task_id),
        CONSTRAINT fk_quality_review_passes_task_id_agent_tasks FOREIGN KEY(task_id)
            REFERENCES agent_tasks (task_id),
	CONSTRAINT uq_quality_review_passes_run_id UNIQUE (run_id),
        CONSTRAINT fk_quality_review_passes_run_id_agent_runs FOREIGN KEY(run_id) REFERENCES
            agent_runs (run_id),
        CONSTRAINT fk_quality_review_passes_prompt_lineage_id_prompt_lineages FOREIGN
            KEY(prompt_lineage_id) REFERENCES prompt_lineages (lineage_id),
        CONSTRAINT fk_quality_review_passes_context_package_id_context_packages FOREIGN
            KEY(context_package_id) REFERENCES context_packages (context_package_id)
)

;

CREATE TABLE chapter_quality_reviews (
	id UUID NOT NULL,
	binding_id UUID NOT NULL,
	project_id UUID NOT NULL,
	chapter_id UUID NOT NULL,
	chapter_version_id UUID NOT NULL,
	version INTEGER NOT NULL,
	compliance_pass_id UUID NOT NULL,
	narrative_pass_id UUID NOT NULL,
	body JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_chapter_quality_reviews PRIMARY KEY (id),
	CONSTRAINT uq_chapter_quality_reviews_chapter_id UNIQUE (chapter_id, version),
	CONSTRAINT ck_chapter_quality_reviews_positive_version CHECK (version > 0),
	CONSTRAINT uq_chapter_quality_reviews_binding_id UNIQUE (binding_id),
        CONSTRAINT fk_chapter_quality_reviews_binding_id_quality_review_bindings FOREIGN
            KEY(binding_id) REFERENCES quality_review_bindings (id),
        CONSTRAINT fk_chapter_quality_reviews_project_id_projects FOREIGN KEY(project_id)
            REFERENCES projects (id),
        CONSTRAINT fk_chapter_quality_reviews_chapter_id_chapters FOREIGN KEY(chapter_id)
            REFERENCES chapters (id),
        CONSTRAINT fk_chapter_quality_reviews_chapter_version_id_chapter_versions FOREIGN
            KEY(chapter_version_id) REFERENCES chapter_versions (id),
	CONSTRAINT uq_chapter_quality_reviews_compliance_pass_id UNIQUE (compliance_pass_id),
        CONSTRAINT fk_chapter_quality_reviews_compliance_pass_id_quality_r_b544 FOREIGN
            KEY(compliance_pass_id) REFERENCES quality_review_passes (id),
	CONSTRAINT uq_chapter_quality_reviews_narrative_pass_id UNIQUE (narrative_pass_id),
        CONSTRAINT fk_chapter_quality_reviews_narrative_pass_id_quality_re_e276 FOREIGN
            KEY(narrative_pass_id) REFERENCES quality_review_passes (id)
)

;
CREATE FUNCTION novel_quality_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Quality review evidence is immutable' USING ERRCODE='23514';
END $$;
        CREATE TRIGGER guard_quality_immutable BEFORE UPDATE OR DELETE ON
            quality_review_bindings FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable();
        CREATE TRIGGER guard_quality_immutable BEFORE UPDATE OR DELETE ON
            quality_review_passes FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable();
        CREATE TRIGGER guard_quality_immutable BEFORE UPDATE OR DELETE ON
            chapter_quality_reviews FOR EACH ROW EXECUTE FUNCTION novel_quality_immutable();
""")

    op.execute(QUALITY_RELATIONS)


def downgrade():
    op.execute(WRITING_GUARD)
    op.execute("""
        DROP TABLE chapter_quality_reviews;
        DROP TABLE quality_review_passes;
        DROP TABLE quality_review_bindings;
        DROP FUNCTION novel_quality_immutable();
        DROP FUNCTION novel_quality_relations();
    """)


# Frozen 0009 function; only the supported definition version changes.
WRITING_GUARD = """
    CREATE OR REPLACE FUNCTION guard_writing_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
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
    """

QUALITY_RELATIONS = """
CREATE FUNCTION novel_quality_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b quality_review_bindings; t agent_tasks;
BEGIN
    IF TG_TABLE_NAME = 'quality_review_bindings' THEN
        IF NOT EXISTS (
            SELECT 1 FROM workflow_instances w
            JOIN chapters c ON c.id=w.chapter_id AND c.project_id=w.project_id
            JOIN chapter_versions v ON v.chapter_id=c.id AND v.project_id=c.project_id
            JOIN chapter_plans p ON p.chapter_id=c.id AND p.project_id=c.project_id
            JOIN creative_briefs brief ON brief.workflow_id=w.id
            JOIN plan_generations g ON g.plan_id=p.id AND g.brief_id=brief.id
            WHERE w.id=NEW.workflow_id AND w.project_id=NEW.project_id
            AND w.chapter_id=NEW.chapter_id AND w.state_version=NEW.state_version
            AND w.workflow_definition_id='chapter-planning'
            AND w.workflow_definition_version=3 AND NOT w.simulation
            AND w.current_state='C09_INTERNAL_REVIEW' AND w.status='WAITING_AGENT'
            AND v.id=NEW.chapter_version_id AND v.version=NEW.draft_version
            AND c.current_version=v.version AND w.draft_version=v.version
            AND p.id=NEW.plan_id AND p.version=NEW.plan_version
            AND c.approved_plan_version=p.version AND w.plan_version=p.version
            AND p.status IN ('APPROVED','LOCKED') AND p.approved_at IS NOT NULL
            AND brief.id=NEW.brief_id AND brief.status='READY'
        ) THEN
            RAISE EXCEPTION 'Quality binding source mismatch' USING ERRCODE='23514';
        END IF;
        IF NEW.profile_record_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM project_writing_profiles WHERE id=NEW.profile_record_id
            AND project_id=NEW.project_id AND version=NEW.profile_version
            AND status='APPROVED' AND authority_level='A5_USER_PREFERENCE'
        ) THEN
            RAISE EXCEPTION 'Quality profile binding mismatch' USING ERRCODE='23514';
        END IF;
    ELSE
        SELECT * INTO b FROM quality_review_bindings WHERE id=NEW.binding_id;
        IF b.id IS NULL THEN
            RAISE EXCEPTION 'Missing quality binding' USING ERRCODE='23514';
        END IF;
        IF TG_TABLE_NAME = 'quality_review_passes' THEN
            SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
            IF t.agent_id <> 'A05_REVIEW' OR t.task_id IS NULL
                OR t.task_type <> 'REVIEW_CHAPTER_' || NEW.pass_name
                OR (t.project_id,t.target_ref,t.workflow_instance_id,t.workflow_state_version)
                    IS DISTINCT FROM (b.project_id,b.chapter_id,b.workflow_id,b.state_version)
                OR t.workflow_state <> 'C09_INTERNAL_REVIEW'
                OR NOT EXISTS (SELECT 1 FROM agent_runs WHERE run_id=NEW.run_id
                    AND task_id=NEW.task_id AND status='RUNNING')
                OR NOT EXISTS (SELECT 1 FROM prompt_lineages WHERE lineage_id=NEW.prompt_lineage_id
                    AND agent_run_id=NEW.run_id AND task_id=NEW.task_id)
                OR NOT EXISTS (SELECT 1 FROM context_packages
                    WHERE context_package_id=NEW.context_package_id
                    AND agent_run_id=NEW.run_id AND task_id=NEW.task_id
                    AND profile_id='CP-006' AND build_status='READY')
                OR NEW.body->>'chapter_id' IS DISTINCT FROM b.chapter_id::text
                OR NEW.body->>'chapter_version_id' IS DISTINCT FROM b.chapter_version_id::text
            THEN
                RAISE EXCEPTION 'Quality pass lineage mismatch' USING ERRCODE='23514';
            END IF;
        ELSE
            IF (NEW.project_id,NEW.chapter_id,NEW.chapter_version_id)
                IS DISTINCT FROM (b.project_id,b.chapter_id,b.chapter_version_id)
                OR NOT EXISTS (SELECT 1 FROM quality_review_passes
                    WHERE id=NEW.compliance_pass_id AND binding_id=b.id
                    AND pass_name='COMPLIANCE')
                OR NOT EXISTS (SELECT 1 FROM quality_review_passes
                    WHERE id=NEW.narrative_pass_id AND binding_id=b.id
                    AND pass_name='NARRATIVE')
                OR NEW.body->>'chapter_id' IS DISTINCT FROM b.chapter_id::text
                OR NEW.body->>'chapter_version_id' IS DISTINCT FROM b.chapter_version_id::text
            THEN
                RAISE EXCEPTION 'Quality aggregate lineage mismatch' USING ERRCODE='23514';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER quality_relations BEFORE INSERT ON quality_review_bindings
    FOR EACH ROW EXECUTE FUNCTION novel_quality_relations();
CREATE TRIGGER quality_relations BEFORE INSERT ON quality_review_passes
    FOR EACH ROW EXECUTE FUNCTION novel_quality_relations();
CREATE TRIGGER quality_relations BEFORE INSERT ON chapter_quality_reviews
    FOR EACH ROW EXECUTE FUNCTION novel_quality_relations();
"""
