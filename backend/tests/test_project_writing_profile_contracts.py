import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from novel_os.domain.errors import DomainError
from novel_os.domain.writing_profile import WritingPreferences
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry


def test_web_fiction_fixture_is_valid_and_not_a_default():
    path = (
        Path(__file__).resolve().parents[2]
        / "evals/writing/v0.1/case-01/web-fiction-test-profile.json"
    )
    data = json.loads(path.read_text())
    preferences = WritingPreferences.from_payload(data)
    assert preferences.pacing == "MEDIUM_FAST"
    assert preferences.relationship_payoff_visibility == "MEDIUM_HIGH"
    assert preferences.payload() == data
    assert WritingPreferences().target_audience == "" and WritingPreferences().pacing is None
    with pytest.raises(FrozenInstanceError):
        preferences.target_audience = "changed"


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "APPROVED"},
        {"pacing": 0.732},
        {"narrative_density": "FAST"},
        {"guidance": "instruction"},
        {"reading_experience": [" "]},
        {"avoid_tendencies": [123]},
        {"target_audience": "\x00"},
        {"guidance": ["x"] * 31},
    ],
)
def test_preferences_reject_forgery_and_ambiguous_values(payload):
    with pytest.raises(DomainError):
        WritingPreferences.from_payload(payload)


def test_prompt_profiles_do_not_replace_hard_intent_or_naturalness():
    registry = PromptRegistry()
    planner = registry.resolve(ModuleRef(module_id="plan-chapter")).content
    writer = registry.resolve(ModuleRef(module_id="write-chapter")).content
    natural = registry.resolve(ModuleRef(module_id="natural-prose")).content
    for body in (planner, writer):
        for boundary in (
            "A5_USER_PREFERENCE",
            "USER_LOCKED",
            "CANON",
            "MUST",
            "FORBIDDEN",
            "required_outcome",
        ):
            assert boundary in body
        assert "description_density" in body and "relationship_payoff_visibility" in body
        assert "If absent, do not invent a default audience" in body
    assert "Do not over-engineer causal mechanisms" in planner
    assert (
        "Keep authoritative_constraints, review_revision_targets and recommendations separate"
        in planner
    )
    assert "Natural prose does not imply literary prose" in writer
    assert "LOW literary_ornamentation does not permit bad grammar" in natural
    assert "never mandates short sentences" in natural
    assert "cliffhangers" in natural and "爽点" in natural
    for key in ("AS-01", "AS-02", "AS-03", "AS-04", "AS-05", "AS-06", "AS-07", "AS-12"):
        assert key in natural


def test_scheduling_pin_is_not_exposed_as_model_requirement():
    from novel_os.services.writing_profile_context import model_requirements

    directive = json.dumps({"type": "USER_PLANNING_DIRECTIVE", "reason": "keep direction"})
    pin = json.dumps({"type": "PROJECT_WRITING_PROFILE_BINDING", "binding": None})
    assert model_requirements(["actual requirement", directive, pin]) == (
        "actual requirement",
        directive,
    )
