"""Shared input and interpretation contract for sparse character tendencies."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProfileText = Annotated[str, Field(min_length=1, max_length=2000)]
ProfileNotes = Annotated[list[ProfileText], Field(max_length=30)]


class RiskTolerance(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProfileContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def clean_text(cls, value):
        items = value if isinstance(value, list) else [value]
        if any(isinstance(item, str) and (not item.strip() or "\x00" in item) for item in items):
            raise ValueError("Profile text must be nonblank and contain no null bytes")
        return value


class RelationshipModifier(ProfileContract):
    other_character_id: UUID
    interaction_tendency: ProfileText | None = None
    trust_expression: ProfileText | None = None
    conflict_pattern: ProfileText | None = None
    things_left_unsaid: ProfileNotes = Field(default_factory=list)
    guidance: ProfileNotes = Field(default_factory=list)


class CharacterBehaviorProfileBody(ProfileContract):
    decision_tendency: ProfileText | None = None
    risk_tolerance: RiskTolerance | None = None
    conflict_response: ProfileText | None = None
    emotional_defense: ProfileText | None = None
    communication_style: ProfileText | None = None
    attention_bias: ProfileText | None = None
    self_image: ProfileText | None = None
    vulnerability: ProfileText | None = None
    default_assumptions: ProfileNotes = Field(default_factory=list)
    avoids_saying_directly: ProfileNotes = Field(default_factory=list)
    behavioral_tells: ProfileNotes = Field(default_factory=list)
    relationship_modifiers: list[RelationshipModifier] = Field(default_factory=list, max_length=30)
    guidance: ProfileNotes = Field(default_factory=list)
    avoid_tendencies: ProfileNotes = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_relationships(self):
        ids = [modifier.other_character_id for modifier in self.relationship_modifiers]
        if len(ids) != len(set(ids)):
            raise ValueError("Use one relationship modifier per other character")
        return self
