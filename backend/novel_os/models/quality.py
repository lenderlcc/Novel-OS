"""Append-only review snapshots, passes and aggregate results."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.models.writing import scope_constraints


class QualityBindingModel(Base):
    __tablename__ = "quality_review_bindings"
    __table_args__ = (
        *scope_constraints(),
        UniqueConstraint("workflow_id", "state_version"),
        CheckConstraint(
            "draft_version > 0 AND plan_version > 0 AND state_version > 0", name="positive_versions"
        ),
        CheckConstraint(
            "(profile_record_id IS NULL AND profile_version IS NULL AND profile_hash IS NULL) OR "
            "(profile_record_id IS NOT NULL AND profile_version > 0 AND profile_hash IS NOT NULL)",
            name="profile_binding",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID]
    state_version: Mapped[int]
    chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    draft_version: Mapped[int]
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_plans.id"))
    plan_version: Mapped[int]
    brief_id: Mapped[UUID] = mapped_column(ForeignKey("creative_briefs.id"))
    profile_record_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_writing_profiles.id")
    )
    profile_version: Mapped[int | None]
    profile_hash: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text)
    source_snapshots: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QualityPassModel(Base):
    __tablename__ = "quality_review_passes"
    __table_args__ = (
        UniqueConstraint("binding_id", "pass_name"),
        CheckConstraint("pass_name IN ('COMPLIANCE', 'NARRATIVE')", name="pass_name"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    binding_id: Mapped[UUID] = mapped_column(ForeignKey("quality_review_bindings.id"))
    pass_name: Mapped[str] = mapped_column(Text)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), unique=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChapterQualityReviewModel(Base):
    __tablename__ = "chapter_quality_reviews"
    __table_args__ = (
        UniqueConstraint("chapter_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    binding_id: Mapped[UUID] = mapped_column(ForeignKey("quality_review_bindings.id"), unique=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id"))
    chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    version: Mapped[int]
    compliance_pass_id: Mapped[UUID] = mapped_column(
        ForeignKey("quality_review_passes.id"), unique=True
    )
    narrative_pass_id: Mapped[UUID] = mapped_column(
        ForeignKey("quality_review_passes.id"), unique=True
    )
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
