import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from novel_os.api.writing_profile_schemas import WritingPreferencesInput
from novel_os.domain.errors import DomainError
from novel_os.domain.writing_profile import (
    NarrativePerspective,
    ProjectWritingProfile,
    WritingPreferences,
)
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry


@pytest.mark.parametrize("perspective", list(NarrativePerspective))
def test_perspective_roundtrips_domain_and_api(perspective):
    body = {"narrative_perspective": perspective.value}
    preferences = WritingPreferences.from_payload(body)
    assert preferences.narrative_perspective is perspective
    assert preferences.payload()["narrative_perspective"] == perspective.value
    assert WritingPreferencesInput(**body).narrative_perspective is perspective


@pytest.mark.parametrize("invalid", ["SECOND_PERSON", "THIRD_PERSON_LIMITED", "", 1, [], True])
def test_invalid_perspective_rejected_by_domain_and_api(invalid):
    with pytest.raises(DomainError):
        WritingPreferences.from_payload({"narrative_perspective": invalid})
    with pytest.raises(ValidationError):
        WritingPreferencesInput(narrative_perspective=invalid)


def test_legacy_payload_and_hash_do_not_change_when_new_field_is_absent_or_null():
    path = Path(__file__).resolve().parents[2] / "evals/writing/v0.1/case-01"
    legacy = json.loads((path / "web-fiction-test-profile.json").read_text())
    project_id = UUID("23c028ee-cd94-4965-af85-731e560c9633")
    original_hash = hashlib.sha256(
        json.dumps(
            {"profile_id": str(project_id), "version": 1, "preferences": legacy},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    for body in (legacy, {**legacy, "narrative_perspective": None}):
        profile = ProjectWritingProfile(
            project_id=project_id,
            version=1,
            created_by="user",
            preferences=WritingPreferences.from_payload(body),
        )
        assert profile.preferences.narrative_perspective is None
        assert profile.preferences.payload() == legacy
        assert profile.profile_hash == original_hash
        changed = replace(
            profile,
            preferences=WritingPreferences.from_payload(
                {**legacy, "narrative_perspective": "THIRD_PERSON"}
            ),
        )
        assert changed.profile_hash != original_hash


def test_writer_prompt_is_additive_versioned_and_does_not_ban_dialogue_pronouns():
    registry = PromptRegistry()
    old = registry.resolve(ModuleRef(module_id="write-chapter", version=3))
    current = registry.resolve(ModuleRef(module_id="write-chapter"))
    assert current.module.version == 6
    assert current.content.startswith(old.content)
    assert "Narrative perspective (STYLE-002)" not in old.content
    for instruction in (
        "THIRD_PERSON",
        "FIRST_PERSON",
        "exact approved",
        "A5_USER_PREFERENCE",
        "我不知道。",
        "你先走。",
        "absent/null",
        "MUST/FORBIDDEN",
    ):
        assert instruction in current.content
