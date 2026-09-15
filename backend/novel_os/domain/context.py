"""Immutable context values. No retrieval, framework, workflow mutation or Memory domain."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now
from novel_os.domain.enums import Authority, Status


class ContextStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    FAILED = "FAILED"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SourceType(StrEnum):
    TASK_INPUT = "TASK_INPUT"
    PROJECT = "PROJECT"
    CHAPTER = "CHAPTER"
    REQUIREMENT = "REQUIREMENT"
    DECISION = "DECISION"
    LOCK = "LOCK"
    CHAPTER_PLAN = "CHAPTER_PLAN"
    CHAPTER_VERSION = "CHAPTER_VERSION"
    EXTENSION = "EXTENSION"


class VersionPolicy(StrEnum):
    APPROVED = "APPROVED"
    CURRENT = "CURRENT"
    EXACT = "EXACT"
    EFFECTIVE = "EFFECTIVE"
    LOCKED = "LOCKED"
    TARGET_VERSION = "TARGET_VERSION"


class ContextScope(StrEnum):
    PROJECT = "PROJECT"
    TARGET_CHAPTER = "TARGET_CHAPTER"
    PREVIOUS_CHAPTER = "PREVIOUS_CHAPTER"
    EXPLICIT = "EXPLICIT"


class FutureKnowledgePolicy(StrEnum):
    NONE = "NONE"
    REQUIRED_ONLY = "REQUIRED_ONLY"
    LIMITED = "LIMITED"
    FULL = "FULL"


class KnowledgeScope(StrEnum):
    GLOBAL_ONLY = "GLOBAL_ONLY"
    CHARACTER_KNOWLEDGE = "CHARACTER_KNOWLEDGE"


class ExclusionReason(StrEnum):
    TOKEN_BUDGET = "TOKEN_BUDGET"
    LOW_PRIORITY = "LOW_PRIORITY"
    STATUS_FILTERED = "STATUS_FILTERED"
    AUTHORITY_SUPERSEDED = "AUTHORITY_SUPERSEDED"
    FUTURE_KNOWLEDGE = "FUTURE_KNOWLEDGE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    DUPLICATE = "DUPLICATE"
    VERSION_FILTERED = "VERSION_FILTERED"
    CHARACTER_KNOWLEDGE = "CHARACTER_KNOWLEDGE"


@dataclass(frozen=True, kw_only=True)
class SourceRef:
    source_type: SourceType
    logical_id: UUID
    version: int


@dataclass(frozen=True, kw_only=True)
class ContextRequest:
    project_id: UUID
    task_id: UUID
    task_type: str
    chapter_id: UUID
    workflow_id: UUID | None = None
    workflow_state_version: int | None = None
    attempt_number: int | None = None
    target_version: int | None = None
    approved_plan_version: int | None = None
    chapter_sequence: int = 1
    objective: str = ""
    requirements: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    explicit_refs: tuple[SourceRef, ...] = ()
    required_refs: tuple[SourceRef, ...] = ()
    missing_bindings: tuple[str, ...] = ()
    required_future_refs: tuple[SourceRef, ...] = ()
    knowledge_scope: KnowledgeScope = KnowledgeScope.GLOBAL_ONLY
    character_id: UUID | None = None
    request_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class ContextItem:
    context_item_id: UUID
    selector_id: str
    source_type: SourceType
    source_id: UUID
    logical_id: UUID
    source_version: int
    project_id: UUID
    status: Status
    authority_level: Authority
    locked: bool
    priority: Priority
    scope: ContextScope
    payload_json: str
    selected_reason: str
    source_created_at: datetime
    source_updated_at: datetime
    chapter_id: UUID | None = None
    chapter_sequence: int | None = None
    relevance_score: int = 0
    knowledge_scope: KnowledgeScope = KnowledgeScope.GLOBAL_ONLY
    character_id: UUID | None = None
    future_knowledge: bool = False
    is_plan: bool = False
    provenance: tuple[str, ...] = ()

    @property
    def structured_payload(self):
        # A copy on access; nested caller edits cannot change the snapshot.
        return json.loads(self.payload_json)

    @property
    def ref(self):
        return SourceRef(
            source_type=self.source_type, logical_id=self.logical_id, version=self.source_version
        )


@dataclass(frozen=True, kw_only=True)
class ExcludedItem:
    source_type: SourceType
    source_id: UUID
    source_version: int
    selector_id: str
    reason: ExclusionReason


@dataclass(frozen=True, kw_only=True)
class AuthorityConflict:
    source_type: SourceType
    logical_id: UUID
    source_ids: tuple[UUID, ...]


@dataclass(frozen=True, kw_only=True)
class SourceSnapshot:
    selector_id: str
    fingerprint: str


@dataclass(frozen=True, kw_only=True)
class ContextPackage:
    project_id: UUID
    task_id: UUID
    workflow_id: UUID | None
    request: ContextRequest
    profile_id: str
    profile_version: int
    profile_hash: str
    profile_json: str
    build_status: ContextStatus
    items: tuple[ContextItem, ...]
    excluded_items: tuple[ExcludedItem, ...]
    missing_required_items: tuple[str, ...]
    authority_conflicts: tuple[AuthorityConflict, ...]
    source_snapshots: tuple[SourceSnapshot, ...]
    token_budget: int
    prompt_overhead: int
    output_reservation: int
    estimated_tokens: int
    future_knowledge_policy: FutureKnowledgePolicy
    package_hash: str
    error_code: str | None = None
    context_package_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class ContextBuildResult:
    status: ContextStatus
    package: ContextPackage | None = None
    error_code: str | None = None
    missing_required_context: tuple[str, ...] = ()
    authority_conflicts: tuple[AuthorityConflict, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateBatch:
    items: tuple[ContextItem, ...] = ()
    excluded: tuple[ExcludedItem, ...] = ()
    snapshots: tuple[SourceSnapshot, ...] = ()
    overflow: tuple[str, ...] = ()
