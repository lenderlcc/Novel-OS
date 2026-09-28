"""Exact-source targeted revision requests, plans and immutable successor lineage."""

from alembic import op

revision = "0012_targeted_revision"
down_revision = "0011_quality_review"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(TABLES)
    op.execute(
        "ALTER TABLE workflow_instances ADD COLUMN revision_request_id UUID "
        "CONSTRAINT fk_workflow_instances_revision_request_id_revision_requests "
        "REFERENCES revision_requests(id)"
    )
    op.execute(WORKFLOW_GUARD.format(revision_field=",'revision_request_id'"))
    op.execute(GUARDS)


def downgrade():
    op.execute(WORKFLOW_GUARD.format(revision_field=""))
    op.execute("DROP TRIGGER revision_workflow_binding ON workflow_instances")
    op.execute("ALTER TABLE workflow_instances DROP COLUMN revision_request_id")
    for table in ("revision_results", "revision_plans", "revision_requests"):
        op.execute("DROP TABLE " + table)
    op.execute("DROP FUNCTION novel_revision_relations()")
    op.execute("DROP FUNCTION novel_revision_workflow_binding()")


TABLES = """

CREATE TABLE revision_requests (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    chapter_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    source_chapter_version_id UUID NOT NULL,
    source_review_id UUID NOT NULL,
    source_binding_id UUID NOT NULL,
    source_context_package_id UUID NOT NULL,
    profile_json TEXT NOT NULL,
    contract JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_revision_requests PRIMARY KEY (id),
    CONSTRAINT fk_revision_requests_chapter_id_chapters FOREIGN KEY(chapter_id, project_id)
        REFERENCES chapters (id, project_id),
    CONSTRAINT fk_revision_requests_workflow_id_workflow_instances FOREIGN KEY(workflow_id,
        project_id) REFERENCES workflow_instances (id, project_id),
    CONSTRAINT fk_revision_requests_source_chapter_version_id_chapter_versions FOREIGN
        KEY(source_chapter_version_id) REFERENCES chapter_versions (id),
    CONSTRAINT fk_revision_requests_source_review_id_chapter_quality_reviews FOREIGN
        KEY(source_review_id) REFERENCES chapter_quality_reviews (id),
    CONSTRAINT fk_revision_requests_source_binding_id_quality_review_bindings FOREIGN
        KEY(source_binding_id) REFERENCES quality_review_bindings (id),
    CONSTRAINT fk_revision_requests_source_context_package_id_context_packages FOREIGN
        KEY(source_context_package_id) REFERENCES context_packages (context_package_id)
)

;

CREATE TABLE revision_plans (
    id UUID NOT NULL,
    request_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    prompt_lineage_id UUID NOT NULL,
    context_package_id UUID NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_revision_plans PRIMARY KEY (id),
    CONSTRAINT uq_revision_plans_request_id UNIQUE (request_id),
    CONSTRAINT fk_revision_plans_request_id_revision_requests FOREIGN KEY(request_id) REFERENCES
        revision_requests (id),
    CONSTRAINT uq_revision_plans_task_id UNIQUE (task_id),
    CONSTRAINT fk_revision_plans_task_id_agent_tasks FOREIGN KEY(task_id) REFERENCES agent_tasks
        (task_id),
    CONSTRAINT uq_revision_plans_run_id UNIQUE (run_id),
    CONSTRAINT fk_revision_plans_run_id_agent_runs FOREIGN KEY(run_id) REFERENCES agent_runs
        (run_id),
    CONSTRAINT fk_revision_plans_prompt_lineage_id_prompt_lineages FOREIGN
        KEY(prompt_lineage_id) REFERENCES prompt_lineages (lineage_id),
    CONSTRAINT fk_revision_plans_context_package_id_context_packages FOREIGN
        KEY(context_package_id) REFERENCES context_packages (context_package_id)
)

;

CREATE TABLE revision_results (
    revision_plan_id UUID NOT NULL,
    chapter_version_id UUID,
    id UUID NOT NULL,
    request_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    prompt_lineage_id UUID NOT NULL,
    context_package_id UUID NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_revision_results PRIMARY KEY (id),
    CONSTRAINT uq_revision_results_revision_plan_id UNIQUE (revision_plan_id),
    CONSTRAINT fk_revision_results_revision_plan_id_revision_plans FOREIGN KEY(revision_plan_id)
        REFERENCES revision_plans (id),
    CONSTRAINT uq_revision_results_chapter_version_id UNIQUE (chapter_version_id),
    CONSTRAINT fk_revision_results_chapter_version_id_chapter_versions FOREIGN
        KEY(chapter_version_id) REFERENCES chapter_versions (id),
    CONSTRAINT uq_revision_results_request_id UNIQUE (request_id),
    CONSTRAINT fk_revision_results_request_id_revision_requests FOREIGN KEY(request_id)
        REFERENCES revision_requests (id),
    CONSTRAINT uq_revision_results_task_id UNIQUE (task_id),
    CONSTRAINT fk_revision_results_task_id_agent_tasks FOREIGN KEY(task_id) REFERENCES
        agent_tasks (task_id),
    CONSTRAINT uq_revision_results_run_id UNIQUE (run_id),
    CONSTRAINT fk_revision_results_run_id_agent_runs FOREIGN KEY(run_id) REFERENCES agent_runs
        (run_id),
    CONSTRAINT fk_revision_results_prompt_lineage_id_prompt_lineages FOREIGN
        KEY(prompt_lineage_id) REFERENCES prompt_lineages (lineage_id),
    CONSTRAINT fk_revision_results_context_package_id_context_packages FOREIGN
        KEY(context_package_id) REFERENCES context_packages (context_package_id)
)

;
"""

