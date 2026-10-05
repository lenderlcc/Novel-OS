"""Accepted chapter memory proposals, atomic human commits and immutable history."""

import runpy
from pathlib import Path

from alembic import op

revision = "0016_memory_commit"
down_revision = "0015_feedback_clarification"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "memory_requests",
    "memory_commit_proposals",
    "memory_commit_batches",
    "memory_subjects",
    "committed_memory",
)


def workflow_guard(fields):
    previous = runpy.run_path(str(Path(__file__).with_name("0012_targeted_revision.py")))
    op.execute(previous["WORKFLOW_GUARD"].format(revision_field=fields))


def upgrade():
    op.execute(TABLES)
    op.execute(INDEXES)
    op.execute(
        "ALTER TABLE workflow_instances ADD COLUMN memory_request_id UUID CONSTRAINT "
        "fk_workflow_instances_memory_request_id_memory_requests REFERENCES "
        "memory_requests(id)"
    )
    workflow_guard(",'revision_request_id','human_feedback_id','memory_request_id'")
    op.execute("ALTER TABLE chapters DROP CONSTRAINT ck_chapters_status")
    op.execute(
        "ALTER TABLE chapters ADD CONSTRAINT ck_chapters_status CHECK (status IN "
        "('DRAFT','PROPOSED','APPROVED','LOCKED','ACTIVE','STALE','SUPERSEDED','DEPRECATED','CANCELLED','EXECUTED','ARCHIVED','COMPLETED'))"
    )
    op.execute(GUARDS)
    for table in TABLE_NAMES:
        op.execute(
            f"CREATE TRIGGER memory_immutable BEFORE UPDATE OR DELETE ON {table} FOR "
            f"EACH ROW EXECUTE FUNCTION novel_quality_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER memory_relations BEFORE INSERT ON {table} FOR EACH ROW "
            f"EXECUTE FUNCTION novel_memory_relations()"
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER memory_atomic_commit AFTER INSERT ON "
        "memory_commit_batches DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE "
        "FUNCTION novel_memory_atomic_commit()"
    )
    op.execute(
        "CREATE TRIGGER memory_completed_chapter BEFORE UPDATE ON chapters FOR EACH ROW "
        "EXECUTE FUNCTION novel_memory_completed_guard()"
    )
    for table in ("chapter_versions", "chapter_plans"):
        op.execute(
            f"CREATE TRIGGER memory_completed_artifact BEFORE INSERT OR UPDATE ON "
            f"{table} FOR EACH ROW EXECUTE FUNCTION novel_memory_completed_guard()"
        )
    op.execute(
        "CREATE TRIGGER memory_workflow_binding BEFORE INSERT OR UPDATE ON "
        "workflow_instances FOR EACH ROW EXECUTE FUNCTION "
        "novel_memory_workflow_binding()"
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM memory_requests) THEN RAISE EXCEPTION "
        "'Export accepted memory history before downgrade'; END IF; END $$"
    )
    op.execute("DROP TRIGGER memory_workflow_binding ON workflow_instances")
    op.execute("DROP FUNCTION novel_memory_workflow_binding()")
    for table in ("chapter_versions", "chapter_plans"):
        op.execute(f"DROP TRIGGER memory_completed_artifact ON {table}")
    op.execute("DROP TRIGGER memory_completed_chapter ON chapters")
    op.execute("DROP FUNCTION novel_memory_completed_guard()")
    workflow_guard(",'revision_request_id','human_feedback_id'")
    op.execute("ALTER TABLE workflow_instances DROP COLUMN memory_request_id")
    for table in reversed(TABLE_NAMES):
        op.drop_table(table)
    op.execute("DROP FUNCTION novel_memory_relations()")
    op.execute("DROP FUNCTION novel_memory_atomic_commit()")
    op.execute("ALTER TABLE chapters DROP CONSTRAINT ck_chapters_status")
    op.execute(
        "ALTER TABLE chapters ADD CONSTRAINT ck_chapters_status CHECK (status IN "
        "('DRAFT','PROPOSED','APPROVED','LOCKED','ACTIVE','STALE','SUPERSEDED','DEPRECATED','CANCELLED','EXECUTED','ARCHIVED'))"
    )


