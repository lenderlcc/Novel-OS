"""Agent execution persistence; frozen DDL for NOVEL-004.

0004 was already used by the published workflow recovery fix.
"""

from alembic import op

revision = "0005_agent_runtime"
down_revision = "0004_workflow_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE workflow_instances ADD CONSTRAINT uq_workflow_instances_id_project UNIQUE (id,
project_id)
""")
    op.execute("""
CREATE TABLE agent_tasks (
task_id UUID NOT NULL,
project_id UUID NOT NULL,
workflow_instance_id UUID NOT NULL,
workflow_state VARCHAR(27) NOT NULL,
workflow_state_version INTEGER NOT NULL,
agent_id VARCHAR(16) NOT NULL,
task_type VARCHAR(80) NOT NULL,
objective TEXT NOT NULL,
target_ref UUID NOT NULL,
requirements JSONB NOT NULL,
constraints JSONB NOT NULL,
capabilities JSONB NOT NULL,
expected_output_schema VARCHAR(80) NOT NULL,
status VARCHAR(9) NOT NULL,
priority INTEGER NOT NULL,
attempt_count INTEGER NOT NULL,
max_attempts INTEGER NOT NULL,
version INTEGER NOT NULL,
created_at TIMESTAMP WITH TIME ZONE NOT NULL,
available_at TIMESTAMP WITH TIME ZONE NOT NULL,
claimed_at TIMESTAMP WITH TIME ZONE,
started_at TIMESTAMP WITH TIME ZONE,
completed_at TIMESTAMP WITH TIME ZONE,
lease_owner VARCHAR(128),
lease_token UUID,
lease_expires_at TIMESTAMP WITH TIME ZONE,
heartbeat_at TIMESTAMP WITH TIME ZONE,
last_error_code VARCHAR(80),
last_error_message TEXT,
result_ref UUID,
result_metadata JSONB NOT NULL,
CONSTRAINT pk_agent_tasks PRIMARY KEY (task_id),
CONSTRAINT fk_agent_tasks_workflow_instance_id_workflow_instances FOREIGN
KEY(workflow_instance_id, project_id) REFERENCES workflow_instances (id, project_id),
CONSTRAINT fk_agent_tasks_target_ref_chapters FOREIGN KEY(target_ref, project_id) REFERENCES
chapters (id, project_id),
CONSTRAINT uq_agent_tasks_logical_stage UNIQUE (workflow_instance_id, workflow_state_version,
task_type),
CONSTRAINT ck_agent_tasks_positive_versions CHECK (version > 0 AND workflow_state_version >
0),
CONSTRAINT ck_agent_tasks_attempt_budget CHECK (attempt_count >= 0 AND attempt_count <=
max_attempts AND max_attempts BETWEEN 1 AND 10),
CONSTRAINT ck_agent_tasks_priority_range CHECK (priority BETWEEN -100 AND 100),
CONSTRAINT ck_agent_tasks_lease_required CHECK ((status IN ('CLAIMED','RUNNING')) =
(lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND
heartbeat_at IS NOT NULL)),
CONSTRAINT fk_agent_tasks_project_id_projects FOREIGN KEY(project_id) REFERENCES projects
(id),
CONSTRAINT ck_agent_tasks_chapterstate CHECK (workflow_state IN ('C00_CREATED',
'C01_REQUIREMENT_INTAKE', 'C02_CONTEXT_ASSEMBLY', 'C03_REQUIREMENT_READY',
'C04_CHAPTER_PLANNING', 'C05_PLAN_REVIEW', 'C06_PLAN_APPROVAL', 'C07_WRITING',
'C08_DETERMINISTIC_CHECK', 'C09_INTERNAL_REVIEW', 'C10_REVISION', 'C11_INTERNAL_PASS',
'C12_USER_REVIEW', 'C13_USER_FEEDBACK_DIAGNOSIS', 'C14_MEMORY_PREPARATION',
'C15_MEMORY_COMMIT', 'C16_COMPLETED', 'C90_BLOCKED', 'C91_FAILED', 'C92_CANCELLED')),
CONSTRAINT ck_agent_tasks_agentid CHECK (agent_id IN ('A01_ORCHESTRATOR', 'A02_REQUIREMENT',
'A03_PLANNING', 'A04_WRITING', 'A05_REVIEW', 'A06_REVISION', 'A07_MEMORY')),
CONSTRAINT ck_agent_tasks_taskstatus CHECK (status IN ('PENDING', 'CLAIMED', 'RUNNING',
'SUCCEEDED', 'BLOCKED', 'FAILED', 'CANCELLED'))
)
""")
    op.execute("""
CREATE INDEX ix_agent_tasks_claim ON agent_tasks (status, priority, available_at,
lease_expires_at)
""")
    op.execute("""
