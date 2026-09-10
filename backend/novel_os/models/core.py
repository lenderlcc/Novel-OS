from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base
from novel_os.domain.enums import (
    ActorType,
    AuditAction,
    Authority,
    ObjectType,
    RequirementType,
    ScopeType,
    Status,
)


def enum_type(enum):
    return Enum(enum, native_enum=False, create_constraint=True)


class RecordColumns:
    id: Mapped[UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[Status] = mapped_column(enum_type(Status))
    source: Mapped[ActorType] = mapped_column(enum_type(ActorType))
    authority_level: Mapped[Authority] = mapped_column(enum_type(Authority))
    locked: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128))
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list] = mapped_column(JSONB)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB)


class ProjectModel(RecordColumns, Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("version > 0", name="positive_version"),)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)

    @property
    def project_id(self) -> UUID:
        return self.id


class ProjectColumns:
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)


class VersionColumns(RecordColumns, ProjectColumns):
    logical_id: Mapped[UUID] = mapped_column(index=True)
    supersedes_id: Mapped[UUID | None]


def version_constraints(table: str):
    return (
        UniqueConstraint("logical_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
        ForeignKeyConstraint(["supersedes_id"], [f"{table}.id"]),
        Index(
            f"uq_{table}_approved",
            "logical_id",
            unique=True,
            postgresql_where=text("status IN ('APPROVED', 'LOCKED') AND approved_at IS NOT NULL"),
        ),
    )


class RequirementModel(VersionColumns, Base):
    __tablename__ = "requirements"
    __table_args__ = (
        *version_constraints("requirements"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="priority_range"),
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="effective_range",
        ),
    )
    content: Mapped[str] = mapped_column(Text)
    requirement_type: Mapped[RequirementType] = mapped_column(enum_type(RequirementType))
    scope_type: Mapped[ScopeType] = mapped_column(enum_type(ScopeType))
    scope_id: Mapped[UUID]
    priority: Mapped[int]
    persistent: Mapped[bool]
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DecisionModel(VersionColumns, Base):
    __tablename__ = "decisions"
    __table_args__ = version_constraints("decisions")
    question: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    affected_objects: Mapped[list] = mapped_column(JSONB)


class ChapterModel(RecordColumns, ProjectColumns, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence"),
        UniqueConstraint("id", "project_id"),
        CheckConstraint("sequence > 0", name="positive_sequence"),
        CheckConstraint("version > 0", name="positive_version"),
        *(
            ForeignKeyConstraint(
                ["id", column],
                [f"{table}.chapter_id", f"{table}.version"],
                name=f"fk_chapters_{column}",
                use_alter=True,
                deferrable=True,
                initially="DEFERRED",
            )
            for column, table in (
                ("current_version", "chapter_versions"),
                ("approved_version", "chapter_versions"),
                ("current_plan_version", "chapter_plans"),
                ("approved_plan_version", "chapter_plans"),
            )
        ),
    )
    sequence: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    current_version: Mapped[int | None]
    approved_version: Mapped[int | None]
    current_plan_version: Mapped[int | None]
    approved_plan_version: Mapped[int | None]


def chapter_version_constraints(table: str):
    return (
        *version_constraints(table),
        UniqueConstraint("chapter_id", "version"),
        CheckConstraint("logical_id = chapter_id", name="chapter_logical_id"),
        ForeignKeyConstraint(["chapter_id", "project_id"], ["chapters.id", "chapters.project_id"]),
    )


class ChapterPlanModel(VersionColumns, Base):
    __tablename__ = "chapter_plans"
    __table_args__ = chapter_version_constraints("chapter_plans")
    chapter_id: Mapped[UUID]
    objective: Mapped[str] = mapped_column(Text)
    required_outcome: Mapped[str] = mapped_column(Text)
    scene_plans: Mapped[list] = mapped_column(JSONB)
    character_progression: Mapped[dict] = mapped_column(JSONB)
    plot_progression: Mapped[dict] = mapped_column(JSONB)
    information_release: Mapped[list] = mapped_column(JSONB)
    ending_state: Mapped[dict] = mapped_column(JSONB)
    constraints: Mapped[list] = mapped_column(JSONB)
    locked_dependencies: Mapped[list] = mapped_column(JSONB)
    risks: Mapped[list] = mapped_column(JSONB)


class ChapterVersionModel(VersionColumns, Base):
    __tablename__ = "chapter_versions"
    __table_args__ = chapter_version_constraints("chapter_versions")
    chapter_id: Mapped[UUID]
    parent_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("chapter_versions.id"))
    content: Mapped[str] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(Text)


class LockModel(ProjectColumns, Base):
    __tablename__ = "locks"
    __table_args__ = (
        Index(
            "uq_locks_active_target",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("active"),
        ),
        CheckConstraint("target_version > 0", name="positive_target_version"),
        CheckConstraint("scope = 'OBJECT'", name="object_scope"),
        CheckConstraint("active = (released_at IS NULL)", name="release_state"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    target_type: Mapped[ObjectType] = mapped_column(enum_type(ObjectType))
    target_id: Mapped[UUID]
    target_version: Mapped[int]
    reason: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool]
    locked_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[str | None] = mapped_column(String(128))
    release_reason: Mapped[str | None] = mapped_column(Text)
    previous_status: Mapped[Status] = mapped_column(enum_type(Status))
    previous_authority: Mapped[Authority] = mapped_column(enum_type(Authority))


class AuditRecordModel(ProjectColumns, Base):
    __tablename__ = "audit_records"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    target_type: Mapped[ObjectType] = mapped_column(enum_type(ObjectType))
    target_id: Mapped[UUID] = mapped_column(index=True)
    target_version: Mapped[int]
    action: Mapped[AuditAction] = mapped_column(enum_type(AuditAction))
    actor_type: Mapped[ActorType] = mapped_column(enum_type(ActorType))
    actor_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(Text)
    before: Mapped[dict] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
