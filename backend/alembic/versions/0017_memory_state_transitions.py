"""Version explicit object states and thread updates without replacing static Canon."""

import runpy
from pathlib import Path

from alembic import op

revision = "0017_memory_state_transitions"
down_revision = "0016_memory_commit"
branch_labels = None
depends_on = None

OLD_TYPES = (
    "OR NEW.memory_type NOT IN ('CHARACTER_STATE','CHARACTER_KNOWLEDGE','RELATIONSHIP_STATE')"
)
TRANSITION_TYPES = """OR NOT COALESCE(CASE
           WHEN NEW.memory_type IN ('CHARACTER_STATE','CHARACTER_KNOWLEDGE','RELATIONSHIP_STATE')
             THEN true
           WHEN NEW.memory_type='OPEN_THREAD' THEN
             candidate->>'state_before' = old_entry.value
             AND candidate->>'state_after' = NEW.value
           WHEN NEW.memory_type='CANON_FACT' THEN
             EXISTS (SELECT 1 FROM memory_subjects s WHERE s.id=NEW.subject_id AND s.kind='OBJECT')
             AND old_entry.body->>'state_after' = old_entry.value
             AND candidate->>'state_before' = old_entry.value
             AND candidate->>'state_after' = NEW.value
           ELSE false
         END, false)"""


def relations_guard():
    # Retain every existing lineage/confirmation check; replace only allowed transitions.
    previous = runpy.run_path(str(Path(__file__).with_name("0016_memory_commit.py")))
    relations = previous["GUARDS"].split("CREATE FUNCTION novel_memory_atomic_commit()", 1)[0]
    return relations.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def upgrade():
    op.execute(relations_guard().replace(OLD_TYPES, TRANSITION_TYPES))


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM committed_memory
                WHERE supersedes_id IS NOT NULL AND memory_type IN ('CANON_FACT','OPEN_THREAD'))
            THEN RAISE EXCEPTION 'Export object/thread transition history before downgrade';
            END IF;
        END $$;
    """)
    op.execute(relations_guard())
