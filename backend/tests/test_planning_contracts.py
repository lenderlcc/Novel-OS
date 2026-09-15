from copy import deepcopy

import pytest
from pydantic import ValidationError

from novel_os.agents.planning_schemas import (
    Ambiguity,
    ChapterPlanOutput,
    CreativeBriefOutput,
    PlanningAgentResult,
    PlanReviewAgentResult,
    PlanReviewOutput,
    RequirementAgentResult,
)
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.services.planning_results import effective_verdict
from tests.planning_support import fixture_outputs


@pytest.mark.parametrize(
    "model,index",
    [(RequirementAgentResult, 0), (PlanningAgentResult, 1), (PlanReviewAgentResult, 2)],
)
@pytest.mark.parametrize(
    "field,value",
    [
        ("authority_level", "A1_USER_LOCKED"),
        ("approved_at", "2026-01-01"),
        ("version", 8),
        ("system_actor", True),
        ("next_event", "USER_APPROVED"),
    ],
)
def test_business_outputs_reject_server_fields(model, index, field, value):
    body = fixture_outputs()[index]
    body["result"][field] = value
    with pytest.raises(ValidationError):
        model.model_validate(body)


@pytest.mark.parametrize(
    "capability",
    [
        "APPROVE",
        "LOCK",
        "UNLOCK",
        "COMMIT_CANON",
        "SET_WORKFLOW_STATE",
        "CREATE_USER_REQUIREMENT",
        "CREATE_USER_DECISION",
    ],
)
def test_business_proposals_never_grant_authority(capability):
    from uuid import uuid4

    from novel_os.agents.authority import AuthorityValidator
    from novel_os.agents.registry import BUSINESS_STAGE_TASKS, AgentRegistry
    from novel_os.domain.agents import AgentTask
    from novel_os.domain.errors import DomainError

    definition = next(iter(BUSINESS_STAGE_TASKS.values()))
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=definition.state,
        workflow_state_version=1,
        agent_id=definition.agent_id,
        task_type=definition.task_type,
        objective="User intent",
        target_ref=uuid4(),
        capabilities=[definition.capability],
        expected_output_schema=definition.result_schema,
    )
    body = fixture_outputs()[0]
    body["task_id"] = str(task.task_id)
    body["proposed_changes"] = [{"capability": capability, "target_ref": str(task.target_ref)}]
    with pytest.raises((ValidationError, DomainError)):
        result = RequirementAgentResult.model_validate(body)
        AuthorityValidator(AgentRegistry()).validate(task, result)


@pytest.mark.parametrize(
    "impact,confidence,safe,expected",
    [
        ("LOW", 0.1, False, False),
        ("MEDIUM", 0.1, False, False),
        ("HIGH", 0.9, False, False),
        ("HIGH", 0.1, True, False),
        ("HIGH", 0.1, False, True),
        ("HIGH", 0.6, False, False),
    ],
)
def test_ambiguity_decision_threshold(impact, confidence, safe, expected):
    ambiguity = Ambiguity(
        issue="Unclear direction",
        impact=impact,
        confidence=confidence,
        can_safely_infer=safe,
        impact_explanation="Direction may change",
        user_decision_needed="Select intended direction",
    )
    assert ambiguity.requires_decision is expected


@pytest.mark.parametrize(
    "code",
    [
        "MISSING_MUST",
        "FORBIDDEN_VIOLATION",
        "LOCKED_CONFLICT",
        "DIRECTION_CONFLICT",
        "OUTCOME_UNACHIEVABLE",
        "MAJOR_LOGIC_BREAK",
        "REQUIREMENT_MISUNDERSTANDING",
    ],
)
def test_hard_gates_override_pass_and_confidence(code):
    brief, plan, review = fixture_outputs()
    review["result"]["hard_gate_issues"] = [{"code": code, "description": "Concrete hard failure"}]
    review["result"]["confidence"] = 1
    result = effective_verdict(
        PlanReviewOutput.model_validate(review["result"]),
        CreativeBriefOutput.model_validate(brief["result"]),
        ChapterPlanOutput.model_validate(plan["result"]),
    )
    assert result.verdict == "FAIL"
    assert result.hard_gate_issues[0].code == code


@pytest.mark.parametrize(
    "field",
    ["missing_requirements", "forbidden_violations", "locked_conflicts", "direction_conflicts"],
)
def test_structured_hard_evidence_overrides_nominal_pass(field):
    brief, plan, review = fixture_outputs()
    review["result"][field] = ["Explicit conflict"]
    result = effective_verdict(
        PlanReviewOutput.model_validate(review["result"]),
        CreativeBriefOutput.model_validate(brief["result"]),
        ChapterPlanOutput.model_validate(plan["result"]),
    )
    assert result.verdict == "FAIL"


def test_soft_quality_warns_without_false_hard_fail():
    brief, plan, review = fixture_outputs()
    review["result"]["quality_issues"] = ["One scene could have a clearer exit"]
    review["result"]["over_specification_issues"] = ["Leave local pacing to Writer"]
    result = effective_verdict(
        PlanReviewOutput.model_validate(review["result"]),
        CreativeBriefOutput.model_validate(brief["result"]),
        ChapterPlanOutput.model_validate(plan["result"]),
    )
    assert result.verdict == "PASS_WITH_WARNINGS" and not result.hard_gate_issues


