"""Versioned character tendencies, separate from identity, state and knowledge."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4, uuid5

from novel_os.domain.core import now
from novel_os.domain.enums import ActorType, Authority, Status


@dataclass(frozen=True, kw_only=True)
class CharacterBehaviorProfile:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    character_id: UUID
    version: int
    body: dict
    created_by: str
    source_text: str | None = None
    supersedes_id: UUID | None = None
    status: Status = Status.DRAFT
    source: ActorType = ActorType.USER
    authority_level: Authority = Authority.A7_AI_INFERENCE
    created_at: datetime = field(default_factory=now)
    approved_at: datetime | None = None
    approved_by: str | None = None

    @property
    def logical_id(self):
        # EXTENSION sources distinguish identity and profile for the same character.
        return uuid5(self.character_id, "character-behavior-profile")

    @property
    def profile_id(self):
        return self.logical_id

    @property
    def profile_hash(self):
        value = {
            "profile_id": str(self.logical_id),
            "version": self.version,
            "body": self.body,
        }
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def binding(self):
        return {
            "character_profile_id": str(self.logical_id),
            "character_profile_version": self.version,
            "character_profile_hash": self.profile_hash,
        }
