"""Versioned A5 project writing preferences; no story or workflow changes.

Revision ID: 0010_project_writing_profile
Revises: 0009_writing_agent
"""

from alembic import op

revision = "0010_project_writing_profile"
down_revision = "0009_writing_agent"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE project_writing_profiles (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id),
            version INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL,
            source VARCHAR(10) NOT NULL,
            authority_level VARCHAR(30) NOT NULL,
            preferences JSONB NOT NULL,
            created_by VARCHAR(128) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            approved_at TIMESTAMPTZ,
            approved_by VARCHAR(128),
            CONSTRAINT uq_project_writing_profiles_project_id UNIQUE(project_id, version),
            CONSTRAINT ck_project_writing_profiles_positive_version CHECK(version > 0),
            CONSTRAINT ck_project_writing_profiles_profile_status
                CHECK(status IN ('DRAFT', 'APPROVED', 'SUPERSEDED')),
            CONSTRAINT ck_project_writing_profiles_preference_authority
                CHECK(authority_level = 'A5_USER_PREFERENCE'),
            CONSTRAINT ck_project_writing_profiles_user_source CHECK(source = 'USER'),
            CONSTRAINT ck_project_writing_profiles_approval_state CHECK(
                (status = 'DRAFT' AND approved_at IS NULL AND approved_by IS NULL) OR
                (status IN ('APPROVED', 'SUPERSEDED') AND approved_at IS NOT NULL
                 AND approved_by IS NOT NULL))
        );
        CREATE UNIQUE INDEX uq_project_writing_profiles_approved ON project_writing_profiles
            (project_id) WHERE status = 'APPROVED';
        CREATE FUNCTION novel_guard_writing_profile() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Writing profile history cannot be deleted';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'DRAFT' THEN
                    RAISE EXCEPTION 'Writing profiles must start as drafts';
                END IF;
                RETURN NEW;
            END IF;
            IF (to_jsonb(NEW) - ARRAY['status', 'approved_at', 'approved_by'])
                IS DISTINCT FROM
                (to_jsonb(OLD) - ARRAY['status', 'approved_at', 'approved_by']) THEN
                RAISE EXCEPTION 'Writing profile version payload is immutable';
            END IF;
            IF OLD.status = 'DRAFT' AND NEW.status = 'APPROVED' THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'APPROVED' AND NEW.status = 'SUPERSEDED'
                AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
                AND NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'Invalid writing profile lifecycle transition';
        END $$;
        CREATE TRIGGER guard_writing_profile BEFORE INSERT OR UPDATE OR DELETE
            ON project_writing_profiles FOR EACH ROW EXECUTE FUNCTION novel_guard_writing_profile();
    """)


def downgrade():
    op.execute("DROP TABLE project_writing_profiles; DROP FUNCTION novel_guard_writing_profile();")
