"""Versioned planning evidence, independent of transport, ORM and model schemas."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now
from novel_os.domain.enums import Authority


class BriefStatus(StrEnum):
    READY = "READY"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    SUPERSEDED = "SUPERSEDED"


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class ExplorationStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, kw_only=True)
class PlanningEvidence:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    agent_run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    source_versions: list[dict]
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class CreativeBrief(PlanningEvidence):
    version: int
    raw_requirement: str
    input_event_id: UUID
    status: BriefStatus
    body: dict
    supersedes_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class PlanGeneration(PlanningEvidence):
    plan_id: UUID
    brief_id: UUID
    planning_iteration: int
    body: dict
    creative_exploration_id: UUID | None = None
    selected_candidate_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class CreativeExploration(PlanningEvidence):
    brief_id: UUID
    body: dict
    status: ExplorationStatus

    @property
    def authority_level(self):
        return Authority.A7_AI_INFERENCE


@dataclass(frozen=True, kw_only=True)
class PlanReviewReport(PlanningEvidence):
    plan_id: UUID
    brief_id: UUID
    verdict: ReviewVerdict
    body: dict
