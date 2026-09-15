from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from novel_os.agents.planning_schemas import (
    ChapterPlanOutput,
    CreativeBriefOutput,
    PlanReviewOutput,
)
from novel_os.agents.schemas import ArtifactText
from novel_os.api.core_schemas import PlanView
from novel_os.api.workflow_schemas import CommandInput, Input
from novel_os.domain.planning import BriefStatus, ReviewVerdict


class CreatePlanningWorkflow(Input):
    event_id: UUID
    project_id: UUID
    chapter_id: UUID
    raw_requirement: ArtifactText = Field(min_length=1, max_length=12000)


class CorrectRequirement(CommandInput):
    expected_brief_version: int = Field(strict=True, ge=0)
    raw_requirement: ArtifactText = Field(min_length=1, max_length=12000)


class EvidenceView(BaseModel):
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    agent_run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    source_versions: list[dict]
    created_at: datetime


class BriefView(EvidenceView):
    version: int
    raw_requirement: str
    input_event_id: UUID
    status: BriefStatus
    body: CreativeBriefOutput
    supersedes_id: UUID | None


class GenerationView(EvidenceView):
    plan_id: UUID
    brief_id: UUID
    planning_iteration: int
    body: ChapterPlanOutput


class ReviewView(EvidenceView):
    plan_id: UUID
    brief_id: UUID
    verdict: ReviewVerdict
    body: PlanReviewOutput


class PlanningView(BaseModel):
    plan: PlanView
    generation: GenerationView


class HistoryView(BaseModel):
    briefs: list[BriefView]
    plans: list[GenerationView]
    reviews: list[ReviewView]


class MetricsView(BaseModel):
    workflow_id: UUID
    requirement_success_rate: float | None
    requirement_needs_human_rate: float | None
    requirement_correction_count: int
    requirement_correction_rate: float | None
    confidence_distribution: dict[str, int]
    planning_first_pass: bool | None
    planning_iterations: int
    human_first_pass_approval: bool | None
    human_rejection_count: int
    hard_gate_distribution: dict[str, int]
    technical_retry_count: int
