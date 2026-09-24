from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from novel_os.api.workflow_schemas import CommandInput
from novel_os.quality.schemas import ChapterReviewResult, ChapterReviewResultV2


class RequestReview(CommandInput):
    expected_draft_version: int = Field(strict=True, gt=0)


class QualityBindingView(BaseModel):
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    state_version: int
    chapter_version_id: UUID
    draft_version: int
    plan_id: UUID
    plan_version: int
    brief_id: UUID
    profile_record_id: UUID | None
    profile_version: int | None
    profile_hash: str | None
    created_at: datetime


class QualityReviewView(BaseModel):
    id: UUID
    binding_id: UUID
    project_id: UUID
    chapter_id: UUID
    chapter_version_id: UUID
    version: int
    compliance_pass_id: UUID
    narrative_pass_id: UUID
    body: ChapterReviewResult | ChapterReviewResultV2
    binding: QualityBindingView
    freshness: Literal["CURRENT", "STALE"]
    created_at: datetime
