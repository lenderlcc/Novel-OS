from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from novel_os.domain.enums import (
    ActorType,
    AuditAction,
    Authority,
    ObjectType,
    RequirementType,
    ScopeType,
    Status,
)
from novel_os.domain.errors import DomainError

MAX_CHAPTER_SEQUENCE = 2**31 - 1


def now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CommandContext:
    request_id: str
    actor_id: str
    actor_type: ActorType = ActorType.USER

    def require_user(self) -> None:
        if self.actor_type != ActorType.USER or not self.actor_id.strip():
            raise DomainError("AUTHORITY_DENIED", "This operation requires a user")


@dataclass(frozen=True)
class VersionToken:
    expected: int

    def check(self, actual: int) -> None:
        if type(self.expected) is not int or self.expected < 0 or self.expected != actual:
            raise DomainError("VERSION_CONFLICT", "The object version has changed; reload it")


@dataclass(frozen=True)
class ObjectRef:
    object_type: ObjectType
    object_id: UUID


@dataclass(frozen=True, kw_only=True)
class Record:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    version: int = 1
    status: Status = Status.PROPOSED
    source: ActorType = ActorType.USER
    authority_level: Authority = Authority.A5_USER_PREFERENCE
    locked: bool = False
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)
    created_by: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def require_editable(self) -> None:
        if self.locked:
            raise DomainError("LOCKED_OBJECT", "The object is locked")
        if self.status not in {Status.DRAFT, Status.PROPOSED, Status.ACTIVE}:
            raise DomainError("INVALID_STATE", "Create a new version instead of editing this state")


@dataclass(frozen=True, kw_only=True)
class VersionedRecord(Record):
    logical_id: UUID = field(default_factory=uuid4)
    supersedes_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class Project(Record):
    object_type: ClassVar[ObjectType] = ObjectType.PROJECT
    name: str
    description: str = ""
    status: Status = Status.ACTIVE


@dataclass(frozen=True, kw_only=True)
class Requirement(VersionedRecord):
    object_type: ClassVar[ObjectType] = ObjectType.REQUIREMENT
    content: str
    requirement_type: RequirementType = RequirementType.MUST
    scope_type: ScopeType = ScopeType.PROJECT
    scope_id: UUID
    priority: int = 1
    persistent: bool = False
    effective_from: datetime | None = None
    effective_until: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class Decision(VersionedRecord):
    object_type: ClassVar[ObjectType] = ObjectType.DECISION
    question: str
    decision: str
    rationale: str = ""
    affected_objects: list[dict] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class Chapter(Record):
    object_type: ClassVar[ObjectType] = ObjectType.CHAPTER
    sequence: int
    title: str
    status: Status = Status.DRAFT
    current_version: int | None = None
    approved_version: int | None = None
    current_plan_version: int | None = None
    approved_plan_version: int | None = None


@dataclass(frozen=True, kw_only=True)
class ChapterPlan(VersionedRecord):
    object_type: ClassVar[ObjectType] = ObjectType.CHAPTER_PLAN
    chapter_id: UUID
    objective: str
    required_outcome: str
    scene_plans: list[dict] = field(default_factory=list)
    character_progression: dict = field(default_factory=dict)
    plot_progression: dict = field(default_factory=dict)
    information_release: list[str] = field(default_factory=list)
    ending_state: dict = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    locked_dependencies: list[dict] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ChapterVersion(VersionedRecord):
    object_type: ClassVar[ObjectType] = ObjectType.CHAPTER_VERSION
    chapter_id: UUID
    content: str
    change_reason: str
    parent_version_id: UUID | None = None
    status: Status = Status.DRAFT


@dataclass(frozen=True, kw_only=True)
class Lock:
    object_type: ClassVar[ObjectType] = ObjectType.LOCK
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    target_type: ObjectType
    target_id: UUID
    target_version: int
    reason: str
    scope: str = "OBJECT"
    active: bool = True
    locked_by: str
    created_at: datetime = field(default_factory=now)
    released_at: datetime | None = None
    released_by: str | None = None
    release_reason: str | None = None
    previous_status: Status
    previous_authority: Authority


@dataclass(frozen=True, kw_only=True)
class AuditRecord:
    object_type: ClassVar[ObjectType] = ObjectType.AUDIT_RECORD
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    target_type: ObjectType
    target_id: UUID
    target_version: int
    action: AuditAction
    actor_type: ActorType
    actor_id: str
    request_id: str
    reason: str
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=now)
