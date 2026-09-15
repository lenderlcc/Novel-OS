"""Writing evidence is a proposal, never an approval or a canon commit."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now


class DeviationSeverity(StrEnum):
    LOCAL = "LOCAL"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"


class DraftCheckStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, kw_only=True)
class WritingTaskBinding:
    task_id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    plan_id: UUID
    plan_version: int
    expected_draft_version: int
    profile_json: str
    source_snapshots: list[dict]
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class WritingGeneration:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    agent_task_id: UUID
    agent_run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    plan_id: UUID
    plan_version: int
    brief_id: UUID | None
    chapter_version_id: UUID | None
    model_profile: str
    provider: str
    model: str
    content_hash: str
    metadata: dict
    check_status: DraftCheckStatus
    check_codes: list[str]
    created_at: datetime = field(default_factory=now)
