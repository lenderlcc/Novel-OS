"""Manual Requirement execution uses the normal queue, leases, workflow and lineage."""

import json
import subprocess
import sys
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.main import create_app
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.services.agent_queue import AgentQueue
from novel_os.worker import AgentWorker

SCOPE = ("PARSE_CHAPTER_REQUIREMENT",)


def scoped_worker(database, scenario="SUCCESS"):
    return AgentWorker(
        database,
        AgentRuntime(MockModelProvider(scenario)),
        task_types=SCOPE,
        max_attempts=1,
        retry_seconds=0,
    )


def test_paused_submission_waits_for_resume_then_only_requirement_executes(
    planning_driver, core_database
):
    d = planning_driver
    original = d.read("/agent-tasks")[0]
    worker = scoped_worker(core_database)
    assert d.post("/pause", d.command(reason="Wait for manual model execution")).status_code == 200
    # The original queued task is cancelled by Pause; no model attempt is created.
    assert worker.run_once() is False
    assert all(t["attempt_count"] == 0 for t in d.read("/agent-tasks"))
    assert d.client.get(d.url + "/creative-brief").status_code == 404
    assert d.post("/resume", d.command(reason="Manually execute requirement")).status_code == 200
    assert worker.run_once()
    assert d.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    assert worker.run_once() is False
    brief = d.read("/creative-brief")
    assert brief["raw_requirement"] == original["objective"]
    tasks = d.read("/agent-tasks")
    completed = next(t for t in tasks if t["status"] == "SUCCEEDED")
    assert completed["attempt_count"] == 1
    history = d.client.get(f"/api/v1/agent-tasks/{completed['task_id']}/runs").json()
    assert history[0]["input_metadata"]["attempt_limit"] == 1
    assert next(t for t in tasks if t["task_type"] == "PLAN_CHAPTER")["attempt_count"] == 0
    assert d.read("/planning/history")["plans"] == d.read("/writing/history") == []
    assert brief["context_package_id"] and brief["prompt_lineage_id"] and brief["agent_run_id"]


def test_scoped_failure_waits_for_explicit_retry(planning_driver, core_database):
    worker = scoped_worker(core_database, "ALWAYS_FAIL")
    assert worker.run_once()
    assert worker.run_once() is False
    task = planning_driver.read("/agent-tasks")[0]
    assert task["status"] == "FAILED"
    assert task["attempt_count"] == 1
    assert task["result_metadata"]["disposition"] == "MANUAL_RETRY_REQUIRED"
    assert planning_driver.refresh()["current_state"] == "C90_BLOCKED"
    assert planning_driver.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"

    assert (
        planning_driver.post(
            "/resume", planning_driver.command(reason="User approved another model call")
        ).status_code
        == 200
    )
    assert scoped_worker(core_database).run_once()
    tasks = planning_driver.read("/agent-tasks")
    requirement_tasks = [task for task in tasks if task["task_type"] == "PARSE_CHAPTER_REQUIREMENT"]
    assert [task["attempt_count"] for task in requirement_tasks] == [1, 1]
    assert next(task for task in tasks if task["task_type"] == "PLAN_CHAPTER")["attempt_count"] == 0
    assert planning_driver.refresh()["current_state"] == "C04_CHAPTER_PLANNING"


def test_lowering_budget_terminates_pending_retry_without_another_call(
    planning_driver, core_database
):
    worker = AgentWorker(
        core_database, AgentRuntime(MockModelProvider("ALWAYS_FAIL")), retry_seconds=0
    )
    assert worker.run_once()
    task = planning_driver.read("/agent-tasks")[0]
    assert task["status"] == "PENDING" and task["attempt_count"] == 1
    assert scoped_worker(core_database).run_once() is False
    assert planning_driver.refresh()["current_state"] == "C90_BLOCKED"
    task = planning_driver.read("/agent-tasks")[0]
    assert task["status"] == "FAILED" and task["attempt_count"] == 1
    assert task["result_metadata"]["attempt_limit"] == 1


def test_excluded_plan_does_not_hide_later_requirement(planning_driver, core_database):
    from tests.core.workflow.test_planning_vertical_slice import PlanningDriver

    worker = scoped_worker(core_database)
    assert worker.run_once()
    project_api = planning_driver.chapter_api.rsplit("/chapters/", 1)[0]
    response = planning_driver.client.post(
        project_api + "/chapters", json={"sequence": 2, "title": "Next"}
    )
    assert response.status_code == 201
    second = PlanningDriver(
        planning_driver.client, project_api + "/chapters/" + response.json()["id"]
    )
    assert worker.run_once()
    assert second.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    assert worker.run_once() is False
    assert all(
        t["attempt_count"] == 0
        for t in planning_driver.read("/agent-tasks")
        if t["task_type"] == "PLAN_CHAPTER"
    )


def test_general_worker_cannot_expand_expired_manual_attempt_budget(planning_driver, core_database):
    with core_database.session() as session:
        lease = AgentQueue(session).claim("dead-manual-worker", task_types=SCOPE, max_attempts=1)
    with core_database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_tasks SET lease_expires_at=clock_timestamp()-INTERVAL '1 second',"
                " version=version+1 WHERE task_id=:id"
            ),
            {"id": lease.task_id},
        )
    assert AgentWorker(core_database, AgentRuntime(MockModelProvider())).run_once() is False
    assert planning_driver.refresh()["current_state"] == "C90_BLOCKED"
    task = planning_driver.read("/agent-tasks")[0]
    assert task["attempt_count"] == 1 and task["status"] == "FAILED"
    history = planning_driver.client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs").json()
    assert len(history) == 1 and history[0]["status"] == "ABANDONED"


