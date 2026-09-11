from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from novel_os.models.core import AuditRecordModel, ChapterPlanModel, ChapterVersionModel
from novel_os.models.workflow import WorkflowEventModel, WorkflowTransitionModel

pytestmark = pytest.mark.integration


def test_happy_path_and_audit_completeness(driver, core_database):
    driver.advance_to("C16_COMPLETED")
    assert driver.workflow["status"] == "COMPLETED"
    assert driver.workflow["simulation"] is True
    assert driver.workflow["retry_count"] == driver.workflow["revision_count"] == 0
    assert driver.workflow["planning_iteration_count"] == 1
    history = driver.client.get(driver.url + "/history").json()
    assert [r["to_state"] for r in history] == [
        "C00_CREATED",
        "C01_REQUIREMENT_INTAKE",
        "C02_CONTEXT_ASSEMBLY",
        "C03_REQUIREMENT_READY",
        "C04_CHAPTER_PLANNING",
        "C05_PLAN_REVIEW",
        "C06_PLAN_APPROVAL",
        "C07_WRITING",
        "C08_DETERMINISTIC_CHECK",
        "C09_INTERNAL_REVIEW",
        "C11_INTERNAL_PASS",
        "C12_USER_REVIEW",
        "C14_MEMORY_PREPARATION",
        "C15_MEMORY_COMMIT",
        "C16_COMPLETED",
    ]
    assert [r["to_version"] for r in history] == list(range(1, 16))
    gates = driver.client.get(driver.url + "/human-gates").json()
    assert [g["status"] for g in gates] == ["APPROVED", "APPROVED"]
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["current_version"] == chapter["approved_version"] == 1
    assert chapter["current_plan_version"] == chapter["approved_plan_version"] == 1
    with core_database.session() as session:
        joined = session.execute(
            select(WorkflowTransitionModel, WorkflowEventModel, AuditRecordModel)
            .join(
                WorkflowEventModel, WorkflowTransitionModel.event_id == WorkflowEventModel.event_id
            )
            .join(AuditRecordModel, WorkflowTransitionModel.audit_record_id == AuditRecordModel.id)
        ).all()
        assert len(joined) == len(history)
        for transition, event, audit in joined:
            assert event.workflow_id == transition.workflow_id == UUID(driver.workflow["id"])
            assert audit.after["workflow_id"] == driver.workflow["id"]
            assert audit.after["state_version"] == transition.to_version
            assert audit.request_id == event.request_id
            assert audit.after["event_id"] == str(event.event_id)
        gate_audits = [
            a for a in session.scalars(select(AuditRecordModel)) if "human_gate_id" in a.after
        ]
        assert len(gate_audits) == 4
    assert driver.event("USER_SUBMITTED").status_code == 409


def test_plan_review_failure_creates_next_version_and_keeps_history(driver, core_database):
    driver.advance_to("C05_PLAN_REVIEW")
    assert driver.fake("review_failure").status_code == 200
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert driver.workflow["planning_iteration_count"] == 2
    assert driver.workflow["retry_count"] == driver.workflow["revision_count"] == 0
    assert driver.fake().status_code == 200
    assert driver.workflow["plan_version"] == 2
    with core_database.session() as session:
        plans = session.scalars(select(ChapterPlanModel).order_by(ChapterPlanModel.version)).all()
        assert [p.version for p in plans] == [1, 2]
        assert plans[1].supersedes_id == plans[0].id
        assert plans[0].objective != plans[1].objective


def test_internal_review_revision_rechecks_and_keeps_approved_pointer(driver):
    driver.advance_to("C09_INTERNAL_REVIEW")
    assert driver.fake("review_failure").status_code == 200
    assert driver.workflow["current_state"] == "C10_REVISION"
    assert driver.workflow["revision_count"] == 1
    assert driver.workflow["retry_count"] == 0
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert driver.workflow["draft_version"] == 2
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    driver.advance_to("C16_COMPLETED")
    assert driver.client.get(driver.chapter_api).json()["approved_version"] == 2


@pytest.mark.parametrize("decision", ["REJECT", "MODIFY", "REQUEST_ALTERNATIVE"])
def test_user_feedback_diagnosis_and_local_revision(driver, decision):
    driver.advance_to("C12_USER_REVIEW")
    assert driver.decide(decision).status_code == 200
    assert driver.workflow["current_state"] == "C13_USER_FEEDBACK_DIAGNOSIS"
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C10_REVISION"
    assert driver.workflow["revision_count"] == 1
    driver.advance_to("C16_COMPLETED")


