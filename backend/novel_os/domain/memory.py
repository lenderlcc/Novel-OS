"""Chapter acceptance and append-only memory; no framework or ORM dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now

MEMORY_TASK = "EXTRACT_CHAPTER_MEMORY"


class MemoryType(StrEnum):
    CANON_FACT = "CANON_FACT"
    CHARACTER_STATE = "CHARACTER_STATE"
    CHARACTER_KNOWLEDGE = "CHARACTER_KNOWLEDGE"
    RELATIONSHIP_STATE = "RELATIONSHIP_STATE"
    OPEN_THREAD = "OPEN_THREAD"
    DERIVED_CHAPTER_SUMMARY = "DERIVED_CHAPTER_SUMMARY"


class EpistemicStatus(StrEnum):
    KNOWS = "KNOWS"
    BELIEVES = "BELIEVES"
    SUSPECTS = "SUSPECTS"
    DOUBTS = "DOUBTS"


class MemoryConflict(StrEnum):
    NONE = "NONE"
    DUPLICATE = "DUPLICATE"
    STATE_TRANSITION = "STATE_TRANSITION"
    CONTRADICTION = "CONTRADICTION"
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"


DERIVED_TYPES = {MemoryType.OPEN_THREAD, MemoryType.DERIVED_CHAPTER_SUMMARY}
STATE_TYPES = {
    MemoryType.CHARACTER_STATE,
    MemoryType.CHARACTER_KNOWLEDGE,
    MemoryType.RELATIONSHIP_STATE,
}
BLOCKING_CONFLICTS = {
    MemoryConflict.CONTRADICTION,
    MemoryConflict.AUTHORITY_CONFLICT,
    MemoryConflict.AMBIGUOUS,
}


@dataclass(frozen=True, kw_only=True)
class MemoryRequest:
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    chapter_version_id: UUID
    draft_version: int
    return_state: str
    profile_json: str
    authority_snapshot: dict
    canon_revision: int
    accepted_by: str
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class MemoryCommitProposal:
    id: UUID = field(default_factory=uuid4)
    request_id: UUID
    task_id: UUID
    agent_run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    raw_output: dict
    candidates: list[dict]
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class MemoryCommitBatch:
    id: UUID
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    chapter_version_id: UUID
    proposal_id: UUID
    canon_revision: int
    selected_candidate_ids: list[str]
    skipped_candidate_ids: list[str]
    expected_source_versions: dict
    confirmed_by: str
    status: str = "COMMITTED"
    created_at: datetime = field(default_factory=now)
    committed_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class MemorySubject:
    id: UUID
    project_id: UUID
    name: str
    normalized_name: str
    kind: str
    aliases: list[str]
    batch_id: UUID | None
    created_at: datetime = field(default_factory=now)
    created_by: str = "memory-commit"


@dataclass(frozen=True, kw_only=True)
class CommittedMemory:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    chapter_id: UUID
    chapter_version_id: UUID
    batch_id: UUID
    candidate_id: str
    logical_id: UUID
    version: int
    supersedes_id: UUID | None
    subject_id: UUID | None
    memory_type: str
    slot: str
    value: str
    statement: str
    epistemic_status: str | None
    authority_level: str
    body: dict
    created_at: datetime = field(default_factory=now)
