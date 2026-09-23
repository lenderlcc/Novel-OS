"""Project reading preferences. Approval never promotes preference authority."""

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now
from novel_os.domain.enums import ActorType, Authority, Status
from novel_os.domain.errors import DomainError


class Intensity(StrEnum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    LOW_MEDIUM = "LOW_MEDIUM"
    MEDIUM = "MEDIUM"
    MEDIUM_HIGH = "MEDIUM_HIGH"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class Pacing(StrEnum):
    VERY_SLOW = "VERY_SLOW"
    SLOW = "SLOW"
    MEDIUM_SLOW = "MEDIUM_SLOW"
    MEDIUM = "MEDIUM"
    MEDIUM_FAST = "MEDIUM_FAST"
    FAST = "FAST"
    VERY_FAST = "VERY_FAST"


class NarrativePerspective(StrEnum):
    FIRST_PERSON = "FIRST_PERSON"
    THIRD_PERSON = "THIRD_PERSON"


PREFERENCE_ENUMS = {"pacing": Pacing, "narrative_perspective": NarrativePerspective}


@dataclass(frozen=True, kw_only=True)
class WritingPreferences:
    target_audience: str = ""
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
    reading_experience: tuple[str, ...] = ()
    guidance: tuple[str, ...] = ()
    avoid_tendencies: tuple[str, ...] = ()

    def __post_init__(self):
        for entry in fields(self):
            value = getattr(self, entry.name)
            if entry.name == "target_audience":
                valid = isinstance(value, str) and len(value) <= 1000 and "\x00" not in value
            elif entry.name in {"reading_experience", "guidance", "avoid_tendencies"}:
                valid = (
                    isinstance(value, tuple)
                    and len(value) <= 30
                    and all(
                        isinstance(item, str)
                        and 0 < len(item.strip()) <= 2000
                        and "\x00" not in item
                        for item in value
                    )
                )
            else:
                enum = PREFERENCE_ENUMS.get(entry.name, Intensity)
                valid = value is None or isinstance(value, enum)
            if not valid:
                raise DomainError("VALIDATION_ERROR", "Invalid writing preference dimension")

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, dict) or payload.keys() - {f.name for f in fields(cls)}:
            raise DomainError("VALIDATION_ERROR", "Unexpected writing preference fields")
        values = dict(payload)
        try:
            for key, value in values.items():
                if key in {"reading_experience", "guidance", "avoid_tendencies"}:
                    if not isinstance(value, (list, tuple)):
                        raise ValueError
                    values[key] = tuple(value)
                elif key != "target_audience" and value is not None:
                    values[key] = PREFERENCE_ENUMS.get(key, Intensity)(value)
            return cls(**values)
        except (ValueError, TypeError):
            raise DomainError("VALIDATION_ERROR", "Invalid writing preferences") from None

    def payload(self):
        payload = asdict(self)
        # Omitted/null perspective preserves historical hashes and context snapshots.
        # A new, explicitly selected perspective participates in the normal version hash.
        if self.narrative_perspective is None:
            payload.pop("narrative_perspective")
        return json.loads(json.dumps(payload, ensure_ascii=False))


@dataclass(frozen=True, kw_only=True)
class ProjectWritingProfile:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    version: int
    preferences: WritingPreferences
    created_by: str
    status: Status = Status.DRAFT
    source: ActorType = ActorType.USER
    authority_level: Authority = Authority.A5_USER_PREFERENCE
    created_at: datetime = field(default_factory=now)
    approved_at: datetime | None = None
    approved_by: str | None = None

    @property
    def profile_id(self):
        # One logical profile per Project; every immutable version has its own row ID.
        return self.project_id

    @property
    def profile_hash(self):
        value = {
            "profile_id": str(self.profile_id),
            "version": self.version,
            "preferences": self.preferences.payload(),
        }
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def binding(self):
        return {
            "writing_profile_id": str(self.profile_id),
            "writing_profile_version": self.version,
            "writing_profile_hash": self.profile_hash,
        }
