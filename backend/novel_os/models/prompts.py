from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


class PromptLineageModel(Base):
    __tablename__ = "prompt_lineages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["agent_run_id", "task_id"], ["agent_runs.run_id", "agent_runs.task_id"]
        ),
        UniqueConstraint("agent_run_id"),
        CheckConstraint(
            "output_schema_version > 0 AND compiler_version > 0", name="positive_versions"
        ),
        CheckConstraint(
            "compiled_prompt_hash ~ '^[a-f0-9]{64}$' AND "
            "output_schema_hash ~ '^[a-f0-9]{64}$' AND "
            "model_profile_hash ~ '^[a-f0-9]{64}$'",
            name="valid_hashes",
        ),
        CheckConstraint("jsonb_typeof(skills) = 'array'", name="skills_array"),
    )
    lineage_id: Mapped[UUID] = mapped_column(primary_key=True)
    agent_run_id: Mapped[UUID]
    task_id: Mapped[UUID] = mapped_column(index=True)
    system_policy: Mapped[dict] = mapped_column(JSONB)
    agent_role: Mapped[dict] = mapped_column(JSONB)
    task_template: Mapped[dict] = mapped_column(JSONB)
    skills: Mapped[list] = mapped_column(JSONB)
    quality_profile: Mapped[dict] = mapped_column(JSONB)
    output_schema_id: Mapped[str] = mapped_column(String(80))
    output_schema_version: Mapped[int]
    output_schema_hash: Mapped[str] = mapped_column(String(64))
    model_profile_id: Mapped[str] = mapped_column(String(80))
    model_profile_hash: Mapped[str] = mapped_column(String(64))
    model_profile: Mapped[dict] = mapped_column(JSONB)
    compiled_prompt_hash: Mapped[str] = mapped_column(String(64))
    compiler_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
