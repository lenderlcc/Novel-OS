"""Immutable approved character behavior and minimal manual identity provenance."""

import runpy
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019_character_behavior_profile"
down_revision = "0018_creative_exploration"
branch_labels = None
depends_on = None


def memory_guard(*, manual):
    previous = runpy.run_path(str(Path(__file__).with_name("0017_memory_state_transitions.py")))
    guard = previous["relations_guard"]().replace(
        previous["OLD_TYPES"], previous["TRANSITION_TYPES"]
    )
    if manual:
        guard = guard.replace(
            "ELSIF TG_TABLE_NAME='memory_subjects' THEN",
            """ELSIF TG_TABLE_NAME='memory_subjects' THEN
    IF NEW.batch_id IS NULL THEN
      IF NEW.kind<>'CHARACTER' OR length(trim(NEW.created_by))=0
      THEN RAISE EXCEPTION 'Manual identity requires user provenance' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END IF;""",
        )
    return guard


def upgrade():
    op.alter_column("memory_subjects", "batch_id", nullable=True)
    op.add_column("memory_subjects", sa.Column("created_at", sa.DateTime(timezone=True)))
    op.add_column("memory_subjects", sa.Column("created_by", sa.Text()))
    # Preserve provenance while the original append-only trigger rejects normal updates.
    op.execute("ALTER TABLE memory_subjects DISABLE TRIGGER memory_immutable")
    op.execute(
        "UPDATE memory_subjects s SET created_at=b.committed_at, created_by=b.confirmed_by "
        "FROM memory_commit_batches b WHERE s.batch_id=b.id"
    )
    op.execute("ALTER TABLE memory_subjects ENABLE TRIGGER memory_immutable")
    op.alter_column("memory_subjects", "created_at", nullable=False)
    op.alter_column("memory_subjects", "created_by", nullable=False)
    op.execute(memory_guard(manual=True))
    op.create_table(
        "character_behavior_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("character_id", sa.UUID(), sa.ForeignKey("memory_subjects.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "supersedes_id",
            sa.UUID(),
            sa.ForeignKey("character_behavior_profiles.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("authority_level", sa.String(30), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.UniqueConstraint("character_id", "version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'SUPERSEDED')", name="profile_status"),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND authority_level = 'A7_AI_INFERENCE') OR "
            "(status IN ('APPROVED', 'SUPERSEDED') AND authority_level = 'A3_CANON')",
            name="profile_authority",
        ),
        sa.CheckConstraint("source = 'USER'", name="user_source"),
        sa.CheckConstraint("jsonb_typeof(body) = 'object'", name="profile_body"),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND approved_at IS NULL AND approved_by IS NULL) OR "
            "(status IN ('APPROVED', 'SUPERSEDED') AND approved_at IS NOT NULL "
            "AND approved_by IS NOT NULL)",
            name="approval_state",
        ),
    )
    op.create_index(
        "uq_character_behavior_profiles_approved",
        "character_behavior_profiles",
        ["character_id"],
        unique=True,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.execute(PROFILE_GUARD)
    op.execute(
        "CREATE TRIGGER guard_character_profile BEFORE INSERT OR UPDATE OR DELETE "
        "ON character_behavior_profiles FOR EACH ROW "
        "EXECUTE FUNCTION novel_guard_character_profile()"
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM memory_subjects WHERE batch_id IS NULL) THEN "
        "RAISE EXCEPTION 'Export manual character identities before downgrade'; END IF; END $$"
    )
    op.drop_table("character_behavior_profiles")
    op.execute("DROP FUNCTION novel_guard_character_profile()")
    op.execute(memory_guard(manual=False))
    op.drop_column("memory_subjects", "created_by")
    op.drop_column("memory_subjects", "created_at")
    op.alter_column("memory_subjects", "batch_id", nullable=False)


PROFILE_GUARD = r"""
CREATE FUNCTION novel_guard_character_profile() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous character_behavior_profiles; modifier jsonb;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Character profile history cannot be deleted' USING ERRCODE='23514';
    END IF;
    IF TG_OP='INSERT' THEN
        PERFORM id FROM projects WHERE id=NEW.project_id FOR UPDATE;
        IF NEW.status<>'DRAFT' OR NOT EXISTS (SELECT 1 FROM memory_subjects s
            WHERE s.id=NEW.character_id AND s.project_id=NEW.project_id AND s.kind='CHARACTER')
        THEN RAISE EXCEPTION 'Character profile must start as a project character draft' USING
            ERRCODE='23514'; END IF;
        SELECT * INTO previous FROM character_behavior_profiles
            WHERE character_id=NEW.character_id ORDER BY version DESC LIMIT 1;
        IF NEW.version<>COALESCE(previous.version,0)+1
            OR NEW.supersedes_id IS DISTINCT FROM previous.id
        THEN RAISE EXCEPTION 'Character profile version lineage mismatch' USING ERRCODE='23514';
        END IF;
        IF (NEW.body->>'risk_tolerance' IS NOT NULL AND
                NEW.body->>'risk_tolerance' NOT IN ('LOW','MEDIUM','HIGH'))
            OR NOT COALESCE(jsonb_typeof(NEW.body->'relationship_modifiers')='array',false)
            OR jsonb_array_length(NEW.body->'relationship_modifiers')>30
        THEN RAISE EXCEPTION 'Invalid character behavior body' USING ERRCODE='23514'; END IF;
        FOR modifier IN SELECT * FROM jsonb_array_elements(NEW.body->'relationship_modifiers') LOOP
            IF modifier->>'other_character_id'=NEW.character_id::text
                OR NOT EXISTS (SELECT 1 FROM memory_subjects s
                    WHERE s.id::text=modifier->>'other_character_id'
                    AND s.project_id=NEW.project_id AND s.kind='CHARACTER')
            THEN RAISE EXCEPTION 'Relationship modifier character scope mismatch' USING
                ERRCODE='23514'; END IF;
        END LOOP;
        IF (SELECT count(*) FROM jsonb_array_elements(NEW.body->'relationship_modifiers')) <>
            (SELECT count(DISTINCT m->>'other_character_id')
                FROM jsonb_array_elements(NEW.body->'relationship_modifiers') m)
        THEN RAISE EXCEPTION 'Duplicate relationship modifier' USING ERRCODE='23514'; END IF;
        RETURN NEW;
    END IF;
    IF (to_jsonb(NEW)-ARRAY['status','authority_level','approved_at','approved_by'])
        IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['status','authority_level','approved_at','approved_by'])
    THEN RAISE EXCEPTION 'Character profile version payload is immutable' USING ERRCODE='23514';
    END IF;
    IF OLD.status='DRAFT' AND NEW.status='APPROVED' AND NEW.authority_level='A3_CANON'
        AND NEW.version=(SELECT max(version) FROM character_behavior_profiles
            WHERE character_id=NEW.character_id)
    THEN RETURN NEW; END IF;
    IF OLD.status='APPROVED' AND NEW.status='SUPERSEDED'
        AND NEW.authority_level IS NOT DISTINCT FROM OLD.authority_level
        AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
        AND NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by
    THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Invalid character profile lifecycle transition' USING ERRCODE='23514';
END $$;
"""
