"""Planning clarification uses existing tasks, Audit and user requirement correction."""

from copy import deepcopy
from uuid import uuid4

import pytest

from tests.core.workflow.test_context_engine import post
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.test_planning_clarification_contract import clarification


@pytest.mark.parametrize("existing_plan", [False, True])
def test_planning_clarification_blocks_without_plan_or_approval_and_user_correction_resumes(
    planning_driver, core_database, existing_plan
):
    d = planning_driver
    run_one(core_database, d)
    if existing_plan:
        run_one(core_database, d)
        run_one(core_database, d)
        assert d.decide("MODIFY", reason="需要核对缺失的视角身份").status_code == 200
    before = d.client.get(d.chapter_api).json()
    history = deepcopy(d.read("/planning/history"))

    def needs_decision(_, body):
        body.update(clarification(body))

    provider = RecordedProvider(needs_decision)
    worker = run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED", d.workflow
    assert d.workflow["block_reason"] == "EXTERNAL_CONDITION"
    assert worker.run_once() is False
    after = d.client.get(d.chapter_api).json()
    assert after == before
    assert d.read("/planning/history") == history
    assert not any(g["status"] == "WAITING" for g in d.read("/human-gates"))
    tasks = d.read("/agent-tasks")
    assert tasks[-1]["task_type"] == "PLAN_CHAPTER" and tasks[-1]["status"] == "BLOCKED"
    assert tasks[-1]["last_error_code"] is None
    assert tasks[-1]["result_metadata"]["kind"] == "planning_clarification"
    audits = d.client.get(d.chapter_api.split("/chapters/")[0] + "/audit").json()
    stored = [a for a in audits if (a.get("after") or {}).get("kind") == "planning_clarification"]
    assert len(stored) == 1
    questions = stored[0]["after"]
    assert stored[0]["actor_type"] == "AGENT"
    assert questions["brief_id"] == d.read("/creative-brief")["id"]
    assert questions["brief_version"] == 1
    assert questions["output_schema"] == "chapter-planning-result.v4"
    assert questions["unresolved_ambiguities"][0]["user_decision_needed"]
    assert questions["agent_run_id"] and questions["prompt_lineage_id"]
    assert questions["context_package_id"]
    selected = {
        (item.source_type, str(item.logical_id), item.source_version)
        for item in provider.requests[0].context_package.items
    }
    cited = {(r["source_type"], r["logical_id"], r["version"]) for r in questions["source_refs"]}
    assert cited <= selected
    assert ("CREATIVE_BRIEF", d.workflow["id"], 1) in cited

    corrected = d.post(
        "/requirement",
        d.command(expected_brief_version=1, raw_requirement="采用全知叙述，不需要单一人物限知。"),
    )
    assert corrected.status_code == 200, corrected.text
    assert d.workflow["current_state"] == "C01_REQUIREMENT_INTAKE"
    assert len(provider.requests) == 1
    run_one(core_database, d)
    assert d.read("/creative-brief")["version"] == 2
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C05_PLAN_REVIEW"
    assert d.read("/planning/plan")["plan"]["version"] == (2 if existing_plan else 1)


@pytest.mark.parametrize("invalid_source", ["foreign_ref", "missing_brief", "missing_lock"])
def test_clarification_retains_exact_snapshot_and_locked_authority_checks(
    planning_driver, core_database, invalid_source
):
    d = planning_driver
    project = d.chapter_api.split("/chapters/")[0]
    decision = post(
        d.client, project + "/decisions", {"question": "人物边界", "decision": "不改身份"}
    )
    post(
        d.client,
        project + "/locks",
        {"target_type": "DECISION", "target_id": decision["logical_id"], "expected_version": 1},
    )
    run_one(core_database, d)

    def invalid(_, body):
        body.update(clarification(body))
        refs = body["result"]["source_refs"]
        if invalid_source == "foreign_ref":
            refs.append(
                {"source_type": "CHAPTER_VERSION", "logical_id": str(uuid4()), "version": 1}
            )
        else:
            omitted = "CREATIVE_BRIEF" if invalid_source == "missing_brief" else "DECISION"
            body["result"]["source_refs"] = [r for r in refs if r["source_type"] != omitted]

    worker = run_one(core_database, d, provider=RecordedProvider(invalid))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert worker.run_once() is False
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "AUTHORITY_DENIED"
    audits = d.client.get(project + "/audit").json()
    assert not any((a.get("after") or {}).get("kind") == "planning_clarification" for a in audits)
