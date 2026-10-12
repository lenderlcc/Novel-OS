"""Allow exact-Draft human feedback before an idle AI Review executes."""

import runpy
from pathlib import Path

from alembic import op

revision = "0022_feedback_before_review"
down_revision = "0021_writing_output_contract"
branch_labels = None
depends_on = None

PREVIOUS_STATE_GUARD = """AND w.current_state=NEW.return_state AND w.current_state IN
        ('C10_REVISION','C11_INTERNAL_PASS')
            AND w.status='WAITING_HUMAN' AND w.revision_request_id IS NULL AND
        w.human_feedback_id IS NULL"""

CURRENT_STATE_GUARD = """AND w.workflow_definition_id='chapter-planning'
            AND w.workflow_definition_version IN (3,4) AND NOT w.simulation
            AND w.human_feedback_id IS NULL AND w.memory_request_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM agent_tasks inflight
                WHERE inflight.workflow_instance_id=w.id
                  AND inflight.status IN ('CLAIMED','RUNNING'))
            AND (
                (w.current_state=NEW.return_state AND w.current_state IN
                    ('C10_REVISION','C11_INTERNAL_PASS') AND w.status='WAITING_HUMAN'
                    AND w.revision_request_id IS NULL)
                OR (NEW.return_state='C10_REVISION' AND (
                    (w.current_state='C09_INTERNAL_REVIEW' AND w.status='WAITING_AGENT')
                    OR (w.status='PAUSED' AND w.resume_state='C09_INTERNAL_REVIEW'))
                    AND (w.revision_request_id IS NULL OR EXISTS (
                        SELECT 1 FROM revision_requests r
                        JOIN revision_results result ON result.request_id=r.id
                        WHERE r.id=w.revision_request_id
                          AND (r.project_id,r.chapter_id,r.workflow_id)
                            =(w.project_id,w.chapter_id,w.id)
                          AND result.chapter_version_id=v.id)))
            )"""


def feedback_guard(*, before_review):
    previous = runpy.run_path(str(Path(__file__).with_name("0014_human_feedback.py")))
    guard = previous["FEEDBACK_GUARDS"].split(
        "CREATE FUNCTION novel_feedback_workflow_binding()", 1
    )[0]
    guard = guard.replace(
        "CREATE FUNCTION novel_feedback_relations()",
        "CREATE OR REPLACE FUNCTION novel_feedback_relations()",
    )
    if before_review:
        guard = guard.replace(PREVIOUS_STATE_GUARD, CURRENT_STATE_GUARD)
    return guard


def upgrade():
    op.execute(feedback_guard(before_review=True))


def downgrade():
    op.execute(feedback_guard(before_review=False))
