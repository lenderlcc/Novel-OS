from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from novel_os.api.core_schemas import Input, PositiveVersion
from novel_os.domain.enums import Status
from novel_os.domain.writing_profile import Intensity, NarrativePerspective, Pacing

ProfileText = Annotated[str, Field(min_length=1, max_length=2000)]
ProfileNotes = Annotated[list[ProfileText], Field(max_length=30)]


class WritingPreferencesInput(Input):
    target_audience: str = Field(default="", max_length=1000)
    narrative_perspective: NarrativePerspective | None = None
    pacing: Pacing | None = None
    narrative_density: Intensity | None = None
    description_density: Intensity | None = None
    dialogue_density: Intensity | None = None
    emotional_explicitness: Intensity | None = None
    subtext_level: Intensity | None = None
    literary_ornamentation: Intensity | None = None
    scene_hook_strength: Intensity | None = None
    chapter_ending_hook: Intensity | None = None
    relationship_payoff_visibility: Intensity | None = None
    exposition_density: Intensity | None = None
    naturalness: Intensity | None = None
    reading_experience: ProfileNotes = Field(default_factory=list)
    guidance: ProfileNotes = Field(default_factory=list)
    avoid_tendencies: ProfileNotes = Field(default_factory=list)

    @field_validator("target_audience", "reading_experience", "guidance", "avoid_tendencies")
    @classmethod
    def clean_text(cls, value):
        items = [value] if isinstance(value, str) else value
        if any("\x00" in item for item in items) or (
            isinstance(value, list) and any(not item.strip() for item in items)
        ):
            raise ValueError("Invalid preference text")
        return value


class WritingProfileCreate(Input):
    expected_version: int = Field(strict=True, ge=0)
    preferences: WritingPreferencesInput
    reason: ProfileText = "Save project writing preferences"


class WritingProfileApprove(Input):
    expected_version: PositiveVersion
    reason: ProfileText = "Approve project writing preferences"


class WritingProfileView(WritingPreferencesInput):
    id: UUID
    profile_id: UUID
    project_id: UUID
    version: int
    status: Literal[Status.DRAFT, Status.APPROVED, Status.SUPERSEDED]
    authority_level: Literal["A5_USER_PREFERENCE"]
    source: Literal["USER"]
    profile_hash: str
    created_at: datetime
    created_by: str
    approved_at: datetime | None
    approved_by: str | None


class WritingProfileState(Input):
    current_profile_version: int | None
    approved_profile_version: int | None
    current: WritingProfileView | None
    approved: WritingProfileView | None


def view(record):
    if record is None:
        return None
    values = {
        name: getattr(record, name)
        for name in (
            "id",
            "profile_id",
            "project_id",
            "version",
            "status",
            "authority_level",
            "source",
            "profile_hash",
            "created_at",
            "created_by",
            "approved_at",
            "approved_by",
        )
    }
    return WritingProfileView(**record.preferences.payload(), **values)
