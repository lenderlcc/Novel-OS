from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from novel_os.agents.writing_schemas import WritingMetadata
from novel_os.api.workflow_schemas import CommandInput
from novel_os.domain.writing import DraftCheckStatus


class RegenerateDraft(CommandInput):
    expected_draft_version: int = Field(strict=True, gt=0)


class WritingGenerationView(BaseModel):
    id: UUID
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
    metadata: WritingMetadata
    check_status: DraftCheckStatus
    check_codes: list[str]
    created_at: datetime
