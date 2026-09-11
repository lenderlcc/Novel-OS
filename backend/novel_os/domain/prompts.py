from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from novel_os.domain.core import now


@dataclass(frozen=True, kw_only=True)
class PromptLineage:
    agent_run_id: UUID
    task_id: UUID
    system_policy: dict
    agent_role: dict
    task_template: dict
    skills: list[dict]
    quality_profile: dict
    output_schema_id: str
    output_schema_version: int
    output_schema_hash: str
    model_profile_id: str
    model_profile_hash: str
    model_profile: dict
    compiled_prompt_hash: str
    compiler_version: int = 1
    lineage_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)
