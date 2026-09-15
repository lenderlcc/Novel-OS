from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from novel_os.db.base import Base


class ContextPackageModel(Base):
    __tablename__ = "context_packages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["agent_run_id", "task_id"], ["agent_runs.run_id", "agent_runs.task_id"]
        ),
        UniqueConstraint("agent_run_id"),
        CheckConstraint("profile_version > 0", name="positive_profile_version"),
        CheckConstraint(
            "profile_hash ~ '^[a-f0-9]{64}$' AND package_hash ~ '^[a-f0-9]{64}$'",
            name="valid_hashes",
        ),
        CheckConstraint(
            "build_status IN ('READY','BLOCKED','STALE','FAILED')", name="build_status"
        ),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="snapshot_object"),
    )
    context_package_id: Mapped[UUID] = mapped_column(primary_key=True)
    agent_run_id: Mapped[UUID]
    task_id: Mapped[UUID] = mapped_column(index=True)
    profile_id: Mapped[str] = mapped_column(String(80))
    profile_version: Mapped[int]
    profile_hash: Mapped[str] = mapped_column(String(64))
    package_hash: Mapped[str] = mapped_column(String(64))
    build_status: Mapped[str] = mapped_column(String(16))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