CREATE INDEX ix_agent_tasks_workflow_instance_id ON agent_tasks (workflow_instance_id)
""")
    op.execute("""
CREATE TABLE agent_runs (
run_id UUID NOT NULL,
task_id UUID NOT NULL,
attempt_number INTEGER NOT NULL,
worker_id VARCHAR(128) NOT NULL,
lease_token UUID NOT NULL,
status VARCHAR(9) NOT NULL,
claimed_at TIMESTAMP WITH TIME ZONE NOT NULL,
started_at TIMESTAMP WITH TIME ZONE,
finished_at TIMESTAMP WITH TIME ZONE,
duration_ms INTEGER,
provider VARCHAR(80) NOT NULL,
model VARCHAR(80) NOT NULL,
input_metadata JSONB NOT NULL,
output_metadata JSONB NOT NULL,
error_code VARCHAR(80),
error_message TEXT,
result_status VARCHAR(11),
disposition VARCHAR(40),
CONSTRAINT pk_agent_runs PRIMARY KEY (run_id),
CONSTRAINT uq_agent_runs_task_id UNIQUE (task_id, attempt_number),
CONSTRAINT uq_agent_runs_run_id UNIQUE (run_id, task_id),
CONSTRAINT uq_agent_runs_lease_token UNIQUE (lease_token),
CONSTRAINT ck_agent_runs_positive_attempt CHECK (attempt_number > 0),
CONSTRAINT ck_agent_runs_nonnegative_duration CHECK (duration_ms IS NULL OR duration_ms >= 0),
CONSTRAINT ck_agent_runs_terminal_timestamp CHECK ((status IN ('CLAIMED','RUNNING')) =
(finished_at IS NULL)),
CONSTRAINT fk_agent_runs_task_id_agent_tasks FOREIGN KEY(task_id) REFERENCES agent_tasks
(task_id),
CONSTRAINT ck_agent_runs_runstatus CHECK (status IN ('CLAIMED', 'RUNNING', 'SUCCEEDED',
'FAILED', 'ABANDONED', 'CANCELLED')),
CONSTRAINT ck_agent_runs_resultstatus CHECK (result_status IN ('SUCCESS', 'PARTIAL',
'BLOCKED', 'NEEDS_HUMAN', 'FAILED'))
)
""")
    op.execute("""
CREATE INDEX ix_agent_runs_task_id ON agent_runs (task_id)
""")
    op.execute("""
ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_result_run FOREIGN KEY(result_ref,
task_id) REFERENCES agent_runs (run_id, task_id) DEFERRABLE INITIALLY DEFERRED
""")

    op.execute("""
CREATE FUNCTION novel_guard_agent_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Execution history cannot be deleted' USING ERRCODE = '23514';
  END IF;
  IF TG_TABLE_NAME = 'agent_tasks' THEN
    IF OLD.status IN ('SUCCEEDED','BLOCKED','FAILED','CANCELLED') OR
       NEW.version != OLD.version + 1 OR
       (to_jsonb(OLD) - ARRAY['status','version','attempt_count','available_at','claimed_at',
        'started_at','completed_at','lease_owner','lease_token','lease_expires_at','heartbeat_at',
        'last_error_code','last_error_message','result_ref','result_metadata']) IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['status','version','attempt_count','available_at','claimed_at',
        'started_at','completed_at','lease_owner','lease_token','lease_expires_at','heartbeat_at',
        'last_error_code','last_error_message','result_ref','result_metadata']) THEN
      RAISE EXCEPTION 'Invalid task update' USING ERRCODE = '23514';
    END IF;
  ELSE
    IF OLD.finished_at IS NOT NULL OR
       (OLD.status = 'RUNNING' AND NEW.status = 'CLAIMED') OR
       (to_jsonb(OLD) - ARRAY['status','started_at','finished_at','duration_ms','output_metadata',
          'error_code','error_message','result_status','disposition']) IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['status','started_at','finished_at','duration_ms','output_metadata',
          'error_code','error_message','result_status','disposition']) THEN
      RAISE EXCEPTION 'Attempt identity and completed history are immutable'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
""")
    for table in ("agent_tasks", "agent_runs"):
        op.execute(
            f"CREATE TRIGGER guard_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION novel_guard_agent_record()"
        )


def downgrade() -> None:
    op.drop_constraint("fk_agent_tasks_result_run", "agent_tasks", type_="foreignkey")
    op.drop_table("agent_runs")
    op.drop_table("agent_tasks")
    op.execute("DROP FUNCTION novel_guard_agent_record()")
    op.drop_constraint("uq_workflow_instances_id_project", "workflow_instances", type_="unique")