@pytest.mark.parametrize("field", ["dialogue", "content", "prose", "sentences"])
def test_scene_schema_cannot_carry_prose_blueprint(field):
    plan = fixture_outputs()[1]["result"]
    plan["scenes"][0][field] = "Full chapter text"
    with pytest.raises(ValidationError):
        ChapterPlanOutput.model_validate(plan)


def test_prompt_and_context_contracts_keep_legacy_profiles():
    contexts = ContextProfileRegistry()
    assert contexts.for_task("MOCK_PLAN").version == 2
    assert contexts.for_task("PLAN_CHAPTER").version == 3
    assert contexts.for_task("PARSE_CHAPTER_REQUIREMENT").profile_id == "CP-003A"
    assert contexts.for_task("REVIEW_CHAPTER_PLAN").profile_id == "CP-004R"
    tasks = TaskDefinitionRegistry()
    for task_type in ["PARSE_CHAPTER_REQUIREMENT", "PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"]:
        definition = tasks.get(task_type)
        modules = definition.resolve(PromptRegistry())
        assert modules and definition.output_schema.model.model_json_schema()
    skills = {ref.module_id for ref in tasks.get("PLAN_CHAPTER").skills}
    assert skills == {"chapter-structure", "creative-exploration", "requirement-alignment"}


def test_missing_coverage_and_required_major_proposals_are_hard_fail():
    brief, plan, review = fixture_outputs()
    plan["result"]["requirement_coverage"] = []
    plan["result"]["proposed_major_changes"] = [
        {
            "description": "Change the world rule",
            "reason": "New direction",
            "affected_scope": "World",
            "required_for_plan": True,
            "disposition": "PROPOSAL_ONLY",
        }
    ]
    result = effective_verdict(
        PlanReviewOutput.model_validate(review["result"]),
        CreativeBriefOutput.model_validate(brief["result"]),
        ChapterPlanOutput.model_validate(plan["result"]),
    )
    assert {i.code for i in result.hard_gate_issues} == {"MISSING_MUST", "DIRECTION_CONFLICT"}


def test_source_quote_is_not_a_license_to_invent_user_constraint():
    brief = deepcopy(fixture_outputs()[0]["result"])
    brief["must"][0]["text"] = "Invent a new major villain"
    with pytest.raises(ValidationError):
        CreativeBriefOutput.model_validate(brief)


@pytest.mark.parametrize(
    "scope,has_evidence,expected",
    [
        ("PLAN_GLOBAL", True, "PASS"),
        ("PLAN_GLOBAL", False, "FAIL"),
        ("SCENE", True, "FAIL"),
    ],
)
def test_global_coverage_requires_plan_evidence_not_a_scene(scope, has_evidence, expected):
    brief, plan, review = fixture_outputs()
    for body in (plan["result"], review["result"]):
        body["requirement_coverage"][0].update(scope=scope, scene_ids=[])
    if not has_evidence:
        plan["result"]["constraints"] = []
    result = effective_verdict(
        PlanReviewOutput.model_validate(review["result"]),
        CreativeBriefOutput.model_validate(brief["result"]),
        ChapterPlanOutput.model_validate(plan["result"]),
    )
    assert result.verdict == expected


@pytest.mark.parametrize("source", ["REQUIREMENT", "DECISION", "CHAPTER_PLAN", "CHAPTER_VERSION"])
def test_lock_policy_covers_every_supported_dependency_and_excludes_review_subject(source):
    from types import SimpleNamespace
    from uuid import uuid4

    from novel_os.domain.context import SourceRef, SourceType
    from novel_os.services.planning_policy import locked_refs, ref_key

    ref = SourceRef(source_type=SourceType(source), logical_id=uuid4(), version=1)
    item = SimpleNamespace(ref=ref, source_type=ref.source_type, locked=True)
    assert locked_refs([item]) == {ref_key(ref)}
    assert locked_refs([item], subject=ref_key(ref)) == set()


def test_profile_requirement_capacity_fits_every_output_contract():
    from novel_os.agents.planning_schemas import REQUIREMENT_FIELDS
    from novel_os.domain.enums import RequirementType

    assert set(REQUIREMENT_FIELDS) == set(RequirementType)
    count = next(
        s.max_items
        for s in ContextProfileRegistry().resolve("CP-003A").selectors
        if s.source_type == "REQUIREMENT"
    )
    brief, plan, review = fixture_outputs()
    source = brief["result"]["must"][0]
    entry = plan["result"]["requirement_coverage"][0]
    brief["result"]["must"] = [{**source, "id": f"M{i}"} for i in range(count)]
    plan["result"]["requirement_coverage"] = [
        {**entry, "constraint_id": f"M{i}"} for i in range(count)
    ]
    review["result"]["requirement_coverage"] = deepcopy(plan["result"]["requirement_coverage"])
    assert (
        effective_verdict(
            PlanReviewOutput.model_validate(review["result"]),
            CreativeBriefOutput.model_validate(brief["result"]),
            ChapterPlanOutput.model_validate(plan["result"]),
        ).verdict
        == "PASS"
    )
