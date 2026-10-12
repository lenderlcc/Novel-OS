import json

import pytest

from novel_os.agents.runtime import AgentRuntime
from novel_os.worker import AgentWorker
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def test_labelled_constraint_is_canonicalized_and_passes_first_iteration(
    planning_driver, core_database
):
    d = planning_driver
    run_one(core_database, d)

    def labels(request, body):
        body["result"]["constraints"] = ["[MUST M1] " + c for c in body["result"]["constraints"]]

    run_one(core_database, d, provider=RecordedProvider(labels))
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.workflow["planning_iteration_count"] == 1
    brief = d.read("/creative-brief")["body"]
    plan = d.read("/planning/plan")
    assert plan["plan"]["constraints"] == [brief["must"][0]["text"]]
    assert d.read("/planning/review")["body"]["hard_gate_issues"] == []


def test_two_round_repair_does_not_promote_or_accumulate_review_advice(
    planning_driver, core_database
):
    d = planning_driver
    run_one(core_database, d)

    def omit(request, body):
        body["result"]["constraints"] = []

    def advise(request, body):
        body["result"]["recommendations"] = ["Specify exactly seven steps and a broken latch"]

    run_one(core_database, d, provider=RecordedProvider(omit))
    run_one(core_database, d, provider=RecordedProvider(advise))
    first = d.read("/planning/review")["body"]
    assert first["verdict"] == "FAIL" and first["missing_requirements"] == ["M1"]
    assert first["requirement_coverage"][0]["covered"] is False
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    items = provider.requests[0].context_package.items
    feedback = next(i for i in items if i.source_type == "PLAN_REVIEW_REPORT")
    assert feedback.authority_level == "A7_AI_INFERENCE" and not feedback.locked
    payload = feedback.structured_payload
    assert payload["recommendations"] == first["recommendations"]
    assert payload["review_revision_targets"] == first["hard_gate_issues"]
    assert set(payload) == {"verdict", "review_revision_targets", "recommendations"}
    brief = next(i for i in items if i.source_type == "CREATIVE_BRIEF").structured_payload
    assert len(brief["authoritative_constraints"]) == 1
    assert brief["authoritative_constraints"][0]["category"] == "MUST"
    task_input = next(i for i in items if i.source_type == "TASK_INPUT").structured_payload
    assert "broken latch" not in json.dumps(task_input)
    plan = d.read("/planning/plan")
    assert plan["plan"]["constraints"] == [brief["must"][0]["text"]]

    def optional_warning(request, body):
        body["result"]["over_specification_issues"] = ["Leave local gestures to the Writer"]

    worker = run_one(core_database, d, provider=RecordedProvider(optional_warning))
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.workflow["planning_iteration_count"] == 2
    assert d.read("/planning/review")["verdict"] == "PASS_WITH_WARNINGS"
    assert not worker.run_once()
    assert len(d.read("/planning/history")["plans"]) == 2
    assert d.decide("MODIFY", reason="Make a local alternative").status_code == 200
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    feedback = next(
        i.structured_payload
        for i in provider.requests[0].context_package.items
        if i.source_type == "PLAN_REVIEW_REPORT"
    )
    assert feedback["review_revision_targets"] == []
    assert feedback["recommendations"] == ["Leave local gestures to the Writer"]
    assert "broken latch" not in json.dumps(feedback)
    assert d.read("/planning/plan")["plan"]["constraints"] == plan["plan"]["constraints"]


def test_two_failures_stop_automatic_loop_and_resume_does_not_buy_more_calls(
    planning_driver, core_database
):
    d = planning_driver
    run_one(core_database, d)
    for _ in range(2):
        run_one(core_database, d)
        worker = run_one(core_database, d, "QUALITY_FAIL")
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["block_reason"] == "PLANNING_ITERATION_LIMIT"
    assert d.workflow["planning_iteration_count"] == 2
    assert d.read("/planning/review")["verdict"] == "FAIL"
    history = d.read("/planning/history")
    assert len(history["plans"]) == len(history["reviews"]) == 2
    for _ in range(2):
        assert d.event("RESUME").status_code == 200
        assert d.workflow["current_state"] == "C90_BLOCKED"
        assert not worker.run_once()
    assert d.read("/planning/history") == history
    corrected = d.post(
        "/requirement",
        d.command(expected_brief_version=1, raw_requirement="必须找到线索，场景可以自行选择。"),
    )
    assert corrected.status_code == 200
    for _ in range(3):
        run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.read("/creative-brief")["version"] == 2


@pytest.mark.parametrize("defect", ["covered", "missing_ids", "soft_only_fail"])
def test_contradictory_review_is_rejected_before_persistence(
    planning_driver, core_database, defect
):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)

    def contradict(request, body):
        review = body["result"]
        review.update(
            verdict="FAIL",
            hard_gate_issues=[
                {"code": "MISSING_MUST", "constraint_id": "M1", "description": "Not covered"}
            ],
            missing_requirements=["M1"],
        )
        if defect == "missing_ids":
            review["missing_requirements"] = []
            review["requirement_coverage"][0]["covered"] = False
        elif defect == "soft_only_fail":
            review.update(
                hard_gate_issues=[], missing_requirements=[], recommendations=["Add detail"]
            )

    worker = AgentWorker(core_database, AgentRuntime(RecordedProvider(contradict)), max_attempts=1)
    assert worker.run_once()
    d.refresh()
    # A one-attempt worker pauses the existing retry budget for explicit user retry.
    assert d.workflow["current_state"] == "C90_BLOCKED"
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "REVIEW_CHAPTER_PLAN")
    assert task["status"] == "FAILED"
    assert task["last_error_code"] == "SCHEMA_PARSE_ERROR"
    assert task["attempt_count"] == 1
    assert task["result_metadata"]["disposition"] == "MANUAL_RETRY_REQUIRED"
    assert d.read("/planning/history")["reviews"] == []
    assert d.workflow["planning_iteration_count"] == 1
    assert not worker.run_once()


def test_planner_cannot_copy_review_advice_into_hard_constraints(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)

    def invent(request, body):
        body["result"]["constraints"].append("Reviewer instruction: MUST add a broken latch")

    run_one(core_database, d, provider=RecordedProvider(invent))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []


def test_review_cannot_reclassify_must_as_forbidden(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)

    def invent(request, body):
        r = body["result"]
        r.update(
            verdict="FAIL",
            forbidden_violations=["M1"],
            hard_gate_issues=[
                {
                    "code": "FORBIDDEN_VIOLATION",
                    "constraint_id": "M1",
                    "description": "Invented ban",
                }
            ],
        )
        r["requirement_coverage"][0]["covered"] = False

    run_one(core_database, d, provider=RecordedProvider(invent))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["reviews"] == []
    assert d.workflow["planning_iteration_count"] == 1


def test_nested_brief_provenance_is_not_a_selected_planning_source(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)

    def cite_history(request, body):
        brief = next(i for i in request.context_package.items if i.source_type == "CREATIVE_BRIEF")
        body["result"]["source_refs"].append(brief.structured_payload["must"][0]["source_ref"])

    run_one(core_database, d, provider=RecordedProvider(cite_history))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []
