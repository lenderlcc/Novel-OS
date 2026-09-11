"""Append-only prompt lineage; bodies remain in Git, existing run history is preserved."""

from alembic import op

revision = "0006_prompt_runtime"
down_revision = "0005_agent_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE prompt_lineages (
            lineage_id UUID PRIMARY KEY,
            agent_run_id UUID NOT NULL,
            task_id UUID NOT NULL,
            system_policy JSONB NOT NULL,
            agent_role JSONB NOT NULL,
            task_template JSONB NOT NULL,
            skills JSONB NOT NULL,
            quality_profile JSONB NOT NULL,
            output_schema_id VARCHAR(80) NOT NULL,
            output_schema_version INTEGER NOT NULL,
            output_schema_hash VARCHAR(64) NOT NULL,
            model_profile_id VARCHAR(80) NOT NULL,
            model_profile_hash VARCHAR(64) NOT NULL,
            model_profile JSONB NOT NULL,
            compiled_prompt_hash VARCHAR(64) NOT NULL,
            compiler_version INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_prompt_lineages_agent_run_id UNIQUE (agent_run_id),
            CONSTRAINT fk_prompt_lineages_agent_run_id_agent_runs
                FOREIGN KEY (agent_run_id, task_id) REFERENCES agent_runs(run_id, task_id),
            CONSTRAINT ck_prompt_lineages_positive_versions
                CHECK (output_schema_version > 0 AND compiler_version > 0),
            CONSTRAINT ck_prompt_lineages_valid_hashes
                CHECK (compiled_prompt_hash ~ '^[a-f0-9]{64}$'
                       AND output_schema_hash ~ '^[a-f0-9]{64}$'
                       AND model_profile_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_prompt_lineages_skills_array CHECK (jsonb_typeof(skills) = 'array')
        );
        CREATE INDEX ix_prompt_lineages_task_id ON prompt_lineages (task_id);
        CREATE FUNCTION protect_prompt_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Prompt lineage is immutable';
        END;
        $$;
        CREATE TRIGGER prompt_lineages_immutable BEFORE UPDATE OR DELETE ON prompt_lineages
            FOR EACH ROW EXECUTE FUNCTION protect_prompt_lineage();
    """)


def downgrade():
    op.execute("DROP TABLE prompt_lineages; DROP FUNCTION protect_prompt_lineage();")
