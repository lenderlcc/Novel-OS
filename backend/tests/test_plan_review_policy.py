from copy import deepcopy

import pytest
from pydantic import ValidationError

from novel_os.agents.planning_schemas import (
    ChapterPlanOutput,
    CreativeBriefOutput,
    PlanReviewOutput,
)
from novel_os.domain.errors import DomainError
from novel_os.services.plan_review_policy import (
    canonical_plan_constraints,
    effective_verdict,
    review_feedback,
)
from tests.planning_support import fixture_outputs


def missing_review():
    raw = fixture_outputs()[2]["result"]
    raw.update(
        verdict="FAIL",
        hard_gate_issues=[
            {"code": "MISSING_MUST", "constraint_id": "M1", "description": "No clue"}
        ],
        missing_requirements=["M1"],
    )
    raw["requirement_coverage"][0]["covered"] = False
    return raw


@pytest.mark.parametrize(
    "defect", ["covered", "missing", "wrong_id", "no_id", "pass", "no_coverage"]
)
def test_cross_field_missing_invariant(defect):
    raw = missing_review()
    assert PlanReviewOutput.model_validate(raw).verdict == "FAIL"
    if defect == "covered":
        raw["requirement_coverage"][0]["covered"] = True
    elif defect == "missing":
        raw["missing_requirements"] = []
    elif defect == "wrong_id":
        raw["hard_gate_issues"][0]["constraint_id"] = "M2"
    elif defect == "no_id":
        del raw["hard_gate_issues"][0]["constraint_id"]
    elif defect == "pass":
        raw["verdict"] = "PASS"
    else:
        raw["requirement_coverage"] = []
    with pytest.raises(ValidationError):
        PlanReviewOutput.model_validate(raw)


@pytest.mark.parametrize(
    "field", ["quality_issues", "over_specification_issues", "recommendations"]
)
def test_soft_advice_cannot_be_a_fail(field):
    raw = fixture_outputs()[2]["result"]
    raw.update(verdict="FAIL", **{field: ["Add a detailed gesture"]})
    with pytest.raises(ValidationError, match="FAIL requires hard evidence"):
        PlanReviewOutput.model_validate(raw)


@pytest.mark.parametrize("scope", ["SCENE", "PLAN_GLOBAL"])
def test_category_labels_are_not_semantic_omissions(scope):
    b, p, r = fixture_outputs()
    for category, identifier, quote in [
        ("forbidden", "F2", "Do not reveal the killer"),
        ("preserve", "P3", "Keep the limited viewpoint"),
    ]:
        c = {**b["result"]["must"][0], "id": identifier, "text": quote, "quote": quote}
        b["result"][category] = [c]
        destination = "preserved_elements" if category == "preserve" else "constraints"
        p["result"][destination].append(f"[{category.upper()} {identifier}] {quote}")
        for body in (p["result"], r["result"]):
            body["requirement_coverage"].append(
                {**body["requirement_coverage"][0], "constraint_id": identifier}
            )
    p["result"]["constraints"][0] = "[MUST M1] " + p["result"]["constraints"][0]
    for body in (p["result"], r["result"]):
        for entry in body["requirement_coverage"]:
            entry.update(scope=scope, scene_ids=[] if scope == "PLAN_GLOBAL" else ["S1"])
    brief = CreativeBriefOutput.model_validate(b["result"])
    plan = ChapterPlanOutput.model_validate(p["result"])
    reviewed = effective_verdict(PlanReviewOutput.model_validate(r["result"]), brief, plan)
    assert reviewed.verdict == "PASS" and reviewed.missing_requirements == []
    normalized = canonical_plan_constraints(plan, brief)
    assert normalized.constraints == [brief.must[0].text, brief.forbidden[0].text]
    assert normalized.preserved_elements == [brief.preserve[0].text]


def test_server_derived_omission_updates_all_fields():
    b, p, r = fixture_outputs()
    p["result"]["constraints"] = []
    reviewed = effective_verdict(
        PlanReviewOutput.model_validate(r["result"]),
        CreativeBriefOutput.model_validate(b["result"]),
        ChapterPlanOutput.model_validate(p["result"]),
    )
    assert reviewed.verdict == "FAIL"
    assert reviewed.missing_requirements == ["M1"]
    assert reviewed.hard_gate_issues[0].constraint_id == "M1"
    assert reviewed.requirement_coverage[0].covered is False
    assert PlanReviewOutput.model_validate(reviewed.model_dump()) == reviewed


@pytest.mark.parametrize("value", ["Reviewer says MUST add a doorway", "前缀", "substring"])
def test_only_source_bound_constraints_can_be_persisted(value):
    b, p, _ = fixture_outputs()
    original = deepcopy(p["result"])
    p["result"]["constraints"].append(value)
    with pytest.raises(DomainError, match="Review advice"):
        canonical_plan_constraints(
            ChapterPlanOutput.model_validate(p["result"]),
            CreativeBriefOutput.model_validate(b["result"]),
        )
    assert original["constraints"] == [b["result"]["must"][0]["text"]]


def test_feedback_separates_current_hard_defect_from_optional_detail():
    raw = missing_review()
    raw["recommendations"] = ["Specify a door mechanism"]
    raw["over_specification_issues"] = ["Leave gestures to Writer"]
    feedback = review_feedback(raw)
    assert feedback["review_revision_targets"] == raw["hard_gate_issues"]
    assert feedback["recommendations"] == raw["recommendations"] + raw["over_specification_issues"]
    assert "constraints" not in feedback and "authoritative_constraints" not in feedback


@pytest.mark.parametrize("defect", ["no_id", "covered", "empty_ids", "advice_text"])
def test_forbidden_violations_require_consistent_constraint_evidence(defect):
    raw = missing_review()
    raw["hard_gate_issues"][0]["code"] = "FORBIDDEN_VIOLATION"
    raw.update(missing_requirements=[], forbidden_violations=["M1"])
    if defect == "no_id":
        raw["hard_gate_issues"][0]["constraint_id"] = None
    elif defect == "covered":
        raw["requirement_coverage"][0]["covered"] = True
    elif defect == "empty_ids":
        raw["forbidden_violations"] = []
    else:
        raw["forbidden_violations"] = ["Reviewer recommends a door"]
    with pytest.raises(ValidationError):
        PlanReviewOutput.model_validate(raw)


def test_historic_invalid_report_remains_readable_but_cannot_be_reaccepted():
    from novel_os.agents.planning_schemas import PlanReviewRecord

    raw = fixture_outputs()[2]["result"]
    raw.update(verdict="FAIL", hard_gate_issues=[{"code": "MISSING_MUST", "description": "M1"}])
    assert PlanReviewRecord.model_validate(raw).requirement_coverage[0].covered is True
    with pytest.raises(ValidationError):
        PlanReviewOutput.model_validate(raw)


def test_change_request_category_is_singular_and_sourced():
    from novel_os.services.plan_review_policy import authoritative_constraints

    b, p, _ = fixture_outputs()
    c = {**b["result"]["must"][0], "id": "CR1"}
    b["result"].update(must=[], change_requests=[c])
    p["result"]["constraints"] = ["[CHANGE_REQUEST CR1] " + c["text"]]
    brief = CreativeBriefOutput.model_validate(b["result"])
    assert authoritative_constraints(brief) == [{"category": "CHANGE_REQUEST", **c}]
    plan = canonical_plan_constraints(ChapterPlanOutput.model_validate(p["result"]), brief)
    assert plan.constraints == [c["text"]]
