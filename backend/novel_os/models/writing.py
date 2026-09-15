from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


def scope_constraints():
    return (
        ForeignKeyConstraint(["chapter_id", "project_id"], ["chapters.id", "chapters.project_id"]),
        ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
        ),
    )


class WritingTaskBindingModel(Base):
    __tablename__ = "writing_task_bindings"
    __table_args__ = (
        *scope_constraints(),
        CheckConstraint("plan_version > 0 AND expected_draft_version >= 0", name="versions"),
        CheckConstraint("jsonb_typeof(source_snapshots) = 'array'", name="snapshot_shape"),
    )
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID]
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_plans.id"))
    plan_version: Mapped[int]
    expected_draft_version: Mapped[int]
    profile_json: Mapped[str] = mapped_column(Text)
    source_snapshots: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WritingGenerationModel(Base):
    __tablename__ = "writing_generations"
    __table_args__ = (
        *scope_constraints(),
        CheckConstraint("plan_version > 0", name="plan_version"),
        CheckConstraint(
            "(check_status = 'PASS' AND chapter_version_id IS NOT NULL) OR "
            "(check_status = 'BLOCKED' AND chapter_version_id IS NULL)",
            name="check_relation",
        ),
        CheckConstraint(
            "jsonb_typeof(metadata) = 'object' AND jsonb_typeof(check_codes) = 'array'",
            name="metadata_shape",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID] = mapped_column(index=True)
    agent_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("writing_task_bindings.task_id"), unique=True
    )
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_plans.id"))
    plan_version: Mapped[int]
    brief_id: Mapped[UUID | None] = mapped_column(ForeignKey("creative_briefs.id"))
    chapter_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_versions.id"), unique=True
    )
    model_profile: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    result_metadata: Mapped[dict] = mapped_column("metadata", JSONB)
    check_status: Mapped[str] = mapped_column(String(20))
    check_codes: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
