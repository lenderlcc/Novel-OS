from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


class EvidenceColumns:
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID] = mapped_column(index=True)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    source_versions: Mapped[list] = mapped_column(JSONB)
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def evidence_constraints():
    return (
        ForeignKeyConstraint(["chapter_id", "project_id"], ["chapters.id", "chapters.project_id"]),
        ForeignKeyConstraint(
            ["workflow_id", "project_id"],
            ["workflow_instances.id", "workflow_instances.project_id"],
        ),
        CheckConstraint(
            "jsonb_typeof(body) = 'object' AND jsonb_typeof(source_versions) = 'array'",
            name="json_shapes",
        ),
    )


class CreativeBriefModel(EvidenceColumns, Base):
    __tablename__ = "creative_briefs"
    __table_args__ = (
        *evidence_constraints(),
        UniqueConstraint("workflow_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("status IN ('READY', 'NEEDS_HUMAN', 'SUPERSEDED')", name="brief_status"),
    )
    version: Mapped[int]
    raw_requirement: Mapped[str] = mapped_column(Text)
    input_event_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_events.event_id"))
    status: Mapped[str] = mapped_column(String(20))
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("creative_briefs.id"))


class PlanGenerationModel(EvidenceColumns, Base):
    __tablename__ = "plan_generations"
    __table_args__ = (
        *evidence_constraints(),
        CheckConstraint("planning_iteration > 0", name="positive_iteration"),
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_plans.id"), unique=True)
    brief_id: Mapped[UUID] = mapped_column(ForeignKey("creative_briefs.id"))
    planning_iteration: Mapped[int]


class PlanReviewReportModel(EvidenceColumns, Base):
    __tablename__ = "plan_review_reports"
    __table_args__ = (
        *evidence_constraints(),
        CheckConstraint("verdict IN ('PASS', 'PASS_WITH_WARNINGS', 'FAIL')", name="review_verdict"),
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plan_generations.plan_id"), index=True)
    brief_id: Mapped[UUID] = mapped_column(ForeignKey("creative_briefs.id"))
    verdict: Mapped[str] = mapped_column(String(24))
