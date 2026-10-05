"""Append-only memory evidence and project-scoped retrieval indexes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.models.writing import scope_constraints


class MemoryRequestModel(Base):
    __tablename__ = "memory_requests"
    __table_args__ = (*scope_constraints(),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID]
    workflow_id: Mapped[UUID] = mapped_column(index=True)
    chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    draft_version: Mapped[int]
    return_state: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text)
    authority_snapshot: Mapped[dict] = mapped_column(JSONB)
    canon_revision: Mapped[int]
    accepted_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MemoryProposalModel(Base):
    __tablename__ = "memory_commit_proposals"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("memory_requests.id"), unique=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("agent_tasks.task_id"), unique=True)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.run_id"), unique=True)
    prompt_lineage_id: Mapped[UUID] = mapped_column(ForeignKey("prompt_lineages.lineage_id"))
    context_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_packages.context_package_id")
    )
    raw_output: Mapped[dict] = mapped_column(JSONB)
    candidates: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MemoryBatchModel(Base):
    __tablename__ = "memory_commit_batches"
    __table_args__ = (
        *scope_constraints(),
        UniqueConstraint("project_id", "canon_revision"),
        CheckConstraint("canon_revision > 0 AND status = 'COMMITTED'", name="committed_revision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    chapter_id: Mapped[UUID] = mapped_column(unique=True)
    workflow_id: Mapped[UUID]
    chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"), unique=True)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("memory_commit_proposals.id"), unique=True)
    canon_revision: Mapped[int]
    selected_candidate_ids: Mapped[list] = mapped_column(JSONB)
    skipped_candidate_ids: Mapped[list] = mapped_column(JSONB)
    expected_source_versions: Mapped[dict] = mapped_column(JSONB)
    confirmed_by: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MemorySubjectModel(Base):
    __tablename__ = "memory_subjects"
    __table_args__ = (UniqueConstraint("project_id", "kind", "normalized_name"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSONB)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("memory_commit_batches.id"))


class MemoryEntryModel(Base):
    __tablename__ = "committed_memory"
    __table_args__ = (
        UniqueConstraint("logical_id", "version"),
        UniqueConstraint("batch_id", "candidate_id"),
        CheckConstraint("version > 0", name="memory_version"),
        CheckConstraint(
            "(memory_type IN ('OPEN_THREAD','DERIVED_CHAPTER_SUMMARY') AND "
            "authority_level = 'A6_DERIVED_MEMORY') OR (memory_type IN "
            "('CANON_FACT','CHARACTER_STATE','CHARACTER_KNOWLEDGE','RELATIONSHIP_STATE') "
            "AND authority_level = 'A3_CANON')",
            name="memory_authority",
        ),
        CheckConstraint(
            "(memory_type = 'CHARACTER_KNOWLEDGE' AND epistemic_status IN "
            "('KNOWS','BELIEVES','SUSPECTS','DOUBTS') AND subject_id IS NOT NULL) OR "
            "(memory_type <> 'CHARACTER_KNOWLEDGE' AND epistemic_status IS NULL)",
            name="memory_knowledge_owner",
        ),
        Index("ix_memory_retrieval", "project_id", "subject_id", "memory_type", "authority_level"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id"))
    chapter_version_id: Mapped[UUID] = mapped_column(ForeignKey("chapter_versions.id"))
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("memory_commit_batches.id"))
    candidate_id: Mapped[str] = mapped_column(Text)
    logical_id: Mapped[UUID]
    version: Mapped[int]
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("committed_memory.id"), unique=True
    )
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("memory_subjects.id"))
    memory_type: Mapped[str] = mapped_column(Text)
    slot: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    epistemic_status: Mapped[str | None] = mapped_column(Text)
    authority_level: Mapped[str] = mapped_column(Text)
    body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


Index(
    "ix_memory_fts",
    func.to_tsvector(literal_column("'simple'"), MemoryEntryModel.statement),
    postgresql_using="gin",
    _table=MemoryEntryModel.__table__,
)
