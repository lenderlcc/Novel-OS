import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from novel_os.agents.runtime import AgentRuntime
from novel_os.repositories.planning import PlanningRepository
from novel_os.worker import AgentWorker
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def reach_gate(database, driver, provider=None):
    for _ in range(3):
        run_one(database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL", driver.workflow


@pytest.mark.parametrize("decision", ["REJECT", "MODIFY", "REQUEST_ALTERNATIVE"])
def test_human_feedback_is_bound_to_new_plan_context(planning_driver, core_database, decision):
    d = planning_driver
    reach_gate(core_database, d)
    old = d.read("/planning/plan")
    assert d.decide(decision, reason="让冲突发生在车站，保留已有重大方向").status_code == 200
    assert d.workflow["planning_iteration_count"] == 2
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    task_input = next(
        item
        for item in provider.requests[0].context_package.items
        if item.source_type == "TASK_INPUT"
    )
    directive = json.loads(task_input.structured_payload["requirements"][0])
    assert directive["decision"] == decision and directive["plan_version"] == 1
    assert "车站" in directive["reason"]
    assert d.read("/planning/plan")["plan"]["version"] == 2
    assert d.read("/planning/plan/versions/1") == old
    run_one(core_database, d)
    assert d.decide().status_code == 200


def test_requirement_correction_versions_brief_and_closes_stale_gate(
    planning_driver, core_database
):
    d = planning_driver
    reach_gate(core_database, d)
    old_brief = d.read("/creative-brief")
    old_gate = d.gate()
    corrected = d.post(
        "/requirement",
        d.command(
            expected_brief_version=1, raw_requirement="新要求：找到线索，但不能透露真正的幕后人物。"
        ),
    )
    assert corrected.status_code == 200, corrected.text
    assert d.read("/creative-brief/versions/1")["status"] == "SUPERSEDED"
    run_one(core_database, d)
    brief = d.read("/creative-brief")
    assert brief["version"] == 2 and brief["supersedes_id"] == old_brief["id"]
    assert brief["raw_requirement"].startswith("新要求")
    assert brief["body"] != old_brief["body"]
    response = d.client.post(
        "/api/v1/human-gates/" + old_gate["id"] + "/decision",
        json=d.command(expected_artifact_version=1, decision="APPROVE"),
    )
    assert response.status_code == 409
    assert d.read("/planning/metrics")["requirement_correction_count"] == 1


def test_stale_human_plan_version_is_409(planning_driver, core_database):
    d = planning_driver
    reach_gate(core_database, d)
    gate = d.gate()
    response = d.client.post(
        "/api/v1/human-gates/" + gate["id"] + "/decision",
        json=d.command(expected_artifact_version=2, decision="APPROVE"),
    )
    assert response.status_code == 409
    assert d.read("/planning/plan")["plan"]["approved_at"] is None


@pytest.mark.parametrize("scenario", ["FORMAT_ERROR_ONCE", "MODEL_ERROR_ONCE"])
def test_technical_retry_preserves_business_iteration(planning_driver, core_database, scenario):
    d = planning_driver
    run_one(core_database, d)
    provider = __import__(
        "novel_os.agents.provider", fromlist=["MockModelProvider"]
    ).MockModelProvider(scenario)
    worker = AgentWorker(core_database, AgentRuntime(provider), retry_seconds=0)
    assert worker.run_once()
    d.refresh()
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.workflow["planning_iteration_count"] == 1
    assert d.read("/planning/history")["plans"] == []
    assert worker.run_once()
    d.refresh()
    assert d.workflow["current_state"] == "C05_PLAN_REVIEW"
    assert d.workflow["planning_iteration_count"] == 1
    assert d.read("/planning/metrics")["technical_retry_count"] == 1


@pytest.mark.parametrize(
    "mode", ["wrong_ref", "invented_must", "fake_assumption", "unnecessary_escalation"]
)
def test_invalid_requirement_never_creates_brief(planning_driver, core_database, mode):
    def mutate(request, body):
        brief = body["result"]
        if mode == "wrong_ref":
            brief["source_refs"][0]["logical_id"] = str(uuid4())
        elif mode == "invented_must":
            brief["must"][0].update(text="用户必须引入新世界规则", quote="用户必须引入新世界规则")
        elif mode == "fake_assumption":
            brief["assumptions"] = [
                {"text": brief["must"][0]["text"], "impact": "LOW", "confidence": 0.9}
            ]
        else:
            body["status"] = "NEEDS_HUMAN"
            body["escalation"] = {"required": True, "reason": "Small missing detail"}

    d = planning_driver
    run_one(core_database, d, provider=RecordedProvider(mutate))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["briefs"] == []


@pytest.mark.parametrize("impact", ["LOW", "MEDIUM"])
def test_safe_ambiguity_records_assumption_and_continues(planning_driver, core_database, impact):
    def mutate(request, body):
        body["result"]["assumptions"] = [
            {"text": "选择车站作为局部场景", "impact": impact, "confidence": 0.4}
        ]
        body["result"]["unresolved_ambiguities"] = [
            {
                "issue": "没有指定场景地点",
                "impact": impact,
                "confidence": 0.4,
                "can_safely_infer": True,
                "impact_explanation": "仅影响局部呈现",
                "user_decision_needed": "无需重大决策",
            }
        ]
        body["confidence"] = 0.4

    d = planning_driver
    run_one(core_database, d, provider=RecordedProvider(mutate))
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.read("/creative-brief")["body"]["assumptions"][0]["impact"] == impact


def test_natural_language_categories_and_persistent_candidate_are_separate(
    planning_driver, core_database
):
    def recorded_interpretation(request, body):
        brief = body["result"]
        ref = brief["source_refs"][0]
        brief["must"] = [
            {"id": "M1", "text": "必须找到线索", "quote": "必须找到线索", "source_ref": ref}
        ]
        brief["forbidden"] = [
            {"id": "F1", "text": "不能杀死主角", "quote": "不能杀死主角", "source_ref": ref}
        ]
        brief["preserve"] = [
            {
                "id": "P1",
                "text": "保留人物之间的信任",
                "quote": "保留人物之间的信任",
                "source_ref": ref,
            }
        ]
        brief["persistent_preference_candidates"] = [
            {
                "id": "PC1",
                "text": "保留人物之间的信任",
                "quote": "保留人物之间的信任",
                "source_ref": ref,
            }
        ]

    d = planning_driver
    run_one(core_database, d, provider=RecordedProvider(recorded_interpretation))
    brief = d.read("/creative-brief")["body"]
    assert brief["must"][0]["text"] == "必须找到线索"
    assert brief["forbidden"][0]["text"] == "不能杀死主角"
    assert brief["preserve"][0]["text"] == "保留人物之间的信任"
    from novel_os.models.core import DecisionModel, RequirementModel

    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(RequirementModel)) == 0
        assert session.scalar(select(func.count()).select_from(DecisionModel)) == 0
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"


