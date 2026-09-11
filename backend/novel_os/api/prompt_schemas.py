from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from novel_os.prompts.contracts import Digest, ModulePin
from novel_os.providers.profiles import ModelProfile


class ModulePinView(ModulePin):
    # Old immutable lineages did not record execution metadata. Never fabricate it.
    execution_hash: Digest | None = None


class PromptLineageView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lineage_id: UUID
    agent_run_id: UUID
    task_id: UUID
    system_policy: ModulePinView
    agent_role: ModulePinView
    task_template: ModulePinView
    skills: list[ModulePinView]
    quality_profile: ModulePinView
    output_schema_id: str
    output_schema_version: int
    output_schema_hash: str
    model_profile_id: str
    model_profile_hash: str
    model_profile: ModelProfile
    compiled_prompt_hash: str
    compiler_version: int
    created_at: datetime
