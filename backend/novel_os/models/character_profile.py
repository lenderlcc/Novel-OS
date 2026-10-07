from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


class CharacterBehaviorProfileModel(Base):
    __tablename__ = "character_behavior_profiles"
    __table_args__ = (
        UniqueConstraint("character_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED', 'SUPERSEDED')", name="profile_status"),
        CheckConstraint(
            "(status = 'DRAFT' AND authority_level = 'A7_AI_INFERENCE') OR "
            "(status IN ('APPROVED', 'SUPERSEDED') AND authority_level = 'A3_CANON')",
            name="profile_authority",
        ),
        CheckConstraint("source = 'USER'", name="user_source"),
        CheckConstraint("jsonb_typeof(body) = 'object'", name="profile_body"),
        CheckConstraint(
            "(status = 'DRAFT' AND approved_at IS NULL AND approved_by IS NULL) OR "
            "(status IN ('APPROVED', 'SUPERSEDED') AND approved_at IS NOT NULL "
            "AND approved_by IS NOT NULL)",
            name="approval_state",
        ),
        Index(
            "uq_character_behavior_profiles_approved",
            "character_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    character_id: Mapped[UUID] = mapped_column(ForeignKey("memory_subjects.id"))
    version: Mapped[int]
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("character_behavior_profiles.id"))
    status: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(10))
    authority_level: Mapped[str] = mapped_column(String(30))
    body: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(String(128))
    source_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(128))
