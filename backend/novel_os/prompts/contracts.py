import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{0,79}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class PromptConfigurationError(ValueError):
    """Safe configuration failure; never include prompt/context contents in the message."""


def normalize(value):
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def canonical(value) -> str:
    return json.dumps(
        normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ModuleType(StrEnum):
    SYSTEM_POLICY = "SYSTEM_POLICY"
    AGENT_ROLE = "AGENT_ROLE"
    TASK_TEMPLATE = "TASK_TEMPLATE"
    SKILL = "SKILL"
    QUALITY_PROFILE = "QUALITY_PROFILE"


class ModuleStatus(StrEnum):
    DRAFT = "DRAFT"
    EXPERIMENTAL = "EXPERIMENTAL"
    STABLE = "STABLE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class ModuleRef(FrozenModel):
    module_id: Identifier
    version: int | None = Field(default=None, strict=True, gt=0)


class ExactModuleRef(FrozenModel):
    module_id: Identifier
    version: int = Field(strict=True, gt=0)


class ModulePin(ExactModuleRef):
    content_hash: Digest
    execution_hash: Digest


class PromptModule(FrozenModel):
    module_id: Identifier
    module_type: ModuleType
    version: int = Field(strict=True, gt=0)
    status: ModuleStatus
    description: str = Field(min_length=1, max_length=1000)
    content_path: str = Field(min_length=1, max_length=300)
    dependencies: tuple[ExactModuleRef, ...]
    compatible_agents: tuple[str, ...] = Field(min_length=1)
    compatible_task_types: tuple[str, ...] = Field(min_length=1)
    created_at: datetime
    content_hash: Digest

    @property
    def execution_hash(self) -> str:
        # Status alone may advance in place. All other manifest fields identify the
        # immutable definition, including dependency/compatibility rules and body hash.
        return digest(canonical(self.model_dump(mode="json", exclude={"status"})))

    def pin(self):
        return ModulePin(
            module_id=self.module_id,
            version=self.version,
            content_hash=self.content_hash,
            execution_hash=self.execution_hash,
        )
