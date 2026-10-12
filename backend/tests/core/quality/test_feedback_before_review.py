"""Human instructions bind current prose without requiring an AI Review first."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from sqlalchemy import text

from alembic import command
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.agent_queue import AgentQueue
from tests.core.quality.test_feedback_corrections import ask_question, discard
from tests.core.quality.test_human_feedback import submit
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


@pytest.mark.parametrize("paused", [False, True])
def test_feedback_before_review_runs_existing_revision_slice(
    revision_quality_driver, core_database, paused
):
    d = revision_quality_driver
    d.client._transport.raise_server_exceptions = True
    run_one(core_database, d)
    original = d.client.get(d.chapter_api + "/versions/1").json()
    review_task = d.read("/agent-tasks")[-1]
    assert review_task["status"] == "PENDING"
    if paused:
        assert d.post("/pause", d.command()).status_code == 200
    response, body = submit(d)
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["resume_state"] is None
    assert d.workflow["resume_status"] is None
    assert d.workflow["revision_request_id"] is None
    with core_database.session() as session:
        assert not WorkflowRepository(session).get(UUID(d.workflow["id"])).resume_new_stage
    assert d.workflow["block_reason"] is None
    assert d.client.post(d.url + "/feedback", json=body).json()["duplicate"]
    feedback = d.read("/feedback")[0]["feedback"]
    assert feedback["source_chapter_version_id"] == original["id"]
    assert feedback["source_review_id"] is None
    assert feedback["return_state"] == "C10_REVISION"
    assert (
        next(t for t in d.read("/agent-tasks") if t["task_id"] == review_task["task_id"])["status"]
        == "CANCELLED"
    )
    provider = RecordedProvider()
    for _ in range(6):
        worker = run_one(core_database, d, provider=provider)
    assert d.workflow["status"] == "WAITING_HUMAN", d.workflow
    assert d.workflow["draft_version"] == 2
    assert not worker.run_once()
    assert d.client.get(d.chapter_api + "/versions/1").json() == original
    current = d.client.get(d.chapter_api + "/versions/2").json()
    assert d.reviews()[0]["chapter_version_id"] == current["id"]
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    assert d.workflow["memory_request_id"] is None
    assert [r.task_type for r in provider.requests] == [
        "INTERPRET_CHAPTER_FEEDBACK",
        "PLAN_CHAPTER_REVISION",
        "REVISE_CHAPTER",
        "VALIDATE_REVISION_FIDELITY",
        "REVIEW_CHAPTER_COMPLIANCE",
        "REVIEW_CHAPTER_NARRATIVE",
    ]


@pytest.mark.parametrize("exit_action", ["discard", "NO_CHANGE", "USER_DECISION_REQUIRED"])
def test_pre_review_feedback_can_return_to_idle_and_accept_followup(
    revision_quality_driver, core_database, exit_action
):
    d = revision_quality_driver
    run_one(core_database, d)
    assert submit(d)[0].status_code == 200
    d.refresh()
    reply = {}
    if exit_action == "discard":
        discard(d)
    else:

        def interpret(request, body):
            if exit_action == "USER_DECISION_REQUIRED":
                ask_question(request, body)
            else:
                body["result"].update(
                    action="NO_CHANGE", change_impact="NONE", requested_changes=[]
                )

        run_one(core_database, d, provider=RecordedProvider(interpret))
        if exit_action == "USER_DECISION_REQUIRED":
            reply = {"reply_to_feedback_id": d.read("/feedback")[0]["feedback"]["id"]}
    assert d.workflow["current_state"] == "C10_REVISION"
    assert d.workflow["status"] == "WAITING_HUMAN"
    assert d.workflow["human_feedback_id"] is None
    assert d.workflow["memory_request_id"] is None
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    assert not d.read("/revisions")
    response, _ = submit(d, "只调整写法，保留故事结果。", **reply)
    assert response.status_code == 200, response.text


def test_completed_revision_can_receive_feedback_before_rereview(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    run_one(core_database, d)
    assert submit(d)[0].status_code == 200
    d.refresh()
    for _ in range(4):
        run_one(core_database, d)
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    assert d.workflow["revision_request_id"]
    draft = d.client.get(d.chapter_api + "/versions/2").json()
    response, _ = submit(d)
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["revision_request_id"] is None
    assert d.read("/feedback")[0]["feedback"]["source_chapter_version_id"] == draft["id"]
    assert len(d.read("/revisions")) == 1


@pytest.mark.parametrize("running", [False, True])
def test_feedback_does_not_interrupt_claimed_or_running_review(
    revision_quality_driver, core_database, running
):
    d = revision_quality_driver
    run_one(core_database, d)
    before = d.workflow.copy()
    with core_database.session() as session:
        lease = AgentQueue(session).claim("feedback-test")
    assert lease is not None
    if running:
        with core_database.session() as session:
            assert AgentQueue(session).start(lease) is not None
    response, _ = submit(d)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INVALID_STATE"
    assert d.refresh() == before
    assert d.read("/feedback") == []
    assert d.read("/agent-tasks")[-1]["status"] == ("RUNNING" if running else "CLAIMED")


def test_review_claim_and_feedback_serialize_on_existing_project_lock(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    run_one(core_database, d)
    task_id = UUID(d.read("/agent-tasks")[-1]["task_id"])

    def claim():
        with core_database.session() as session:
            return AgentQueue(session).claim("feedback-race", task_ids=[task_id])

    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted = pool.submit(submit, d)
        claimed = pool.submit(claim)
        response, _ = submitted.result()
        lease = claimed.result()
    if lease is None:
        assert response.status_code == 200, response.text
        assert d.refresh()["current_state"] == "C13_USER_FEEDBACK_DIAGNOSIS"
        assert d.read("/agent-tasks")[-1]["task_type"] == "INTERPRET_CHAPTER_FEEDBACK"
    else:
        assert response.status_code == 409, response.text
        assert lease.task_id == task_id
        assert d.refresh()["current_state"] == "C09_INTERNAL_REVIEW"
        assert not d.read("/feedback")


def test_feedback_admission_migration_roundtrip_preserves_draft_and_feedback(
    revision_quality_driver, core_database, migration_config
):
    d = revision_quality_driver
    run_one(core_database, d)
    original = d.client.get(d.chapter_api + "/versions/1").json()
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        current_guard = connection.scalar(
            text("SELECT pg_get_functiondef('novel_feedback_relations()'::regprocedure)")
        )
        command.downgrade(migration_config, "-1")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0021_writing_output_contract"
        )
    assert submit(d)[0].status_code == 409
    assert not d.read("/feedback")
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(
                text("SELECT pg_get_functiondef('novel_feedback_relations()'::regprocedure)")
            )
            == current_guard
        )
    response, _ = submit(d)
    assert response.status_code == 200, response.text
    feedback = d.read("/feedback")
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "-1")
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    assert d.read("/feedback") == feedback
    assert d.client.get(d.chapter_api + "/versions/1").json() == original