def test_feedback_can_replan_and_preserves_approved_plan(driver):
    driver.advance_to("C12_USER_REVIEW")
    assert driver.decide("REJECT").status_code == 200
    assert driver.fake("replan").status_code == 200
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert driver.fake().status_code == 200
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["current_plan_version"] == 2
    assert chapter["approved_plan_version"] == 1
    driver.advance_to("C16_COMPLETED")


def test_block_resume_and_pause_resume(driver):
    driver.advance_to("C04_CHAPTER_PLANNING")
    assert driver.event("BLOCK", reason="Waiting for external dependency").status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    assert driver.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert driver.workflow["planning_iteration_count"] == 1
    assert driver.post("/pause", driver.command()).status_code == 200
    assert driver.workflow["status"] == "PAUSED"
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert driver.fake().status_code == 409
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["status"] == "WAITING_AGENT"
    driver.advance_to("C16_COMPLETED")


def test_pause_resume_at_gate_does_not_duplicate_gate(driver):
    driver.advance_to("C06_PLAN_APPROVAL")
    gate_id = driver.gate()["id"]
    assert driver.post("/pause", driver.command()).status_code == 200
    assert driver.decide().status_code == 409
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.gate()["id"] == gate_id
    assert driver.decide().status_code == 200


def test_cancel_closes_gate_and_rejects_future_events(driver):
    driver.advance_to("C06_PLAN_APPROVAL")
    assert driver.post("/cancel", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == "C92_CANCELLED"
    assert driver.workflow["status"] == "CANCELLED"
    assert driver.client.get(driver.url + "/human-gates").json()[0]["status"] == "CANCELLED"
    assert driver.post("/resume", driver.command()).status_code == 409
    assert driver.event("USER_SUBMITTED").status_code == 409


def test_gate_cancel(driver):
    driver.advance_to("C06_PLAN_APPROVAL")
    assert driver.decide("CANCEL").status_code == 200
    assert driver.workflow["current_state"] == "C92_CANCELLED"


@pytest.mark.parametrize("outcome,attempts", [("technical_failure", 3), ("fatal_failure", 1)])
def test_persistent_or_fatal_executor_failure_is_failed(driver, outcome, attempts):
    driver.advance_to("C04_CHAPTER_PLANNING")
    for attempt in range(attempts):
        assert driver.fake(outcome).status_code == 200
        if attempt < attempts - 1:
            assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
            assert driver.workflow["retry_count"] == attempt + 1
    assert driver.workflow["current_state"] == "C91_FAILED"
    assert driver.workflow["planning_iteration_count"] == 1
    assert driver.workflow["revision_count"] == 0
    assert driver.post("/resume", driver.command()).status_code == 409


def test_retry_budget_resets_for_next_stage_but_total_retained(driver):
    driver.advance_to("C04_CHAPTER_PLANNING")
    driver.fake("technical_failure")
    driver.fake("technical_failure")
    driver.fake()
    assert driver.workflow["state_retry_count"] == 0
    driver.fake("technical_failure")
    assert driver.workflow["retry_count"] == 3
    assert driver.workflow["state_retry_count"] == 1
    assert driver.workflow["current_state"] == "C05_PLAN_REVIEW"


def test_illegal_event_and_unknown_workflow(driver):
    before = dict(driver.workflow)
    assert driver.post("/resume", driver.command()).status_code == 409
    assert driver.workflow == before
    assert driver.client.get("/api/v1/workflows/" + str(uuid4())).status_code == 404


def test_no_memory_tables_or_side_effects(driver, core_database):
    driver.advance_to("C14_MEMORY_PREPARATION")
    with core_database.session() as session:
        versions = [(v.id, v.content) for v in session.scalars(select(ChapterVersionModel))]
    driver.advance_to("C16_COMPLETED")
    with core_database.session() as session:
        assert [(v.id, v.content) for v in session.scalars(select(ChapterVersionModel))] == versions


def test_block_resume_does_not_refresh_technical_retry_budget(driver):
    driver.advance_to("C04_CHAPTER_PLANNING")
    assert driver.fake("technical_failure").status_code == 200
    assert driver.fake("technical_failure").status_code == 200
    assert driver.event("BLOCK").status_code == 200
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["state_retry_count"] == 2
    assert driver.fake("technical_failure").status_code == 200
    assert driver.workflow["current_state"] == "C91_FAILED"
