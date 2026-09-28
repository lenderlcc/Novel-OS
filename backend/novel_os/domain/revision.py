"""Append-only, exact-source revision evidence; no framework or database imports."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now

REVISION_TASKS = frozenset({"PLAN_CHAPTER_REVISION", "REVISE_CHAPTER"})


class RevisionScope(StrEnum):
    TARGETED = "TARGETED"
    FULL_PASS = "FULL_PASS"


@dataclass(frozen=True, kw_only=True)
class RevisionRequest:
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    source_chapter_version_id: UUID
    source_review_id: UUID
    source_binding_id: UUID
    source_context_package_id: UUID
    profile_json: str
    contract: dict
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class RevisionPlan:
    id: UUID = field(default_factory=uuid4)
    request_id: UUID
    task_id: UUID
    run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    body: dict
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class RevisionResult(RevisionPlan):
    revision_plan_id: UUID
    chapter_version_id: UUID | None
