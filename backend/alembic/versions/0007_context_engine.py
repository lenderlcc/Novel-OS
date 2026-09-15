"""Immutable context execution snapshots, preserving all existing history."""

from alembic import op

revision = "0007_context_engine"
down_revision = "0006_prompt_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE context_packages (
            context_package_id UUID PRIMARY KEY,
            agent_run_id UUID NOT NULL,
            task_id UUID NOT NULL,
            profile_id VARCHAR(80) NOT NULL,
            profile_version INTEGER NOT NULL,
            profile_hash VARCHAR(64) NOT NULL,
            package_hash VARCHAR(64) NOT NULL,
            build_status VARCHAR(16) NOT NULL,
            snapshot JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT fk_context_packages_agent_run_id_agent_runs
                FOREIGN KEY (agent_run_id, task_id) REFERENCES agent_runs(run_id, task_id),
            CONSTRAINT uq_context_packages_agent_run_id UNIQUE (agent_run_id),
            CONSTRAINT ck_context_packages_positive_profile_version CHECK (profile_version > 0),
            CONSTRAINT ck_context_packages_valid_hashes CHECK (profile_hash ~ '^[a-f0-9]{64}$'
                AND package_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_context_packages_build_status CHECK (build_status IN
                ('READY','BLOCKED','STALE','FAILED')),
            CONSTRAINT ck_context_packages_snapshot_object CHECK (jsonb_typeof(snapshot) = 'object')
        );
        CREATE INDEX ix_context_packages_task_id ON context_packages(task_id);
        CREATE FUNCTION protect_context_package() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Context package is immutable' USING ERRCODE = '23514';
        END;
        $$;
        CREATE TRIGGER context_packages_immutable BEFORE UPDATE OR DELETE ON context_packages
            FOR EACH ROW EXECUTE FUNCTION protect_context_package();
    """)


def downgrade():
    op.execute("DROP TABLE context_packages; DROP FUNCTION protect_context_package();")
