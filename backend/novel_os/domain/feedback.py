"""Immutable user revision intent, separate from requirements and evaluation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now

FEEDBACK_TASK = "INTERPRET_CHAPTER_FEEDBACK"


class FeedbackAction(StrEnum):
    REVISION = "REVISION"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    PROFILE_CHANGE_REQUIRED = "PROFILE_CHANGE_REQUIRED"
    USER_DECISION_REQUIRED = "USER_DECISION_REQUIRED"
    NO_CHANGE = "NO_CHANGE"


class FeedbackScope(StrEnum):
    LOCAL = "LOCAL"
    SECTION = "SECTION"
    CHAPTER_WIDE = "CHAPTER_WIDE"


class RevisionSource(StrEnum):
    AI_REVIEW = "AI_REVIEW"
    HUMAN_FEEDBACK = "HUMAN_FEEDBACK"
    BOTH = "BOTH"


@dataclass(frozen=True, kw_only=True)
class HumanFeedback:
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    source_chapter_version_id: UUID
    source_state_version: int
    source_draft_version: int
    source_review_id: UUID | None
    raw_feedback: str
    return_state: str
    profile_json: str
    authority_snapshot: dict
    reply_to_feedback_id: UUID | None = None
    source: str = "USER"
    status: str = "RECORDED"
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class HumanFeedbackInterpretation:
    id: UUID = field(default_factory=uuid4)
    feedback_id: UUID
    task_id: UUID
    run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    body: dict
    created_at: datetime = field(default_factory=now)