@pytest.mark.parametrize(
    "mutation", ["missing_coverage", "required_major_change", "missing_constraint"]
)
def test_plan_defects_cannot_pass_nominal_review(planning_driver, core_database, mutation):
    d = planning_driver
    run_one(core_database, d)

    def mutate(request, body):
        plan = body["result"]
        if mutation == "missing_coverage":
            plan["requirement_coverage"] = []
        elif mutation == "missing_constraint":
            plan["constraints"] = []
        else:
            plan["proposed_major_changes"] = [
                {
                    "description": "引入新的世界规则",
                    "reason": "大幅改变故事",
                    "affected_scope": "世界设定",
                    "required_for_plan": True,
                    "disposition": "PROPOSAL_ONLY",
                }
            ]

    run_one(core_database, d, provider=RecordedProvider(mutate))
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.read("/planning/review")["verdict"] == "FAIL"
    assert d.workflow["planning_iteration_count"] == 2


def test_optional_major_proposal_remains_unapproved_after_plan_approval(
    planning_driver, core_database
):
    d = planning_driver
    run_one(core_database, d)

    def mutate(request, body):
        body["result"]["proposed_major_changes"] = [
            {
                "description": "备选世界规则",
                "reason": "仅供未来考虑",
                "affected_scope": "世界",
                "required_for_plan": False,
                "disposition": "PROPOSAL_ONLY",
            }
        ]

    run_one(core_database, d, provider=RecordedProvider(mutate))
    run_one(core_database, d)
    assert d.decide().status_code == 200
    plan = d.read("/planning/plan")
    assert plan["plan"]["status"] == "APPROVED"
    assert plan["generation"]["body"]["proposed_major_changes"][0]["disposition"] == "PROPOSAL_ONLY"


def test_cancelled_inflight_business_result_is_ignored(planning_driver, core_database):
    d = planning_driver

    def cancel(request, body):
        assert d.event("CANCEL").status_code == 200

    run_one(core_database, d, provider=RecordedProvider(cancel))
    assert d.workflow["current_state"] == "C92_CANCELLED"
    assert d.read("/planning/history")["briefs"] == []
    tasks = d.read("/agent-tasks")
    assert tasks[0]["result_metadata"]["disposition"] == "STALE_IGNORED"


def test_business_plan_and_brief_cannot_be_updated_or_deleted(planning_driver, core_database):
    d = planning_driver
    reach_gate(core_database, d)
    brief = d.read("/creative-brief")
    plan = d.read("/planning/plan")
    statements = [
        ("UPDATE creative_briefs SET body = '{}' WHERE id=:id", brief["id"]),
        ("DELETE FROM creative_briefs WHERE id=:id", brief["id"]),
        ("UPDATE chapter_plans SET objective='changed' WHERE id=:id", plan["plan"]["id"]),
        ("UPDATE plan_generations SET body='{}' WHERE plan_id=:id", plan["plan"]["id"]),
    ]
    for sql, identifier in statements:
        with core_database.session() as session, pytest.raises(IntegrityError), session.begin():
            session.execute(text(sql), {"id": UUID(identifier)})


def test_artifact_failure_rolls_back_task_workflow_and_audit(
    planning_driver, core_database, monkeypatch
):
    d = planning_driver
    before = d.refresh()
    original = PlanningRepository.add

    def fail_after_insert(self, entity):
        original(self, entity)
        raise RuntimeError("Injected application failure after artifact insert")

    monkeypatch.setattr(PlanningRepository, "add", fail_after_insert)
    with pytest.raises(RuntimeError):
        run_one(core_database, d)
    assert d.refresh() == before
    assert d.read("/planning/history")["briefs"] == []
    assert d.read("/agent-tasks")[0]["status"] == "RUNNING"


def test_repository_never_commits_or_rolls_back():
    import ast
    from pathlib import Path

    module = ast.parse(Path("novel_os/repositories/planning.py").read_text())
    assert not [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"commit", "rollback"}
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "APPROVED"),
        ("authority_level", "A1_USER_LOCKED"),
        ("version", 2),
        ("actor_type", "SYSTEM"),
    ],
)
def test_natural_input_api_rejects_authority_fields(core_client, chapter_api, field, value):
    parts = chapter_api.split("/")
    result = core_client.post(
        "/api/v1/workflows/chapter-planning",
        json={
            "project_id": parts[4],
            "chapter_id": parts[6],
            "event_id": str(uuid4()),
            "raw_requirement": "找到线索",
            field: value,
        },
    )
    assert result.status_code == 422
