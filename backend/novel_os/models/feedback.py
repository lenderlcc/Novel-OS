from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.models.writing import scope_constraints


class HumanFeedbackModel(Base):
    __tablename__ = "human_feedback"
    __table_args__ = (
        *scope_constraints(),
        CheckConstraint("source = 'USER' AND status = 'RECORDED'", name="user_feedback_source"),
        CheckConstraint("source_draft_version > 0", name="feedback_draft_version"),
        CheckConstraint(
            "length(btrim(raw_feedback)) > 0 AND length(raw_feedback) <= 12000",
            name="feedback_nonempty",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID]
    source_chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    source_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_draft_version: Mapped[int]
    source_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("chapter_quality_reviews.id"))
    raw_feedback: Mapped[str] = mapped_column(Text)
    reply_to_feedback_id: Mapped[UUID | None] = mapped_column(ForeignKey("human_feedback.id"))
    return_state: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text)
    authority_snapshot: Mapped[dict] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeedbackInterpretationModel(Base):
    __tablename__ = "human_feedback_interpretations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("human_feedback.id"), unique=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), unique=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
