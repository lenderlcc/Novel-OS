"""Preserve workflow recovery intent (NOVEL-003 review fix).

Revision ID: 0004_workflow_recovery
Revises: 0003_workflow_engine
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_workflow_recovery"
down_revision = "0003_workflow_engine"
branch_labels = None
depends_on = None

# Frozen copy of the 0003 trigger, with only its mutable-field allowlist extended.
# Keeping the old body here also makes downgrade independent of runtime code.
GUARD_FUNCTION = """
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
        {recovery_field}])
      IS DISTINCT FROM
       (to_jsonb(NEW) - ARRAY['current_state','status','state_version','retry_count',
        'state_retry_count','revision_count','planning_iteration_count','plan_version',
        'draft_version','resume_state','resume_status','block_reason','blocked_guard','updated_at'
        {recovery_field}])
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


def restore_instance_trigger() -> None:
    op.execute(
        "CREATE TRIGGER guard_workflow_instances BEFORE UPDATE OR DELETE ON workflow_instances "
        "FOR EACH ROW EXECUTE FUNCTION novel_guard_workflow()"
    )


def upgrade() -> None:
    op.add_column(
        "workflow_instances",
        sa.Column("resume_new_stage", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # ALTER TABLE holds its exclusive lock until commit. Only the derived recovery metadata
    # is backfilled; state versions, immutable events and audit history remain untouched.
    op.execute("DROP TRIGGER guard_workflow_instances ON workflow_instances")
    op.execute("""
        UPDATE workflow_instances AS w
        SET resume_new_stage = true
        WHERE w.status = 'BLOCKED' AND (
            w.blocked_guard IS NULL OR EXISTS (
                SELECT 1 FROM workflow_transitions AS t
                JOIN audit_records AS a ON a.id = t.audit_record_id
                WHERE t.workflow_id = w.id AND t.to_state = 'C90_BLOCKED'
                  AND a."after" ->> 'blocked_guard' IS NULL
                  AND t.to_version > (
                      SELECT COALESCE(MAX(previous.to_version), 0)
                      FROM workflow_transitions AS previous
                      WHERE previous.workflow_id = w.id
                        AND previous.to_state <> 'C90_BLOCKED'
                  )
            )
        )
    """)
    op.execute(GUARD_FUNCTION.format(recovery_field=",'resume_new_stage'"))
    restore_instance_trigger()
    op.create_check_constraint(
        "recovery_requires_blocked",
        "workflow_instances",
        "NOT resume_new_stage OR status = 'BLOCKED'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workflow_instances_recovery_requires_blocked", "workflow_instances")
    op.execute("DROP TRIGGER guard_workflow_instances ON workflow_instances")
    # Restore 0003's representation for any still-pending new-stage recovery.
    op.execute("UPDATE workflow_instances SET blocked_guard = NULL WHERE resume_new_stage")
    op.drop_column("workflow_instances", "resume_new_stage")
    op.execute(GUARD_FUNCTION.format(recovery_field=""))
    restore_instance_trigger()
