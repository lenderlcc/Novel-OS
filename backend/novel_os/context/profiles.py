"""Validated, versioned structured selectors; file definitions are not agent instructions."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from novel_os.domain.context import (
    ContextScope,
    FutureKnowledgePolicy,
    Priority,
    SourceType,
    VersionPolicy,
)
from novel_os.domain.enums import Authority, RequirementType, Status
from novel_os.prompts.contracts import FrozenModel, Identifier, ModuleStatus, canonical, digest
from novel_os.prompts.registry import unique_object


class ContextConfigurationError(ValueError):
    pass


class ContextSelector(FrozenModel):
    selector_id: Identifier
    source_type: SourceType
    priority: Priority
    required: bool = Field(strict=True)
    authority_floor: Authority
    allowed_statuses: tuple[Status, ...] = Field(min_length=1)
    version_policy: VersionPolicy
    scope: ContextScope
    max_items: int = Field(strict=True, ge=1, le=1000)
    requirement_types: tuple[RequirementType, ...] = ()
    ranking_policy: Literal["PRIORITY_AUTHORITY_RELEVANCE_SCOPE_FRESHNESS"] = (
        "PRIORITY_AUTHORITY_RELEVANCE_SCOPE_FRESHNESS"
    )
    serialization_policy: Literal["STRUCTURED"] = "STRUCTURED"

    @model_validator(mode="after")
    def safe_selection(self):
        if self.required and self.priority != Priority.P0:
            raise ValueError("Required selectors must be P0")
        if set(self.allowed_statuses) & {
            Status.SUPERSEDED,
            Status.DEPRECATED,
            Status.CANCELLED,
            Status.ARCHIVED,
            Status.STALE,
        }:
            raise ValueError("Inactive sources cannot be effective context")
        if set(self.allowed_statuses) & {Status.DRAFT, Status.PROPOSED} and (
            self.version_policy not in {VersionPolicy.EXACT, VersionPolicy.TARGET_VERSION}
            or self.scope not in {ContextScope.EXPLICIT, ContextScope.TARGET_CHAPTER}
        ):
            raise ValueError("Drafts require an explicit target version")
        return self


class ContextProfile(FrozenModel):
    profile_id: Identifier
    version: int = Field(strict=True, gt=0)
    status: ModuleStatus
    description: str = Field(min_length=1, max_length=2000)
    allowed_task_types: tuple[str, ...] = Field(min_length=1)
    token_budget: int = Field(strict=True, ge=1, le=1_000_000)
    future_knowledge_policy: FutureKnowledgePolicy
    future_horizon: int = Field(default=1, strict=True, ge=0, le=10)
    selectors: tuple[ContextSelector, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_selectors(self):
        if len({s.selector_id for s in self.selectors}) != len(self.selectors):
            raise ValueError("Duplicate context selector")
        return self

    @property
    def profile_hash(self):
        return digest(canonical(self.model_dump(mode="json", exclude={"status"})))


TASK_PROFILES = {
    "PARSE_CHAPTER_REQUIREMENT": "CP-003A",
    "PLAN_CHAPTER": "CP-004",
    "REVIEW_CHAPTER_PLAN": "CP-004R",
    "CHAPTER_PLANNING": "CP-004",
    "CHAPTER_WRITING": "CP-005",
    "CHAPTER_REVIEW": "CP-006",
    "CHAPTER_REVISION": "CP-007",
    "MOCK_PLAN": "CP-004",
    "MOCK_WRITE": "CP-005",
    "MOCK_CHECK": "CP-006",
    "MOCK_REVIEW": "CP-006",
    "MOCK_REVISE": "CP-007",
}


class ContextProfileRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).parent / "profiles"
        self._profiles = {}
        try:
            for path in sorted(self.root.glob("*.json")):
                profile = ContextProfile.model_validate(
                    json.loads(path.read_text(), object_pairs_hook=unique_object)
                )
                key = (profile.profile_id, profile.version)
                if key in self._profiles:
                    raise ValueError("Duplicate context profile")
                self._profiles[key] = profile
            if not self._profiles:
                raise ValueError("No profiles")
        except (OSError, ValueError, RecursionError):
            raise ContextConfigurationError("Invalid context profile library") from None

    def resolve(self, profile_id, version=None, *, expected_hash=None):
        candidates = [
            p
            for (name, _), p in self._profiles.items()
            if name == profile_id
            and (p.version == version if version is not None else p.status == ModuleStatus.STABLE)
        ]
        profile = max(candidates, key=lambda p: p.version, default=None)
        if profile is None or profile.status == ModuleStatus.RETIRED:
            raise ContextConfigurationError("Context profile not available")
        if expected_hash is not None and expected_hash != profile.profile_hash:
            raise ContextConfigurationError("Context profile version conflict")
        return profile

    def for_task(self, task_type):
        candidates = [
            p
            for p in self._profiles.values()
            if p.profile_id == TASK_PROFILES.get(task_type, "CP-000")
            and p.status == ModuleStatus.STABLE
            and task_type in p.allowed_task_types
        ]
        profile = max(candidates, key=lambda p: p.version, default=None)
        if profile is None:
            raise ContextConfigurationError("Task not supported by context profile")
        return profile

    def reload(self):
        new = ContextProfileRegistry(self.root)
        if any(
            key not in new._profiles or old.profile_hash != new._profiles[key].profile_hash
            for key, old in self._profiles.items()
        ):
            raise ContextConfigurationError("Existing context profile version changed")
        self._profiles = new._profiles