@pytest.mark.parametrize("expired", [False, True])
def test_scope_excludes_other_stages_even_during_lease_recovery(
    planning_driver, core_database, expired
):
    assert scoped_worker(core_database).run_once()
    plan = next(t for t in planning_driver.read("/agent-tasks") if t["task_type"] == "PLAN_CHAPTER")
    if expired:
        with core_database.session() as session:
            lease = AgentQueue(session).claim("other-worker")
        assert str(lease.task_id) == plan["task_id"]
        with core_database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE agent_tasks SET lease_expires_at=clock_timestamp()-INTERVAL '1 second',"
                    " version=version+1 WHERE task_id=:id"
                ),
                {"id": lease.task_id},
            )
    with core_database.session() as session:
        before = AgentTaskRepository(session).get(UUID(plan["task_id"]))
    assert scoped_worker(core_database).run_once() is False
    with core_database.session() as session:
        assert AgentTaskRepository(session).get(before.task_id) == before


def test_independent_process_reads_scope_and_attempt_limit_from_file(
    planning_driver, core_database, core_settings, tmp_path
):
    config = tmp_path / "worker.toml"
    config.write_text(
        "postgres_url = " + json.dumps(core_settings.postgres_url.get_secret_value()) + "\n"
        'agent_execution_scope = "requirement-only"\nagent_max_attempts = 1\n'
    )
    config.chmod(0o600)
    for _ in range(2):
        process = subprocess.run(
            [sys.executable, "-m", "novel_os.worker", "--once", "--config", str(config)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert process.returncode == 0, "Scoped worker process failed"
    assert planning_driver.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    tasks = planning_driver.read("/agent-tasks")
    assert sum(t["attempt_count"] for t in tasks) == 1
    history = planning_driver.client.get(f"/api/v1/agent-tasks/{tasks[0]['task_id']}/runs").json()
    assert history[0]["input_metadata"]["attempt_limit"] == 1


@pytest.mark.parametrize(
    ("profile", "scope", "task_types"),
    [
        ("lingzhi-requirement", "requirement-only", ["PARSE_CHAPTER_REQUIREMENT"]),
        (
            "lingzhi-structured",
            "chapter-writing",
            [
                "PARSE_CHAPTER_REQUIREMENT",
                "EXPLORE_CHAPTER_CONCEPTS",
                "PLAN_CHAPTER",
                "REVIEW_CHAPTER_PLAN",
                "WRITE_CHAPTER",
            ],
        ),
    ],
)
def test_execution_configuration_exposes_policy_but_no_credentials(
    core_settings, profile, scope, task_types
):
    settings = core_settings.model_copy(
        update={
            "agent_model_profile": profile,
            "agent_execution_scope": scope,
            "agent_max_attempts": 1,
        }
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/agent-execution/config")
    assert response.status_code == 200
    assert response.json() == {
        "model_profile": profile,
        "provider": "lingzhi",
        "model": "gpt-5.6-sol",
        "task_types": task_types,
        "max_attempts": 1,
    }


def test_opening_scope_continues_queued_plan_and_stops_at_human_approval(
    planning_driver, core_database, core_settings
):
    d = planning_driver
    assert scoped_worker(core_database).run_once()
    assert d.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    configured = core_settings.model_copy(
        update={"agent_execution_scope": "chapter-writing", "agent_max_attempts": 1}
    )
    worker = AgentWorker(
        core_database,
        AgentRuntime(MockModelProvider()),
        task_types=configured.agent_task_types,
        max_attempts=configured.agent_max_attempts,
    )
    assert worker.run_once()
    assert d.refresh()["current_state"] == "C05_PLAN_REVIEW"
    assert worker.run_once()
    assert d.refresh()["current_state"] == "C06_PLAN_APPROVAL"
    assert worker.run_once() is False
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] is None
    tasks = d.read("/agent-tasks")
    assert {task["task_type"] for task in tasks} == {
        "PARSE_CHAPTER_REQUIREMENT",
        "PLAN_CHAPTER",
        "REVIEW_CHAPTER_PLAN",
    }
    assert all(task["attempt_count"] == 1 for task in tasks)
    for task in tasks:
        runs = d.client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs").json()
        assert len(runs) == 1 and runs[0]["input_metadata"]["attempt_limit"] == 1


def test_business_scope_skips_earlier_pending_simulation_tasks(
    driver, core_database, core_settings
):
    from tests.core.workflow.test_planning_vertical_slice import PlanningDriver

    assert driver.event("USER_SUBMITTED").status_code == 200
    simulation_task = driver.client.get(driver.url + "/agent-tasks").json()[0]
    assert simulation_task["task_type"] == "MOCK_INTAKE"
    project_api = driver.chapter_api.rsplit("/chapters/", 1)[0]
    response = driver.client.post(project_api + "/chapters", json={"sequence": 2, "title": "Real"})
    assert response.status_code == 201
    business = PlanningDriver(driver.client, project_api + "/chapters/" + response.json()["id"])
    settings = core_settings.model_copy(
        update={"agent_execution_scope": "chapter-writing", "agent_max_attempts": 1}
    )
    worker = AgentWorker(
        core_database,
        AgentRuntime(MockModelProvider()),
        task_types=settings.agent_task_types,
        max_attempts=settings.agent_max_attempts,
    )
    assert worker.run_once()
    assert business.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    unchanged = driver.client.get(f"/api/v1/agent-tasks/{simulation_task['task_id']}").json()
    assert unchanged == simulation_task
    assert driver.client.get(f"/api/v1/agent-tasks/{simulation_task['task_id']}/runs").json() == []
