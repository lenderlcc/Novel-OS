from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from novel_os.domain.core import MAX_CHAPTER_SEQUENCE
from novel_os.domain.enums import (
    ActorType,
    AuditAction,
    Authority,
    ObjectType,
    RequirementType,
    ScopeType,
    Status,
)

PositiveVersion = Annotated[int, Field(strict=True, ge=1)]
TextValue = Annotated[str, Field(min_length=1)]
TagsValue = Annotated[list[str], Field(max_length=100)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetadataInput(Input):
    tags: TagsValue = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ReferenceInput(Input):
    object_type: Literal[
        ObjectType.PROJECT,
        ObjectType.REQUIREMENT,
        ObjectType.DECISION,
        ObjectType.CHAPTER,
        ObjectType.CHAPTER_PLAN,
        ObjectType.CHAPTER_VERSION,
    ]
    object_id: UUID


class VersionCommand(Input):
    expected_version: PositiveVersion
    reason: TextValue = "User request"


class ProjectInput(MetadataInput):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str = ""


class ProjectUpdate(VersionCommand):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    tags: TagsValue | None = None
    metadata: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Project fields cannot be null")
        return self


class RequirementInput(MetadataInput):
    content: TextValue
    requirement_type: RequirementType = RequirementType.MUST
    scope_type: ScopeType = ScopeType.PROJECT
    scope_id: UUID | None = None
    priority: Annotated[int, Field(strict=True, ge=1, le=5)] = 1
    persistent: bool = False
    effective_from: AwareDatetime | None = None
    effective_until: AwareDatetime | None = None


class RequirementRevision(RequirementInput, VersionCommand):
    pass


class DecisionInput(MetadataInput):
    question: TextValue
    decision: TextValue
    rationale: str = ""
    affected_objects: list[ReferenceInput] = Field(default_factory=list)


class DecisionRevision(DecisionInput, VersionCommand):
    pass


class ChapterInput(MetadataInput):
    sequence: Annotated[int, Field(strict=True, ge=1, le=MAX_CHAPTER_SEQUENCE)]
    title: Annotated[str, Field(min_length=1, max_length=300)]


class PlanInput(MetadataInput):
    objective: TextValue
    required_outcome: TextValue
    scene_plans: list[dict[str, JsonValue]] = Field(default_factory=list)
    character_progression: dict[str, JsonValue] = Field(default_factory=dict)
    plot_progression: dict[str, JsonValue] = Field(default_factory=dict)
    information_release: list[str] = Field(default_factory=list)
    ending_state: dict[str, JsonValue] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    locked_dependencies: list[ReferenceInput] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PlanCreate(PlanInput):
    expected_version: Annotated[int, Field(strict=True, ge=0)]
    reason: TextValue = "Create plan version"


class ChapterVersionInput(MetadataInput):
    content: TextValue
    change_reason: TextValue


class ChapterVersionCreate(ChapterVersionInput):
    expected_version: Annotated[int, Field(strict=True, ge=0)]


class LockInput(VersionCommand):
    target_type: Literal[
        ObjectType.PROJECT,
        ObjectType.REQUIREMENT,
        ObjectType.DECISION,
        ObjectType.CHAPTER,
        ObjectType.CHAPTER_PLAN,
        ObjectType.CHAPTER_VERSION,
    ]
    target_id: UUID
    scope: Literal["OBJECT"] = "OBJECT"


class RecordView(BaseModel):
    id: UUID
    project_id: UUID
    object_type: ObjectType
    version: int
    status: Status
    source: ActorType
    authority_level: Authority
    locked: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    tags: list[str]
    metadata: dict


class VersionView(RecordView):
    logical_id: UUID
    supersedes_id: UUID | None


class ProjectView(ProjectInput, RecordView):
    pass


class RequirementView(RequirementInput, VersionView):
    scope_id: UUID


class DecisionView(DecisionInput, VersionView):
    pass


class ChapterView(ChapterInput, RecordView):
    current_version: int | None
    approved_version: int | None
    current_plan_version: int | None
    approved_plan_version: int | None


class PlanView(PlanInput, VersionView):
    chapter_id: UUID


class ChapterVersionView(ChapterVersionInput, VersionView):
    chapter_id: UUID
    parent_version_id: UUID | None


class LockView(BaseModel):
    id: UUID
    project_id: UUID
    object_type: ObjectType
    target_type: ObjectType
    target_id: UUID
    target_version: int
    reason: str
    scope: str
    active: bool
    locked_by: str
    created_at: datetime
    released_at: datetime | None
    released_by: str | None
    release_reason: str | None
    previous_status: Status
    previous_authority: Authority


class AuditView(BaseModel):
    id: UUID
    project_id: UUID
    object_type: ObjectType
    target_type: ObjectType
    target_id: UUID
    target_version: int
    action: AuditAction
    actor_type: ActorType
    actor_id: str
    request_id: str
    reason: str
    before: dict
    after: dict
    created_at: datetime


def view(entity) -> dict:
    # Convert a domain snapshot, never a live SQLAlchemy model.
    return {**asdict(entity), "object_type": entity.object_type}


def payload(command: Input) -> dict:
    return command.model_dump(exclude_unset=True, exclude={"expected_version", "reason"})
