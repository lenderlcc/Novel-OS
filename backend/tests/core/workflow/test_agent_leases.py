from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID

import pytest
from agent_test_support import claim, complete, pending_task, runs, start, task_record, worker
from sqlalchemy import event, text

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import RunStatus, TaskStatus
from novel_os.services.agent_queue import AgentQueue
from novel_os.worker import AgentWorker

pytestmark = pytest.mark.integration


def expire(database, lease):
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_tasks SET lease_expires_at = clock_timestamp() "
                "- INTERVAL '1 second', "
                "version = version + 1 WHERE task_id = :id"
            ),
            {"id": lease.task_id},
        )


def test_two_workers_claim_only_once_using_skip_locked(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    barrier = Barrier(2)
    statements = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        if "SKIP LOCKED" in statement:
            statements.append(statement)

    def competing_claim(name):
        barrier.wait(timeout=5)
        return claim(core_database, name)

    event.listen(core_database.engine, "before_cursor_execute", record_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(competing_claim, ["worker-a", "worker-b"]))
    finally:
        event.remove(core_database.engine, "before_cursor_execute", record_sql)
    winners = [lease for lease in results if lease]
    assert len(winners) == 1
    assert len(runs(core_database, winners[0].task_id)) == 1
    assert any("FOR UPDATE SKIP LOCKED" in sql for sql in statements)


def test_skip_locked_does_not_wait_for_locked_task(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    with core_database.engine.begin() as connection:
        connection.execute(
            text("SELECT task_id FROM agent_tasks WHERE task_id=:id FOR UPDATE"), {"id": task_id}
        )
        assert claim(core_database) is None
    assert claim(core_database) is not None


@pytest.mark.parametrize("started", [False, True])
def test_expired_claim_or_running_task_is_recovered_with_fencing(driver, core_database, started):
    driver.advance_to("C04_CHAPTER_PLANNING")
    old_lease = claim(core_database, "worker-a")
    old_task = (
        start(core_database, old_lease)
        if started
        else task_record(core_database, old_lease.task_id)
    )
    old_output = AgentRuntime(MockModelProvider()).execute(old_task)
    expire(core_database, old_lease)
    new_lease = claim(core_database, "worker-b")
    assert new_lease.task_id == old_lease.task_id
    assert new_lease.token != old_lease.token
    assert new_lease.attempt_number == 2
    new_task = start(core_database, new_lease)
    assert (
        complete(core_database, new_lease, AgentRuntime(MockModelProvider()).execute(new_task))
        == "APPLIED"
    )
    before = task_record(core_database, old_lease.task_id)
    history = runs(core_database, old_lease.task_id)
    assert history[0].status == RunStatus.ABANDONED
    assert history[0].error_code == "LEASE_EXPIRED"
    assert history[1].status == RunStatus.SUCCEEDED
    assert complete(core_database, old_lease, old_output) == "LEASE_LOST"
    with core_database.session() as session:
        assert not AgentQueue(session).heartbeat(old_lease)
    assert task_record(core_database, old_lease.task_id) == before
    assert runs(core_database, old_lease.task_id) == history
    assert driver.refresh()["current_state"] == "C05_PLAN_REVIEW"
    assert len(driver.client.get(driver.chapter_api + "/plans").json()) == 1


def test_expired_lease_cannot_complete_or_renew_before_reclaim(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)
    expire(core_database, lease)
    before = driver.workflow.copy()
    assert (
        complete(core_database, lease, AgentRuntime(MockModelProvider()).execute(task))
        == "LEASE_LOST"
    )
    with core_database.session() as session:
        assert not AgentQueue(session).heartbeat(lease)
    assert driver.refresh() == before


def test_heartbeat_extends_lease_and_wrong_token_is_rejected(driver, core_database):
    from uuid import uuid4

    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    start(core_database, lease)
    before = task_record(core_database, lease.task_id)
    with core_database.session() as session:
        assert not AgentQueue(session).heartbeat(replace(lease, token=uuid4()))
        assert AgentQueue(session).heartbeat(lease)
    after = task_record(core_database, lease.task_id)
    assert after.heartbeat_at > before.heartbeat_at
    assert after.lease_expires_at > before.lease_expires_at
    assert after.version == before.version + 1
    assert claim(core_database, "another") is None


@pytest.mark.parametrize("control", ["cancel", "pause", "advance"])
def test_running_result_is_ignored_after_workflow_changes(driver, core_database, control):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)
    output = AgentRuntime(MockModelProvider()).execute(task)
    if control == "advance":
        assert driver.fake().status_code == 200
    else:
        assert driver.post("/" + control, driver.command()).status_code == 200
    expected = driver.workflow.copy()
    history = driver.client.get(driver.url + "/history").json()
    plans = driver.client.get(driver.chapter_api + "/plans").json()
    assert complete(core_database, lease, output) == "STALE_IGNORED"
    assert driver.refresh() == expected
    assert driver.client.get(driver.url + "/history").json() == history
    assert driver.client.get(driver.chapter_api + "/plans").json() == plans
    run = runs(core_database, lease.task_id)[0]
    assert run.status == RunStatus.SUCCEEDED
    assert run.result_status == "SUCCESS"
    assert run.disposition == "STALE_IGNORED"
    assert task_record(core_database, lease.task_id).status == TaskStatus.CANCELLED


@pytest.mark.parametrize("claimed", [False, True])
def test_cancelled_unstarted_task_cannot_execute(driver, core_database, claimed):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    lease = claim(core_database) if claimed else None
    assert driver.post("/cancel", driver.command()).status_code == 200
    assert task_record(core_database, task_id).status == TaskStatus.CANCELLED
    if claimed:
        assert start(core_database, lease) is None
        assert runs(core_database, task_id)[0].status == RunStatus.CANCELLED
    assert claim(core_database) is None


def test_crash_recovery_exhaustion_does_not_retry_forever(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    for _ in range(3):
        lease = claim(core_database)
        start(core_database, lease)
        expire(core_database, lease)
    assert claim(core_database, "recovery-worker") is None
    assert task_record(core_database, lease.task_id).status == TaskStatus.FAILED
    assert len(runs(core_database, lease.task_id)) == 3
    assert driver.refresh()["current_state"] == "C91_FAILED"


def test_worker_heartbeats_while_provider_runs_outside_transaction(
    driver, core_database, monkeypatch
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    original = AgentQueue.heartbeat
    renewals = []

    def heartbeat(self, lease):
        result = original(self, lease)
        renewals.append(result)
        return result

    monkeypatch.setattr(AgentQueue, "heartbeat", heartbeat)
    provider = MockModelProvider("SLOW_SUCCESS", delay_seconds=1.2)
    executor = AgentWorker(
        core_database, AgentRuntime(provider), lease_seconds=1, heartbeat_seconds=0.1
    )
    assert executor.run_once()
    assert any(renewals)
    assert task_record(core_database, task_id).status == TaskStatus.SUCCEEDED
    assert driver.refresh()["current_state"] == "C05_PLAN_REVIEW"


def test_fresh_worker_resumes_pending_tasks(driver, core_database):
    assert driver.event("USER_SUBMITTED").status_code == 200
    assert worker(core_database, worker_id="first-process").run_once()
    assert worker(core_database, worker_id="second-process").run_once()
    assert driver.refresh()["current_state"] == "C03_REQUIREMENT_READY"
