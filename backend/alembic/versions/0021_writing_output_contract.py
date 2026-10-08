"""Align versioned Writer output with the existing exact-lineage persistence guard."""

import runpy
from pathlib import Path

from alembic import op

revision = "0021_writing_output_contract"
down_revision = "0020_character_report_lineage"
branch_labels = None
depends_on = None


def writing_guard(*, current_contract):
    previous = runpy.run_path(str(Path(__file__).with_name("0011_quality_review.py")))
    guard = previous["WRITING_GUARD"].replace(
        "w.workflow_definition_version=2", "w.workflow_definition_version IN (2,3,4)"
    )
    if current_contract:
        guard = guard.replace(
            "AND output_schema_id='chapter-writing-result' AND output_schema_version=1",
            "AND output_schema_id='chapter-writing-result' AND output_schema_version IN (1,2)"
            "\n                    AND output_schema_id || '.v' || output_schema_version "
            "= t.expected_output_schema",
        )
    return guard


def upgrade():
    op.execute(writing_guard(current_contract=True))


def downgrade():
    op.execute(writing_guard(current_contract=False))