GUARDS = """
CREATE FUNCTION novel_revision_workflow_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.revision_request_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM revision_requests r WHERE r.id=NEW.revision_request_id
        AND (r.workflow_id,r.project_id,r.chapter_id)=(NEW.id,NEW.project_id,NEW.chapter_id)
    ) THEN RAISE EXCEPTION 'Revision workflow scope mismatch' USING ERRCODE='23514'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER revision_workflow_binding BEFORE INSERT OR UPDATE ON workflow_instances
FOR EACH ROW EXECUTE FUNCTION novel_revision_workflow_binding();

CREATE FUNCTION novel_revision_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r revision_requests; t agent_tasks; expected_task text;
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
        SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
        expected_task := CASE WHEN TG_TABLE_NAME='revision_plans' THEN 'PLAN_CHAPTER_REVISION'
        ELSE 'REVISE_CHAPTER' END;
        IF r.id IS NULL OR t.task_id IS NULL OR t.agent_id <> 'A06_REVISION'
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
        IF TG_TABLE_NAME='revision_results' THEN
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
CREATE TRIGGER revision_relations BEFORE INSERT ON revision_requests FOR EACH ROW EXECUTE
        FUNCTION novel_revision_relations();
CREATE TRIGGER revision_relations BEFORE INSERT ON revision_plans FOR EACH ROW EXECUTE FUNCTION
        novel_revision_relations();
CREATE TRIGGER revision_relations BEFORE INSERT ON revision_results FOR EACH ROW EXECUTE
        FUNCTION novel_revision_relations();
CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON revision_requests FOR EACH ROW
        EXECUTE FUNCTION novel_quality_immutable();
CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON revision_plans FOR EACH ROW EXECUTE
        FUNCTION novel_quality_immutable();
CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON revision_results FOR EACH ROW
        EXECUTE FUNCTION novel_quality_immutable();
"""

WORKFLOW_GUARD = """

CREATE OR REPLACE FUNCTION novel_guard_workflow() RETURNS trigger LANGUAGE plpgsql AS $$
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
'draft_version','resume_state','resume_status','block_reason','blocked_guard','updated_at'
        ,'resume_new_stage'{revision_field}])
      IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['current_state','status','state_version','retry_count',
        'state_retry_count','revision_count','planning_iteration_count','plan_version',
'draft_version','resume_state','resume_status','block_reason','blocked_guard','updated_at'
        ,'resume_new_stage'{revision_field}])
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

"""
