"""Bind a clarification reply to an immutable question on the same Draft."""

from alembic import op

revision = "0015_feedback_clarification"
down_revision = "0014_human_feedback"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE human_feedback ADD COLUMN reply_to_feedback_id UUID "
        "CONSTRAINT fk_human_feedback_reply_to_feedback_id_human_feedback "
        "REFERENCES human_feedback(id)"
    )
    op.execute("""
        CREATE FUNCTION novel_feedback_reply_binding() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.reply_to_feedback_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM human_feedback f
                JOIN human_feedback_interpretations i ON i.feedback_id=f.id
                WHERE f.id=NEW.reply_to_feedback_id
                  AND (f.project_id,f.chapter_id,f.workflow_id,f.source_chapter_version_id)
                    =(NEW.project_id,NEW.chapter_id,NEW.workflow_id,NEW.source_chapter_version_id)
                  AND f.source_state_version < NEW.source_state_version
                  AND i.body->>'action'='USER_DECISION_REQUIRED'
                  AND NOT EXISTS (SELECT 1 FROM human_feedback newer
                    WHERE newer.workflow_id=f.workflow_id
                      AND newer.source_state_version > f.source_state_version)
            ) THEN
                RAISE EXCEPTION 'Feedback reply source mismatch' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER feedback_reply_binding BEFORE INSERT ON human_feedback
        FOR EACH ROW EXECUTE FUNCTION novel_feedback_reply_binding();
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM human_feedback WHERE reply_to_feedback_id IS NOT NULL) THEN
                RAISE EXCEPTION 'Cannot discard immutable feedback clarification history';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER feedback_reply_binding ON human_feedback")
    op.execute("DROP FUNCTION novel_feedback_reply_binding()")
    op.execute("ALTER TABLE human_feedback DROP COLUMN reply_to_feedback_id")
