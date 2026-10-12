"""Offline output/route contracts; no model calls or claims of prose-quality improvement."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.planning_schemas import PlanningAgentResultV4
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.services.context import ContextService
from tests.planning_support import fixture_outputs


def clarification(body=None):
    body = deepcopy(body or fixture_outputs()[1])
    refs = body["result"]["source_refs"]
    body.update(
        status="NEEDS_HUMAN",
        escalation={"required": True, "reason": "An explicit POV owner needs clarification"},
        proposed_changes=[],
        result={
            "kind": "planning_clarification",
            "unresolved_ambiguities": [
                {
                    "issue": "The required limited POV character has no supplied identity",
                    "impact": "HIGH",
                    "confidence": 0.3,
                    "can_safely_infer": False,
                    "impact_explanation": (
                        "Choosing an owner changes the chapter knowledge boundary"
                    ),
                    "user_decision_needed": "Identify the existing intended POV owner",
                }
            ],
            "source_refs": refs,
        },
    )
    return body


def test_current_planning_contract_accepts_only_a_plan_or_typed_consequential_clarification():
    executable = PlanningAgentResultV4.model_validate(fixture_outputs()[1])
    stopped = PlanningAgentResultV4.model_validate(clarification())
    assert executable.result.kind == "chapter_plan" and executable.status == "SUCCESS"
    assert stopped.result.kind == "planning_clarification" and stopped.status == "NEEDS_HUMAN"
    assert stopped.result.unresolved_ambiguities[0].requires_decision
    assert not stopped.proposed_changes and not stopped.memory_proposals
    assert not hasattr(stopped.result, "scenes")


@pytest.mark.parametrize(
    "mutation",
    [
        "success_status",
        "missing_escalation",
        "not_required",
        "blank_reason",
        "low_impact",
        "high_confidence",
        "safe_inference",
        "no_question",
        "no_source",
        "proposal",
        "executable_fields",
    ],
)
def test_clarification_cannot_hide_an_executable_plan_or_escalate_safe_missing_material(mutation):
    body = clarification()
    ambiguity = body["result"]["unresolved_ambiguities"][0]
    if mutation == "success_status":
        body["status"] = "SUCCESS"
    elif mutation == "missing_escalation":
        body["escalation"] = None
    elif mutation == "not_required":
        body["escalation"]["required"] = False
    elif mutation == "blank_reason":
        body["escalation"]["reason"] = "  "
    elif mutation == "low_impact":
        ambiguity["impact"] = "LOW"
    elif mutation == "high_confidence":
        ambiguity["confidence"] = 0.6
    elif mutation == "safe_inference":
        ambiguity["can_safely_infer"] = True
    elif mutation == "no_question":
        body["result"]["unresolved_ambiguities"] = []
    elif mutation == "no_source":
        body["result"]["source_refs"] = []
    elif mutation == "proposal":
        body["proposed_changes"] = [{"capability": "PROPOSE_PLAN", "target_ref": str(uuid4())}]
    else:
        body["result"]["scenes"] = fixture_outputs()[1]["result"]["scenes"]
    with pytest.raises(ValidationError):
        PlanningAgentResultV4.model_validate(body)


@pytest.mark.parametrize("status", ["NEEDS_HUMAN", "BLOCKED", "FAILED"])
def test_v4_plan_cannot_be_returned_with_non_executable_disposition(status):
    body = fixture_outputs()[1]
    body["status"] = status
    with pytest.raises(ValidationError):
        PlanningAgentResultV4.model_validate(body)


def test_saved_v3_contract_and_legacy_context_profiles_remain_exact():
    definition = TaskDefinitionRegistry().get("PLAN_CHAPTER", "chapter-planning-result.v3")
    assert definition.output_schema.schema_hash == (
        "4a2b40d261663f69b49ccb8f3193e2ec848a31b4b449ee092b3414133b0d9687"
    )
    assert definition.task_template.version == 11
    definition.output_schema.model.model_validate(fixture_outputs()[1])
    with pytest.raises(ValidationError):
        definition.output_schema.model.model_validate(clarification())
    profiles = ContextProfileRegistry()
    for profile_id, version, expected_hash in [
        ("CP-004", 9, "f169d020396a1a1db177748f3183cfb962e9aa47cc9455aa7b13a8fe04e2b3a9"),
        ("CP-004R", 4, "6edeaf15fbc05818a11862f6c665554152463124bb58fff2512cbc15c5169af4"),
    ]:
        assert profiles.resolve(profile_id, version).profile_hash == expected_hash


@pytest.mark.parametrize(
    "exploration,schema,expected",
    [(True, 4, 10), (True, 3, 9), (True, 2, 9), (True, 1, 9), (False, 4, 8), (False, 3, 8)],
)
def test_context_selection_keeps_saved_planning_schema_on_its_previous_profile(
    monkeypatch, exploration, schema, expected
):
    from novel_os.repositories import workflows
    from novel_os.services import exploration_policy

    monkeypatch.setattr(
        workflows, "WorkflowRepository", lambda _: SimpleNamespace(get=lambda _: object())
    )
    monkeypatch.setattr(exploration_policy, "supports_exploration", lambda _: exploration)
    task = SimpleNamespace(
        task_type="PLAN_CHAPTER",
        workflow_instance_id=uuid4(),
        expected_output_schema=f"chapter-planning-result.v{schema}",
    )
    assert ContextService(None).task_profile(task).version == expected


@pytest.mark.parametrize("profile_id,version", [("CP-004", 10), ("CP-004R", 5)])
def test_current_history_is_optional_at_first_chapter_but_mandatory_if_available(
    profile_id, version
):
    selector = next(
        s
        for s in ContextProfileRegistry().resolve(profile_id, version).selectors
        if s.selector_id == "previous-approved-chapter"
    )
    assert selector.priority == "P0" and not selector.required
    assert selector.version_policy == "APPROVED" and selector.scope == "PREVIOUS_CHAPTER"


@pytest.mark.parametrize("profile_id,version", [("CP-004", 10), ("CP-004R", 5)])
def test_prior_prose_overflow_blocks_instead_of_silently_omitting_the_comparison_baseline(
    profile_id, version
):
    from novel_os.context.engine import ContextEngine
    from novel_os.domain.context import CandidateBatch, ContextRequest, SourceType
    from novel_os.prompts.contracts import canonical
    from tests.context.test_context import item

    profile = ContextProfileRegistry().resolve(profile_id, version)
    selector = next(s for s in profile.selectors if s.selector_id == "previous-approved-chapter")
    profile = profile.model_copy(update={"selectors": (selector,), "token_budget": 100})
    request = ContextRequest(
        project_id=uuid4(),
        task_id=uuid4(),
        task_type=profile.allowed_task_types[0],
        chapter_id=uuid4(),
        chapter_sequence=2,
    )
    history = item(
        request,
        selector_id=selector.selector_id,
        source_type=SourceType.CHAPTER_VERSION,
        chapter_id=uuid4(),
        chapter_sequence=1,
        payload_json=canonical({"content": "Accepted prose " * 500}),
    )
    built = ContextEngine(estimator=SimpleNamespace(estimate=len)).build(
        request, profile, CandidateBatch(items=(history,))
    )
    assert built.status == "BLOCKED" and built.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert built.package.items[0].source_id == history.source_id
    assert not any(i.reason == "TOKEN_BUDGET" for i in built.package.excluded_items)
