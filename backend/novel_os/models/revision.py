from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.models.writing import scope_constraints


class RevisionRequestModel(Base):
    __tablename__ = "revision_requests"
    __table_args__ = scope_constraints()
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID]
    source_chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    source_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("chapter_quality_reviews.id"))
    source_binding_id: Mapped[UUID | None] = mapped_column(ForeignKey("quality_review_bindings.id"))
    source_context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    source_feedback_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("human_feedback.id"), unique=True
    )
    profile_json: Mapped[str] = mapped_column(Text)
    contract: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RevisionEvidenceColumns:
    id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("revision_requests.id"), unique=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), unique=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RevisionPlanModel(RevisionEvidenceColumns, Base):
    __tablename__ = "revision_plans"


class RevisionCandidateModel(RevisionEvidenceColumns, Base):
    __tablename__ = "revision_candidates"
    revision_plan_id: Mapped[UUID] = mapped_column(ForeignKey("revision_plans.id"), unique=True)


class RevisionResultModel(RevisionEvidenceColumns, Base):
    __tablename__ = "revision_results"
    revision_plan_id: Mapped[UUID] = mapped_column(ForeignKey("revision_plans.id"), unique=True)
    chapter_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapter_versions.id"), unique=True
    )
