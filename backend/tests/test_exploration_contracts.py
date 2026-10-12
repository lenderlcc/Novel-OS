from copy import deepcopy
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.exploration_schemas import (
    CreativeExplorationOutput,
    ExplorationAgentResult,
    StoryConceptCandidate,
)
from novel_os.domain.enums import Authority
from novel_os.domain.planning import CreativeExploration, ExplorationStatus


def candidate(candidate_id="A"):
    return {
        "id": candidate_id,
        "concept_summary": "A local setback shaped by this character's competing goals.",
        "core_event": "The character's preferred approach fails in the current situation.",
        "conflict_engine": "The character must choose between two immediate goals.",
        "character_pressure": "Their established caution becomes a local disadvantage.",
        "story_progression": "Their cooperation becomes deliberate without changing the main plot.",
        "reader_interest": "The choice reveals what the character values.",
        "continuity_fit": "Preserves the supplied facts and current relationship.",
        "requirement_fit": "The setback is small, unexpected and recoverable.",
        "creative_freedom_fit": "Only a local conflict within the granted freedom.",
        "audience_fit": "Matches the approved reading experience.",
        "execution_feasibility": "Can fit within the chapter without requiring future information.",
        "required_new_elements": ["One transient local obstacle."],
        "major_change_risk": "LOW",
        "major_change_reason": "No new world rule, major fact or direction.",
        "similarity_risk": "LOW",
        "similarity_reason": "A different character choice from the supplied recent mechanisms.",
        "authority_fit": "WITHIN_BOUNDS",
        "authority_reason": "Uses the existing characters without altering locked decisions.",
        "strengths": ["Character-specific pressure."],
        "risks": ["The local choice must stay proportionate."],
    }


def exploration():
    second = candidate("B")
    second.update(
        core_event="A time window changes before the character can act.",
        conflict_engine="External timing conflicts with the character's careful method.",
        character_pressure="They must accept imperfect information to help their partner.",
    )
    return {
        "kind": "creative_exploration",
        "brief_id": str(uuid4()),
        "mode": "DIVERGENT",
        "focused_reason": None,
        "candidates": [candidate(), second],
        "selected_candidate_id": "A",
        "selection_reason": "A best uses the character's current competing goals safely.",
        "rejected_reasons": [
            {"candidate_id": "B", "code": "WEAKER_STORY_FIT", "reason": "Less character-specific."}
        ],
        "source_refs": [
            {"source_type": "CREATIVE_BRIEF", "logical_id": str(uuid4()), "version": 1}
        ],
        "blocked_reason": None,
    }


def envelope(body=None):
    return {
        "task_id": str(uuid4()),
        "status": "SUCCESS",
        "result": body or exploration(),
        "confidence": 0.8,
        "assumptions": [],
        "issues": [],
        "proposed_changes": [],
        "memory_proposals": [],
        "escalation": None,
    }


def test_valid_candidate_and_exploration_use_qualitative_diagnostics():
    assert StoryConceptCandidate.model_validate(candidate()).major_change_risk == "LOW"
    result = ExplorationAgentResult.model_validate(envelope())
    assert result.result.selected_candidate_id == "A"
    schema = CreativeExplorationOutput.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "creativity_score" not in schema["properties"]


@pytest.mark.parametrize("selected", ["UNKNOWN", ""])
def test_selected_candidate_must_exist(selected):
    body = exploration()
    body["selected_candidate_id"] = selected
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "selected"])
def test_rejections_partition_the_unselected_candidates(mutation):
    body = exploration()
    if mutation == "missing":
        body["rejected_reasons"] = []
    elif mutation == "duplicate":
        body["rejected_reasons"] *= 2
    else:
        body["rejected_reasons"][0]["candidate_id"] = "UNKNOWN" if mutation == "unknown" else "A"
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("major_change_risk", "HIGH"),
        ("authority_fit", "REQUIRES_MAJOR_CHANGE"),
        ("authority_fit", "VIOLATES_LOCK_OR_CANON"),
    ],
)
def test_selected_concept_cannot_override_major_direction_lock_or_canon(field, value):
    body = exploration()
    body["candidates"][0][field] = value
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)


@pytest.mark.parametrize("authority", ["WITHIN_BOUNDS", "VIOLATES_LOCK_OR_CANON"])
def test_major_change_candidate_remains_rejected_diagnostic(authority):
    body = exploration()
    body["candidates"][1]["major_change_risk"] = "HIGH"
    body["candidates"][1]["authority_fit"] = authority
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)
    body["rejected_reasons"][0]["code"] = "REQUIRES_MAJOR_CHANGE"
    result = CreativeExplorationOutput.model_validate(body)
    assert result.selected_candidate_id == "A"


def test_all_unsafe_candidates_block_without_human_gate_or_proposal():
    body = exploration()
    for item in body["candidates"]:
        item["major_change_risk"] = "HIGH"
        item["authority_fit"] = "REQUIRES_MAJOR_CHANGE"
    body["selected_candidate_id"] = None
    body["blocked_reason"] = "NEEDS_REPLAN_CONTEXT: every concept needs a major direction change."
    body["rejected_reasons"] = [
        {"candidate_id": item["id"], "code": "REQUIRES_MAJOR_CHANGE", "reason": "Outside scope."}
        for item in body["candidates"]
    ]
    result = envelope(body)
    result["status"] = "BLOCKED"
    parsed = ExplorationAgentResult.model_validate(result)
    assert parsed.result.selected_candidate_id is None and parsed.proposed_changes == []
    result["status"] = "SUCCESS"
    with pytest.raises(ValidationError):
        ExplorationAgentResult.model_validate(result)


