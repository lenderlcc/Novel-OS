from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


class ProjectWritingProfileModel(Base):
    __tablename__ = "project_writing_profiles"
    __table_args__ = (
        UniqueConstraint("project_id", "version"),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED', 'SUPERSEDED')", name="profile_status"),
        CheckConstraint("authority_level = 'A5_USER_PREFERENCE'", name="preference_authority"),
        CheckConstraint("source = 'USER'", name="user_source"),
        CheckConstraint(
            "(status = 'DRAFT' AND approved_at IS NULL AND approved_by IS NULL) OR "
            "(status IN ('APPROVED', 'SUPERSEDED') AND approved_at IS NOT NULL "
            "AND approved_by IS NOT NULL)",
            name="approval_state",
        ),
        Index(
            "uq_project_writing_profiles_approved",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(10))
    authority_level: Mapped[str] = mapped_column(String(30))
    preferences: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(128))
