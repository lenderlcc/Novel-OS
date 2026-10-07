from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from novel_os.api.core_schemas import Input, PositiveVersion
from novel_os.characters.schemas import CharacterBehaviorProfileBody, ProfileText
from novel_os.domain.enums import Status

CharacterName = Annotated[str, Field(min_length=1, max_length=200)]


class CharacterSubjectInput(Input):
    name: CharacterName
    aliases: list[CharacterName] = Field(default_factory=list, max_length=10)
    reason: ProfileText = "Create character identity"

    @field_validator("name", "aliases", "reason")
    @classmethod
    def clean_text(cls, value):
        items = value if isinstance(value, list) else [value]
        if any(not item.strip() or "\x00" in item for item in items):
            raise ValueError("Invalid character text")
        return value


class CharacterSubjectView(Input):
    id: UUID
    project_id: UUID
    name: str
    normalized_name: str
    kind: Literal["CHARACTER"]
    aliases: list[str]
    batch_id: UUID | None
    created_at: datetime
    created_by: str


class CharacterProfileCommand(Input):
    reason: ProfileText

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Invalid character profile reason")
        return value


class CharacterProfileCreate(CharacterProfileCommand):
    expected_version: int = Field(strict=True, ge=0)
    profile: CharacterBehaviorProfileBody
    reason: ProfileText = "Save character behavior profile"


class CharacterProfileApprove(CharacterProfileCommand):
    expected_version: PositiveVersion
    reason: ProfileText = "Approve character behavior profile"


class CharacterProfileInterpret(Input):
    expected_version: int = Field(strict=True, ge=0)
    text: Annotated[str, Field(min_length=1, max_length=10000)]

    @field_validator("text")
    @classmethod
    def clean_text(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Invalid character description")
        return value


class CharacterProfileView(CharacterBehaviorProfileBody):
    id: UUID
    logical_id: UUID
    profile_id: UUID
    project_id: UUID
    character_id: UUID
    version: int
    status: Literal[Status.DRAFT, Status.APPROVED, Status.SUPERSEDED]
    authority_level: Literal["A7_AI_INFERENCE", "A3_CANON"]
    source: Literal["USER"]
    profile_hash: str
    supersedes_id: UUID | None
    source_text: str | None
    created_at: datetime
    created_by: str
    approved_at: datetime | None
    approved_by: str | None


class CharacterProfileState(Input):
    current_profile_version: int | None
    approved_profile_version: int | None
    current: CharacterProfileView | None
    approved: CharacterProfileView | None


def subject_view(record):
    return CharacterSubjectView(**asdict(record))


def view(record):
    if record is None:
        return None
    values = asdict(record)
    body = values.pop("body")
    return CharacterProfileView(
        **body,
        **values,
        logical_id=record.logical_id,
        profile_id=record.profile_id,
        profile_hash=record.profile_hash,
    )
