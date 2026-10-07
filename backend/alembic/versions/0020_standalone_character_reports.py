"""Explicit A02 character reports reuse the existing execution evidence chain."""

import sqlalchemy as sa

from alembic import op

revision = "0020_character_report_lineage"
down_revision = "0019_character_behavior_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_memory_subjects_id_project", "memory_subjects", ["id", "project_id"]
    )
    op.add_column("agent_tasks", sa.Column("report_character_id", sa.UUID(), nullable=True))
    for name in ("workflow_instance_id", "workflow_state", "workflow_state_version", "target_ref"):
        op.alter_column("agent_tasks", name, nullable=True)
    op.create_foreign_key(
        "fk_agent_tasks_report_character_id_memory_subjects",
        "agent_tasks",
        "memory_subjects",
        ["report_character_id", "project_id"],
        ["id", "project_id"],
    )
    op.create_check_constraint(
        "execution_scope",
        "agent_tasks",
        "(workflow_instance_id IS NOT NULL AND workflow_state IS NOT NULL "
        "AND workflow_state_version IS NOT NULL AND target_ref IS NOT NULL "
        "AND report_character_id IS NULL AND task_type <> 'INTERPRET_CHARACTER_PROFILE') "
        "OR (workflow_instance_id IS NULL AND workflow_state IS NULL "
        "AND workflow_state_version IS NULL AND target_ref IS NULL "
        "AND report_character_id IS NOT NULL AND task_type = 'INTERPRET_CHARACTER_PROFILE' "
        "AND agent_id = 'A02_REQUIREMENT' AND capabilities = '[\"REPORT_RESULT\"]'::jsonb "
        "AND expected_output_schema = 'character-profile-draft.v1' AND max_attempts = 1)",
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM agent_tasks WHERE report_character_id IS NOT NULL) "
        "THEN RAISE EXCEPTION 'Export standalone character report execution history before "
        "downgrade'; END IF; END $$"
    )
    op.drop_constraint(op.f("ck_agent_tasks_execution_scope"), "agent_tasks", type_="check")
    op.drop_constraint(
        "fk_agent_tasks_report_character_id_memory_subjects", "agent_tasks", type_="foreignkey"
    )
    op.drop_column("agent_tasks", "report_character_id")
    for name in ("workflow_instance_id", "workflow_state", "workflow_state_version", "target_ref"):
        op.alter_column("agent_tasks", name, nullable=False)
    op.drop_constraint("uq_memory_subjects_id_project", "memory_subjects", type_="unique")