TABLES = r"""
CREATE TABLE memory_requests (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    chapter_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    chapter_version_id UUID NOT NULL,
    draft_version INTEGER NOT NULL,
    return_state TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    canon_revision INTEGER NOT NULL,
    accepted_by TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_memory_requests PRIMARY KEY (id),
    CONSTRAINT fk_memory_requests_chapter_id_chapters FOREIGN KEY(chapter_id, project_id)
    REFERENCES chapters (id, project_id),
    CONSTRAINT fk_memory_requests_workflow_id_workflow_instances FOREIGN KEY(workflow_id,
    project_id) REFERENCES workflow_instances (id, project_id),
    CONSTRAINT fk_memory_requests_chapter_version_id_chapter_versions FOREIGN
    KEY(chapter_version_id) REFERENCES chapter_versions (id)
);

CREATE TABLE memory_commit_proposals (
    id UUID NOT NULL,
    request_id UUID NOT NULL,
    task_id UUID NOT NULL,
    agent_run_id UUID NOT NULL,
    prompt_lineage_id UUID NOT NULL,
    context_package_id UUID NOT NULL,
    raw_output JSONB NOT NULL,
    candidates JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_memory_commit_proposals PRIMARY KEY (id),
    CONSTRAINT uq_memory_commit_proposals_request_id UNIQUE (request_id),
    CONSTRAINT fk_memory_commit_proposals_request_id_memory_requests FOREIGN KEY(request_id)
    REFERENCES memory_requests (id),
    CONSTRAINT uq_memory_commit_proposals_task_id UNIQUE (task_id),
    CONSTRAINT fk_memory_commit_proposals_task_id_agent_tasks FOREIGN KEY(task_id) REFERENCES
    agent_tasks (task_id),
    CONSTRAINT uq_memory_commit_proposals_agent_run_id UNIQUE (agent_run_id),
    CONSTRAINT fk_memory_commit_proposals_agent_run_id_agent_runs FOREIGN KEY(agent_run_id)
    REFERENCES agent_runs (run_id),
    CONSTRAINT fk_memory_commit_proposals_prompt_lineage_id_prompt_lineages FOREIGN
    KEY(prompt_lineage_id) REFERENCES prompt_lineages (lineage_id),
    CONSTRAINT fk_memory_commit_proposals_context_package_id_context_packages FOREIGN
    KEY(context_package_id) REFERENCES context_packages (context_package_id)
);

CREATE TABLE memory_commit_batches (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    chapter_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    chapter_version_id UUID NOT NULL,
    proposal_id UUID NOT NULL,
    canon_revision INTEGER NOT NULL,
    selected_candidate_ids JSONB NOT NULL,
    skipped_candidate_ids JSONB NOT NULL,
    expected_source_versions JSONB NOT NULL,
    confirmed_by TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    committed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_memory_commit_batches PRIMARY KEY (id),
    CONSTRAINT fk_memory_commit_batches_chapter_id_chapters FOREIGN KEY(chapter_id, project_id)
    REFERENCES chapters (id, project_id),
    CONSTRAINT fk_memory_commit_batches_workflow_id_workflow_instances FOREIGN KEY(workflow_id,
    project_id) REFERENCES workflow_instances (id, project_id),
    CONSTRAINT uq_memory_commit_batches_project_id UNIQUE (project_id, canon_revision),
    CONSTRAINT ck_memory_commit_batches_committed_revision CHECK (canon_revision > 0 AND status
    = 'COMMITTED'),
    CONSTRAINT uq_memory_commit_batches_chapter_id UNIQUE (chapter_id),
    CONSTRAINT uq_memory_commit_batches_chapter_version_id UNIQUE (chapter_version_id),
    CONSTRAINT fk_memory_commit_batches_chapter_version_id_chapter_versions FOREIGN
    KEY(chapter_version_id) REFERENCES chapter_versions (id),
    CONSTRAINT uq_memory_commit_batches_proposal_id UNIQUE (proposal_id),
    CONSTRAINT fk_memory_commit_batches_proposal_id_memory_commit_proposals FOREIGN
    KEY(proposal_id) REFERENCES memory_commit_proposals (id)
);

CREATE TABLE memory_subjects (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    aliases JSONB NOT NULL,
    batch_id UUID NOT NULL,
    CONSTRAINT pk_memory_subjects PRIMARY KEY (id),
    CONSTRAINT uq_memory_subjects_project_id UNIQUE (project_id, kind, normalized_name),
    CONSTRAINT fk_memory_subjects_project_id_projects FOREIGN KEY(project_id) REFERENCES
    projects (id),
    CONSTRAINT fk_memory_subjects_batch_id_memory_commit_batches FOREIGN KEY(batch_id)
    REFERENCES memory_commit_batches (id)
);

CREATE TABLE committed_memory (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    chapter_id UUID NOT NULL,
    chapter_version_id UUID NOT NULL,
    batch_id UUID NOT NULL,
    candidate_id TEXT NOT NULL,
    logical_id UUID NOT NULL,
    version INTEGER NOT NULL,
    supersedes_id UUID,
    subject_id UUID,
    memory_type TEXT NOT NULL,
    slot TEXT NOT NULL,
    value TEXT NOT NULL,
    statement TEXT NOT NULL,
    epistemic_status TEXT,
    authority_level TEXT NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_committed_memory PRIMARY KEY (id),
    CONSTRAINT uq_committed_memory_logical_id UNIQUE (logical_id, version),
    CONSTRAINT uq_committed_memory_batch_id UNIQUE (batch_id, candidate_id),
    CONSTRAINT ck_committed_memory_memory_version CHECK (version > 0),
    CONSTRAINT ck_committed_memory_memory_authority CHECK ((memory_type IN
    ('OPEN_THREAD','DERIVED_CHAPTER_SUMMARY') AND authority_level = 'A6_DERIVED_MEMORY') OR
    (memory_type IN ('CANON_FACT','CHARACTER_STATE','CHARACTER_KNOWLEDGE','RELATIONSHIP_STATE')
    AND authority_level = 'A3_CANON')),
    CONSTRAINT ck_committed_memory_memory_knowledge_owner CHECK ((memory_type =
    'CHARACTER_KNOWLEDGE' AND epistemic_status IN ('KNOWS','BELIEVES','SUSPECTS','DOUBTS') AND
    subject_id IS NOT NULL) OR (memory_type <> 'CHARACTER_KNOWLEDGE' AND epistemic_status IS
    NULL)),
    CONSTRAINT fk_committed_memory_project_id_projects FOREIGN KEY(project_id) REFERENCES
    projects (id),
    CONSTRAINT fk_committed_memory_chapter_id_chapters FOREIGN KEY(chapter_id) REFERENCES
    chapters (id),
    CONSTRAINT fk_committed_memory_chapter_version_id_chapter_versions FOREIGN
    KEY(chapter_version_id) REFERENCES chapter_versions (id),
    CONSTRAINT fk_committed_memory_batch_id_memory_commit_batches FOREIGN KEY(batch_id)
    REFERENCES memory_commit_batches (id),
    CONSTRAINT uq_committed_memory_supersedes_id UNIQUE (supersedes_id),
    CONSTRAINT fk_committed_memory_supersedes_id_committed_memory FOREIGN KEY(supersedes_id)
    REFERENCES committed_memory (id),
    CONSTRAINT fk_committed_memory_subject_id_memory_subjects FOREIGN KEY(subject_id) REFERENCES
    memory_subjects (id)
);
"""