@pytest.mark.parametrize("mode", ["FOCUSED", "DIVERGENT"])
def test_mode_has_consistent_concept_count_and_reason(mode):
    body = exploration()
    body.update(mode=mode, candidates=[body["candidates"][0]], rejected_reasons=[])
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)
    body.update(mode="FOCUSED", focused_reason="The user already specifies the event and conflict.")
    assert len(CreativeExplorationOutput.model_validate(body).candidates) == 1


def test_source_refs_required_unique_and_exactly_versioned():
    body = exploration()
    for refs in ([], body["source_refs"] * 2, [{**body["source_refs"][0], "version": 0}]):
        invalid = {**body, "source_refs": refs}
        with pytest.raises(ValidationError):
            CreativeExplorationOutput.model_validate(invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("authority_level", "A4_APPROVED_PLAN"),
        ("status", "APPROVED"),
        ("approved_at", "2026-10-05"),
        ("system_actor", True),
        ("version", 2),
    ],
)
def test_provider_cannot_forge_server_authority_or_lifecycle(field, value):
    body = exploration()
    body[field] = value
    with pytest.raises(ValidationError):
        CreativeExplorationOutput.model_validate(body)


@pytest.mark.parametrize("field", ["proposed_changes", "memory_proposals"])
def test_exploration_is_not_a_plan_or_memory_proposal_channel(field):
    result = envelope()
    result[field] = [{"capability": "PROPOSE_PLAN", "target_ref": str(uuid4())}]
    with pytest.raises(ValidationError):
        ExplorationAgentResult.model_validate(result)


@pytest.mark.parametrize("field", ["scenes", "creativity_score", "novelty_score"])
def test_candidate_contract_excludes_plan_scenes_and_numeric_scores(field):
    body = candidate()
    body[field] = [] if field == "scenes" else 90
    with pytest.raises(ValidationError):
        StoryConceptCandidate.model_validate(body)


def test_entity_identity_and_status_are_frozen_and_authority_remains_a7():
    item = CreativeExploration(
        project_id=uuid4(),
        chapter_id=uuid4(),
        workflow_id=uuid4(),
        brief_id=uuid4(),
        agent_run_id=uuid4(),
        prompt_lineage_id=uuid4(),
        context_package_id=uuid4(),
        source_versions=[],
        body=deepcopy(exploration()),
        status=ExplorationStatus.READY,
    )
    assert item.authority_level == Authority.A7_AI_INFERENCE
    with pytest.raises(FrozenInstanceError):
        item.status = "APPROVED"


def planning_prompt(schema="chapter-planning-result.v4", payload=None):
    from novel_os.agents.provider import MockModelProvider
    from novel_os.domain.agents import AgentId, Capability
    from novel_os.prompts.runtime import PromptRuntime

    # Compilation only: this helper never invokes the provider or writes persistence.
    return PromptRuntime(MockModelProvider()).prepare(
        task_id=uuid4(),
        task_type="PLAN_CHAPTER",
        agent_id=AgentId.A03_PLANNING,
        attempt=1,
        target_ref=uuid4(),
        output_kind="chapter_plan",
        capabilities=[Capability.PROPOSE_PLAN],
        constraints=[],
        expected_output_schema=schema,
        context_payload=payload or {},
    )


def prompt_pins(request):
    return {module.module.module_id: module.module.version for module in request.prompt.modules}


def test_historical_planning_schema_retains_its_original_template():
    request = planning_prompt(
        "chapter-planning-result.v1", {"profile": {"id": "CP-004", "version": 6}}
    )
    assert request.prompt.output.version == 1
    assert prompt_pins(request)["plan-chapter"] == 5


def test_planning_skeleton_reserves_the_larger_current_prompt_modules():
    from novel_os.providers.tokens import prompt_overhead

    skeleton = planning_prompt()
    current = planning_prompt(payload={"profile": {"id": "CP-004", "version": 9}})
    previous = planning_prompt(
        "chapter-planning-result.v2", payload={"profile": {"id": "CP-004", "version": 6}}
    )
    assert prompt_pins(skeleton) == prompt_pins(current)
    assert prompt_pins(current)["plan-chapter"] == 12
    assert prompt_pins(current)["creative-exploration"] == 2
    assert prompt_pins(previous)["plan-chapter"] == 6
    assert prompt_pins(previous)["creative-exploration"] == 1
    assert prompt_overhead(skeleton) > prompt_overhead(previous)


def test_other_context_profile_versions_cannot_select_exploration_planning_prompt():
    request = planning_prompt(
        "chapter-planning-result.v2", payload={"profile": {"id": "CP-OTHER", "version": 7}}
    )
    assert prompt_pins(request)["plan-chapter"] == 6
