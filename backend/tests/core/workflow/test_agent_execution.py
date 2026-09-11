from uuid import UUID

import pytest
from agent_test_support import claim, complete, pending_task, runs, start, task_record, worker
from sqlalchemy import select

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.registry import STAGE_TASKS, AgentRegistry
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import AgentId, RunStatus, TaskStatus
from novel_os.models.core import AuditRecordModel

pytestmark = pytest.mark.integration


def test_registry_has_exactly_seven_agents():
    registry = AgentRegistry()
    assert set(registry.definitions) == set(AgentId)
    assert len(registry.definitions) == 7
    for definition in STAGE_TASKS.values():
        agent = registry.get(definition.agent_id)
        assert definition.task_type in agent.accepted_task_types
        assert definition.capability in agent.default_capabilities


def test_stage_task_is_atomic_idempotent_and_read_only_over_http(driver):
    body = driver.command(event_type="USER_SUBMITTED")
    assert driver.post("/events", body).status_code == 200
    tasks = driver.client.get(driver.url + "/agent-tasks").json()
    assert len(tasks) == 1
    task = tasks[0]
    assert task["task_type"] == "MOCK_INTAKE"
    assert task["agent_id"] == "A02_REQUIREMENT"
    assert task["workflow_state_version"] == driver.workflow["state_version"]
    assert task["attempt_count"] == 0
    assert "lease_token" not in task
    assert driver.post("/events", body).json()["duplicate"] is True
    assert driver.client.get(driver.url + "/agent-tasks").json() == tasks
    url = "/api/v1/agent-tasks/" + task["task_id"]
    assert driver.client.get(url).json() == task
    assert driver.client.get(url + "/runs").json() == []
    assert driver.client.post(url + "/mock-execute", json={}).status_code in {404, 405}
    assert driver.client.post(
        "/api/v1/agent-tasks", json={"capabilities": ["APPROVE"]}
    ).status_code in {404, 405}


