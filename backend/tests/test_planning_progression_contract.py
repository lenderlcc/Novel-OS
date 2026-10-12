"""Offline routing and authority regressions, not a model prose-quality evaluation."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.planning_schemas import (
    ChapterPlanOutput,
    CreativeBriefOutput,
    PlanReviewOutput,
)
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.runtime import PromptRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.services.plan_review_policy import (
    canonical_plan_constraints,
    effective_verdict,
    review_feedback,
)
from tests.planning_support import fixture_outputs


@pytest.mark.parametrize(
    "task_type,schema,profile_id,profile_version,template_version",
    [
        ("PLAN_CHAPTER", None, "CP-004", 8, 12),
        ("REVIEW_CHAPTER_PLAN", None, "CP-004R", 5, 7),
        ("PLAN_CHAPTER", "chapter-planning-result.v1", "CP-004", 6, 5),
        ("PLAN_CHAPTER", "chapter-planning-result.v3", "CP-004", 9, 11),
        ("REVIEW_CHAPTER_PLAN", "chapter-plan-review-result.v2", "CP-004R", 4, 5),
    ],
)
def test_new_planning_guidance_is_compiled_without_rebinding_historical_tasks(
    task_type, schema, profile_id, profile_version, template_version
):
    tasks = TaskDefinitionRegistry()
    definition = tasks.get(task_type, schema)
    prepared = PromptRuntime(None, tasks=tasks).prepare(
        task_id=uuid4(),
        task_type=task_type,
        agent_id=definition.agent_id,
        attempt=1,
        target_ref=uuid4(),
        output_kind="chapter_plan" if task_type == "PLAN_CHAPTER" else "plan_review",
        capabilities=definition.capabilities,
        constraints=[],
        context_payload={"profile": {"id": profile_id, "version": profile_version}},
        expected_output_schema=schema,
    )
    template = next(
        item for item in prepared.prompt.modules if item.module.module_type == "TASK_TEMPLATE"
    )
    assert template.module.version == template_version
    assert prepared.prompt.output.schema_hash == definition.output_schema.schema_hash


@pytest.mark.parametrize(
    "module,version,content_hash",
    [
        ("plan-chapter", 10, "191570808253c9363a8c27643b9d0a4a984c014edf8dd0cde498aa41ed7ad083"),
        (
            "review-chapter-plan",
            6,
            "2e2606fa8984ffb23915bb4c574e1e9e12631b7d0ba51bfafbc8026ed8ea6d2a",
        ),
    ],
)
def test_previous_planning_templates_keep_their_exact_content(module, version, content_hash):
    historical = PromptRegistry().resolve(
        ModuleRef(module_id=module, version=version), expected_hash=content_hash
    )
    assert historical.module.content_hash == content_hash


@pytest.mark.parametrize(
    "outcome,key_change,concern,recommendation",
    [
        (
            "继续查阅档案，双方保留分歧但允许共同查看原卷。",
            "保管员由拒绝查阅转为允许研究者查看原卷，双方承担登记责任。",
            "缺页已在前章确定；再登记一次核查计划没有新增发现，现有信息不足以支撑篇幅。",
            "保留开放原卷的选择及后果，明确缺少哪一步核查材料；不要用缺页的同义解释扩写。",
        ),
        (
            "两名学徒仍合作检修，不擅自认定旧故障的责任。",
            "一人交出独用工具，另一人同意留下承担试验风险，合作条件发生变化。",
            "旧故障已知；再次同意检查不是查出故障来源，长篇幅与单一行动的材料不匹配。",
            "保留工具共享和承担风险的选择；若后续材料不足，报告缺口而不是新增事故或改偏好。",
        ),
    ],
    ids=["archive-access-choice", "workshop-risk-choice"],
)
def test_material_and_length_concerns_stay_warnings_and_preserve_character_choices(
    outcome, key_change, concern, recommendation
):
    brief_raw, plan_raw, review_raw = fixture_outputs()
    brief_body, plan_body, review_body = (
        brief_raw["result"],
        plan_raw["result"],
        review_raw["result"],
    )
    brief_body.update(chapter_objective=outcome, required_outcome=outcome)
    brief_body["must"][0].update(text=outcome, quote=outcome)
    plan_body.update(objective=outcome, required_outcome=outcome, constraints=[outcome])
    plan_body["scenes"][0].update(key_change=key_change, exit_condition=outcome)
    review_body.update(quality_issues=[concern], recommendations=[recommendation])
    brief = CreativeBriefOutput.model_validate(brief_body)
    plan = ChapterPlanOutput.model_validate(plan_body)
    original = deepcopy(plan.model_dump())
    reviewed = effective_verdict(PlanReviewOutput.model_validate(review_body), brief, plan)

    assert reviewed.verdict == "PASS_WITH_WARNINGS"
    assert not reviewed.hard_gate_issues and not reviewed.missing_requirements
    assert reviewed.requirement_coverage[0].covered
    assert canonical_plan_constraints(plan, brief).model_dump() == original
    feedback = review_feedback(reviewed.model_dump())
    assert not feedback["review_revision_targets"]
    assert feedback["recommendations"] == [recommendation, concern]
    assert "constraints" not in feedback
    with pytest.raises(ValidationError, match="FAIL requires hard evidence"):
        PlanReviewOutput.model_validate({**reviewed.model_dump(), "verdict": "FAIL"})