INDEXES = r"""
CREATE INDEX ix_memory_fts ON committed_memory USING gin (to_tsvector('simple', statement));
CREATE INDEX ix_memory_requests_workflow_id ON memory_requests (workflow_id);
CREATE INDEX ix_memory_retrieval ON committed_memory (project_id, subject_id, memory_type,
    authority_level);
"""

GUARDS = r"""
CREATE FUNCTION novel_memory_relations() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r memory_requests; p memory_commit_proposals; b memory_commit_batches;
        old_entry committed_memory; candidate JSONB; t agent_tasks;
BEGIN
  IF TG_TABLE_NAME='memory_requests' THEN
    IF NOT EXISTS (SELECT 1 FROM workflow_instances w JOIN chapters c ON c.id=w.chapter_id
      JOIN chapter_versions v ON v.chapter_id=c.id AND v.version=c.current_version
      WHERE w.id=NEW.workflow_id AND (w.project_id,w.chapter_id)=(NEW.project_id,NEW.chapter_id)
      AND w.current_state=NEW.return_state AND w.status='WAITING_HUMAN'
      AND w.current_state IN ('C10_REVISION','C11_INTERNAL_PASS')
      AND w.revision_request_id IS NULL AND w.human_feedback_id IS NULL AND w.memory_request_id
    IS NULL
      AND c.status<>'COMPLETED' AND c.approved_version=v.version AND v.status IN
    ('APPROVED','LOCKED')
      AND v.id=NEW.chapter_version_id AND v.version=NEW.draft_version)
    THEN RAISE EXCEPTION 'Memory requires accepted exact current chapter' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME='memory_commit_proposals' THEN
    SELECT * INTO r FROM memory_requests WHERE id=NEW.request_id;
    SELECT * INTO t FROM agent_tasks WHERE task_id=NEW.task_id;
    IF r.id IS NULL OR t.task_id IS NULL OR t.task_type<>'EXTRACT_CHAPTER_MEMORY'
      OR t.agent_id<>'A07_MEMORY' OR t.workflow_state<>'C14_MEMORY_PREPARATION'
      OR (t.project_id,t.target_ref,t.workflow_instance_id) IS DISTINCT FROM
    (r.project_id,r.chapter_id,r.workflow_id)
      OR NOT EXISTS (SELECT 1 FROM workflow_instances w WHERE w.id=r.workflow_id
         AND w.memory_request_id=r.id AND w.state_version=t.workflow_state_version AND
    w.status='WAITING_AGENT')
      OR NOT EXISTS (SELECT 1 FROM agent_runs a WHERE a.run_id=NEW.agent_run_id AND
    a.task_id=t.task_id)
      OR NOT EXISTS (SELECT 1 FROM prompt_lineages l WHERE l.lineage_id=NEW.prompt_lineage_id
        AND l.agent_run_id=NEW.agent_run_id AND l.task_id=t.task_id)
      OR NOT EXISTS (SELECT 1 FROM context_packages c WHERE
    c.context_package_id=NEW.context_package_id
        AND c.task_id=t.task_id AND
    c.snapshot->'request'->>'target_version'=r.draft_version::text)
    THEN RAISE EXCEPTION 'Memory extraction lineage mismatch' USING ERRCODE='23514'; END IF;
  ELSIF TG_TABLE_NAME='memory_commit_batches' THEN
    SELECT * INTO p FROM memory_commit_proposals WHERE id=NEW.proposal_id;
    SELECT * INTO r FROM memory_requests WHERE id=p.request_id;
    IF r.id IS NULL OR (r.project_id,r.chapter_id,r.workflow_id,r.chapter_version_id) IS
    DISTINCT FROM
       (NEW.project_id,NEW.chapter_id,NEW.workflow_id,NEW.chapter_version_id)
       OR NEW.canon_revision<>r.canon_revision+1
       OR r.canon_revision<>COALESCE((SELECT max(canon_revision) FROM memory_commit_batches
    WHERE project_id=r.project_id),0)
       OR NOT EXISTS (SELECT 1 FROM workflow_instances w JOIN chapters c ON c.id=w.chapter_id
         WHERE w.id=r.workflow_id AND w.memory_request_id=r.id AND
    w.current_state='C15_MEMORY_COMMIT'
         AND w.status='WAITING_HUMAN' AND c.current_version=r.draft_version AND
    c.approved_version=r.draft_version)
       OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(NEW.selected_candidate_ids) s
         WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(p.candidates) c WHERE
    c->>'id'=s.value
           AND c->>'conflict_status' IN ('NONE','DUPLICATE','STATE_TRANSITION')))
       OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(NEW.skipped_candidate_ids) s
         WHERE NOT NEW.selected_candidate_ids ? s.value)
    THEN RAISE EXCEPTION 'Memory commit source or confirmation mismatch' USING ERRCODE='23514';
    END IF;
  ELSIF TG_TABLE_NAME='memory_subjects' THEN
    IF NOT EXISTS (SELECT 1 FROM memory_commit_batches mb WHERE mb.id=NEW.batch_id AND
    mb.project_id=NEW.project_id)
    THEN RAISE EXCEPTION 'Memory subject scope mismatch' USING ERRCODE='23514'; END IF;
  ELSE
    SELECT * INTO b FROM memory_commit_batches WHERE id=NEW.batch_id;
    SELECT * INTO p FROM memory_commit_proposals WHERE id=b.proposal_id;
    SELECT c INTO candidate FROM jsonb_array_elements(p.candidates) c WHERE
    c->>'id'=NEW.candidate_id;
    IF b.id IS NULL OR candidate IS NULL OR NOT b.selected_candidate_ids ? NEW.candidate_id
      OR b.skipped_candidate_ids ? NEW.candidate_id
      OR (NEW.project_id,NEW.chapter_id,NEW.chapter_version_id) IS DISTINCT FROM
         (b.project_id,b.chapter_id,b.chapter_version_id)
      OR NEW.body IS DISTINCT FROM candidate
      OR
    (NEW.memory_type,NEW.slot,NEW.value,NEW.statement,NEW.authority_level,NEW.epistemic_status)
        IS DISTINCT FROM (candidate->>'candidate_type',candidate->>'slot',candidate->>'value',
          candidate->>'statement',candidate->>'authority_level',candidate->>'epistemic_status')
      OR NEW.subject_id IS DISTINCT FROM (candidate->>'subject_id')::uuid
      OR (NEW.subject_id IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM memory_subjects s WHERE s.id=NEW.subject_id AND
    s.project_id=NEW.project_id))
    THEN RAISE EXCEPTION 'Committed memory must match the confirmed proposal' USING
    ERRCODE='23514'; END IF;
    IF NEW.supersedes_id IS NOT NULL THEN
      SELECT * INTO old_entry FROM committed_memory WHERE id=NEW.supersedes_id;
      IF old_entry.id IS NULL OR (old_entry.project_id,old_entry.logical_id,old_entry.subject_id,
         old_entry.memory_type,old_entry.slot) IS DISTINCT FROM
         (NEW.project_id,NEW.logical_id,NEW.subject_id,NEW.memory_type,NEW.slot)
         OR NEW.version<>old_entry.version+1 OR candidate->>'conflict_status'<>'STATE_TRANSITION'
         OR NEW.memory_type NOT IN ('CHARACTER_STATE','CHARACTER_KNOWLEDGE','RELATIONSHIP_STATE')
      THEN RAISE EXCEPTION 'Memory supersession is invalid' USING ERRCODE='23514'; END IF;
    ELSIF NEW.version<>1 OR EXISTS (SELECT 1 FROM committed_memory e WHERE
    e.project_id=NEW.project_id
      AND e.subject_id IS NOT DISTINCT FROM NEW.subject_id AND e.memory_type=NEW.memory_type AND
    e.slot=NEW.slot)
    THEN RAISE EXCEPTION 'New memory must have a unique current attribute' USING
    ERRCODE='23514'; END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION novel_memory_atomic_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM chapters c JOIN workflow_instances w ON w.chapter_id=c.id
    JOIN workflow_events e ON e.workflow_id=w.id AND e.event_id=NEW.id
    WHERE c.id=NEW.chapter_id AND c.status='COMPLETED' AND c.current_version=c.approved_version
      AND w.id=NEW.workflow_id AND w.current_state='C16_COMPLETED' AND w.status='COMPLETED'
      AND e.actor_type='USER' AND e.actor_id=NEW.confirmed_by AND e.event_type='CONFIRM_MEMORY')
    OR (SELECT count(*) FROM committed_memory WHERE batch_id=NEW.id) <>
      jsonb_array_length(NEW.selected_candidate_ids)-jsonb_array_length(NEW.skipped_candidate_ids)
  THEN RAISE EXCEPTION 'Memory and user-confirmed chapter completion must be atomic' USING
    ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION novel_memory_completed_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='chapters' THEN
    IF OLD.status='COMPLETED' OR (NEW.status='COMPLETED' AND NOT EXISTS (
      SELECT 1 FROM memory_commit_batches b WHERE b.chapter_id=NEW.id))
    THEN RAISE EXCEPTION 'Completed chapter is immutable and requires memory commit' USING
    ERRCODE='23514'; END IF;
  ELSE
    IF EXISTS (SELECT 1 FROM chapters c WHERE c.id=NEW.chapter_id AND c.status='COMPLETED')
    THEN RAISE EXCEPTION 'Completed chapter artifacts cannot change' USING ERRCODE='23514'; END
    IF;
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION novel_memory_workflow_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.memory_request_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM memory_requests r
     WHERE r.id=NEW.memory_request_id AND (r.project_id,r.chapter_id,r.workflow_id)=
       (NEW.project_id,NEW.chapter_id,NEW.id))
  THEN RAISE EXCEPTION 'Workflow memory scope mismatch' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
"""