def test_claim_start_success_has_separate_run_and_audit(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    assert lease is not None
    assert task_record(core_database, lease.task_id).status == TaskStatus.CLAIMED
    assert runs(core_database, lease.task_id)[0].status == RunStatus.CLAIMED
    task = start(core_database, lease)
    assert task.status == TaskStatus.RUNNING
    execution = AgentRuntime(MockModelProvider()).execute(task)
    assert complete(core_database, lease, execution) == "APPLIED"
    task = task_record(core_database, lease.task_id)
    assert task.status == TaskStatus.SUCCEEDED
    assert task.lease_token is task.lease_owner is task.lease_expires_at is None
    run = runs(core_database, task.task_id)[0]
    assert run.status == RunStatus.SUCCEEDED
    assert run.started_at >= run.claimed_at
    assert run.finished_at >= run.started_at
    assert run.duration_ms >= 0
    assert task.result_ref == run.run_id
    assert driver.refresh()["current_state"] == "C05_PLAN_REVIEW"
    assert driver.client.get(driver.chapter_api).json()["current_plan_version"] == 1
    with core_database.session() as session:
        records = [
            a
            for a in session.scalars(select(AuditRecordModel))
            if a.after.get("agent_task_id") == str(task.task_id)
        ]
        assert {a.after.get("status") for a in records} >= {
            "PENDING",
            "CLAIMED",
            "RUNNING",
            "SUCCEEDED",
        }
        assert any(a.after.get("run_id") == str(run.run_id) for a in records)
    history = driver.client.get(driver.url + "/history").json()
    assert complete(core_database, lease, execution) == "DUPLICATE"
    assert driver.client.get(driver.url + "/history").json() == history
    assert len(runs(core_database, task.task_id)) == 1


@pytest.mark.parametrize(
    "scenario,error", [("FORMAT_ERROR_ONCE", "FORMAT_ERROR"), ("MODEL_ERROR_ONCE", "MODEL_TIMEOUT")]
)
def test_technical_retry_keeps_task_and_creates_independent_runs(
    driver, core_database, scenario, error
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    before = driver.workflow.copy()
    assert worker(core_database, scenario).run_once()
    failed = runs(core_database, task_id)[0]
    assert failed.status == RunStatus.FAILED
    assert failed.error_code == error
    assert failed.disposition == "RETRY_SCHEDULED"
    assert task_record(core_database, task_id).status == TaskStatus.PENDING
    assert driver.refresh() == before
    # A fresh worker/provider represents process restart; scenario is keyed by persisted attempt.
    assert worker(core_database, scenario).run_once()
    history = runs(core_database, task_id)
    assert [r.attempt_number for r in history] == [1, 2]
    assert history[0] == failed
    assert history[1].status == RunStatus.SUCCEEDED
    assert history[0].run_id != history[1].run_id
    assert driver.refresh()["retry_count"] == driver.workflow["revision_count"] == 0
    assert driver.workflow["planning_iteration_count"] == 1


@pytest.mark.parametrize("scenario", ["ALWAYS_FAIL", "MALFORMED_OUTPUT"])
def test_retry_exhaustion_is_terminal(driver, core_database, scenario):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    for _ in range(3):
        assert worker(core_database, scenario).run_once()
    task = task_record(core_database, task_id)
    assert task.status == TaskStatus.FAILED
    assert task.attempt_count == task.max_attempts == 3
    history = runs(core_database, task_id)
    assert len(history) == 3
    assert all(r.status == RunStatus.FAILED for r in history)
    assert driver.refresh()["current_state"] == "C91_FAILED"
    assert not worker(core_database, scenario).run_once()


@pytest.mark.parametrize(
    "stage,target,revision,planning",
    [
        ("C05_PLAN_REVIEW", "C04_CHAPTER_PLANNING", 0, 2),
        ("C08_DETERMINISTIC_CHECK", "C10_REVISION", 1, 1),
        ("C09_INTERNAL_REVIEW", "C10_REVISION", 1, 1),
    ],
)
def test_quality_failure_uses_review_verdict_without_technical_retry(
    driver, core_database, stage, target, revision, planning
):
    driver.advance_to(stage)
    task_id = UUID(pending_task(driver)["task_id"])
    assert worker(core_database, "QUALITY_FAIL").run_once()
    assert task_record(core_database, task_id).status == TaskStatus.SUCCEEDED
    history = runs(core_database, task_id)
    assert len(history) == 1
    assert history[0].output_metadata["verdict"] == "FAIL"
    assert driver.refresh()["current_state"] == target
    assert driver.workflow["revision_count"] == revision
    assert driver.workflow["planning_iteration_count"] == planning
    assert driver.workflow["retry_count"] == 0


@pytest.mark.parametrize("scenario", ["BLOCKED", "NEEDS_HUMAN", "LOW_CONFIDENCE"])
def test_business_block_and_escalation_never_approve(driver, core_database, scenario):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    assert worker(core_database, scenario).run_once()
    task = task_record(core_database, task_id)
    assert task.status == TaskStatus.BLOCKED
    assert task.attempt_count == 1
    assert driver.refresh()["current_state"] == "C90_BLOCKED"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None
    assert not worker(core_database).run_once()
    assert task.result_metadata["escalation_required"]


def test_full_mock_pipeline_stops_at_human_gates_and_completes(driver, core_database):
    assert driver.event("USER_SUBMITTED").status_code == 200
    executor = worker(core_database)
    for gate_state in ("C06_PLAN_APPROVAL", "C12_USER_REVIEW", "C16_COMPLETED"):
        for _ in range(20):
            if driver.refresh()["current_state"] == gate_state:
                break
            assert executor.run_once()
        assert driver.workflow["current_state"] == gate_state
        assert not executor.run_once()
        if gate_state != "C16_COMPLETED":
            assert driver.gate()["status"] == "WAITING"
            assert driver.decide().status_code == 200
    tasks = driver.client.get(driver.url + "/agent-tasks").json()
    assert len(tasks) == 11
    assert all(task["status"] == "SUCCEEDED" and task["attempt_count"] == 1 for task in tasks)
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["current_version"] == chapter["approved_version"] == 1
    assert chapter["current_plan_version"] == chapter["approved_plan_version"] == 1
