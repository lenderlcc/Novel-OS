from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from agent_test_support import claim, complete, pending_task, runs, start, task_record, worker
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import AgentTask, TaskStatus
from novel_os.models.agents import AgentRunModel
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.services.task_history import TaskHistory
from novel_os.services.task_scheduling import TaskScheduler

pytestmark = pytest.mark.integration


def test_repository_flushes_without_commit_or_rollback(driver, core_database, monkeypatch):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    before = task_record(core_database, task_id)
    with core_database.session() as session:
        monkeypatch.setattr(session, "commit", lambda: pytest.fail("Repository committed"))
        monkeypatch.setattr(session, "rollback", lambda: pytest.fail("Repository rolled back"))
        repository = AgentTaskRepository(session)
        changed = replace(
            before,
            version=before.version + 1,
            available_at=before.available_at + timedelta(seconds=1),
        )
        repository.save(changed)
        assert repository.get(task_id) == changed
        assert task_record(core_database, task_id) == before
        assert session.in_transaction()
    assert task_record(core_database, task_id) == before


def test_stale_task_snapshot_cannot_overwrite_new_claim(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    stale = task_record(core_database, task_id)
    lease = claim(core_database)
    before = task_record(core_database, task_id)
    with pytest.raises(IntegrityError), core_database.session() as session:
        AgentTaskRepository(session).save(replace(stale, version=stale.version + 1))
    assert task_record(core_database, task_id) == before
    assert len(runs(core_database, lease.task_id)) == 1


def test_logical_task_identity_is_database_unique(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task = task_record(core_database, UUID(pending_task(driver)["task_id"]))
    with pytest.raises(IntegrityError), core_database.session() as session:
        AgentTaskRepository(session).add(replace(task, task_id=uuid4()))


@pytest.mark.parametrize(
    "assignment",
    [
        "workflow_state_version = workflow_state_version + 1",
        "capabilities = '[\"APPROVE\"]'::jsonb",
        "agent_id = 'A01_ORCHESTRATOR'",
        "task_type = 'FORGED'",
        "max_attempts = max_attempts + 1",
    ],
)
def test_task_identity_and_authority_scope_are_immutable(driver, core_database, assignment):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    before = task_record(core_database, task_id)
    with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE agent_tasks SET version = version + 1, {assignment} WHERE task_id=:id"),
            {"id": task_id},
        )
    assert task_record(core_database, task_id) == before


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE agent_runs SET output_metadata = '{}'::jsonb",
        "UPDATE agent_runs SET error_message = 'rewritten'",
        "UPDATE agent_tasks SET version = version + 1 WHERE status = 'SUCCEEDED'",
        "DELETE FROM agent_runs",
        "DELETE FROM agent_tasks",
    ],
)
def test_completed_execution_history_is_immutable(driver, core_database, sql):
    driver.advance_to("C04_CHAPTER_PLANNING")
    assert worker(core_database).run_once()
    with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
        connection.execute(text(sql))


def test_task_audit_failure_rolls_back_workflow_transition(driver, core_database, monkeypatch):
    before = driver.workflow.copy()
    original = TaskHistory.audit

    def fail_task_audit(self, task, old, new, context, reason):
        original(self, task, old, new, context, reason)
        raise RuntimeError("injected task audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(TaskHistory, "audit", fail_task_audit)
        assert driver.event("USER_SUBMITTED").status_code == 500
    assert driver.refresh() == before
    assert driver.client.get(driver.url + "/agent-tasks").json() == []
    assert driver.event("USER_SUBMITTED").status_code == 200


def test_claim_failure_rolls_back_task_run_and_audit(driver, core_database, monkeypatch):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    before = task_record(core_database, task_id)
    original = TaskHistory.audit

    def fail_run_audit(self, task, old, new, context, reason):
        original(self, task, old, new, context, reason)
        if not isinstance(new, AgentTask):
            raise RuntimeError("injected run audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(TaskHistory, "audit", fail_run_audit)
        with pytest.raises(RuntimeError, match="injected"):
            claim(core_database)
    assert task_record(core_database, task_id) == before
    assert runs(core_database, task_id) == []


def test_completion_failure_rolls_back_artifact_workflow_task_run_and_audit(
    driver, core_database, monkeypatch
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    workflow = driver.workflow.copy()
    history = driver.client.get(driver.url + "/history").json()
    lease = claim(core_database)
    task = start(core_database, lease)
    run_history = runs(core_database, task.task_id)
    execution = AgentRuntime(MockModelProvider()).execute(task)
    original = TaskHistory.finish_run

    def fail_after_finish(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after artifact and run creation")

    with monkeypatch.context() as patch:
        patch.setattr(TaskHistory, "finish_run", fail_after_finish)
        with pytest.raises(RuntimeError, match="injected"):
            complete(core_database, lease, execution)
    assert driver.refresh() == workflow
    assert driver.client.get(driver.url + "/history").json() == history
    assert task_record(core_database, task.task_id) == task
    assert runs(core_database, task.task_id) == run_history
    assert driver.client.get(driver.chapter_api + "/plans").json() == []
    assert complete(core_database, lease, execution) == "APPLIED"
    assert len(driver.client.get(driver.chapter_api + "/plans").json()) == 1


def test_concurrent_delivery_creates_one_artifact_and_transition(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)
    execution = AgentRuntime(MockModelProvider()).execute(task)
    barrier = Barrier(2)

    def deliver(_):
        barrier.wait(timeout=5)
        return complete(core_database, lease, execution)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(deliver, range(2))) == ["APPLIED", "DUPLICATE"]
    assert driver.refresh()["state_version"] == task.workflow_state_version + 1
    assert len(driver.client.get(driver.chapter_api + "/plans").json()) == 1
    with core_database.session() as session:
        assert len(session.scalars(select(AgentRunModel)).all()) == 1


def test_queue_respects_priority_and_available_at(driver, core_database, monkeypatch):
    original = TaskScheduler.synchronize

    def enqueue(test_driver, priority, delay=0):
        with monkeypatch.context() as patch:
            patch.setattr(
                TaskScheduler,
                "synchronize",
                lambda self, workflow, context: original(
                    self, workflow, context, priority=priority, delay_seconds=delay
                ),
            )
            assert test_driver.event("USER_SUBMITTED").status_code == 200
        return UUID(pending_task(test_driver)["task_id"])

    def another_driver():
        project = driver.client.post("/api/v1/projects", json={"name": "Queue priority"}).json()
        url = "/api/v1/projects/" + project["id"] + "/chapters"
        chapter = driver.client.post(url, json={"sequence": 1, "title": "First"}).json()
        return type(driver)(driver.client, url + "/" + chapter["id"])

    low = enqueue(driver, -10)
    high = enqueue(another_driver(), 10)
    future = enqueue(another_driver(), 100, 60)
    assert claim(core_database).task_id == high
    assert claim(core_database).task_id == low
    assert claim(core_database) is None
    assert task_record(core_database, future).status == TaskStatus.PENDING
