from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState, EventCommand
from novel_os.models.core import AuditRecordModel, ChapterPlanModel, ChapterVersionModel
from novel_os.models.workflow import HumanGateModel, WorkflowEventModel, WorkflowTransitionModel
from novel_os.workflow.fake_executor import FakeExecutor
from novel_os.workflow.runtime import WorkflowRuntime

pytestmark = pytest.mark.integration


def counts(database):
    with database.session() as session:
        return {
            m.__tablename__: session.scalar(select(func.count()).select_from(m))
            for m in (
                AuditRecordModel,
                ChapterPlanModel,
                ChapterVersionModel,
                HumanGateModel,
                WorkflowEventModel,
                WorkflowTransitionModel,
            )
        }


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_type", "SYSTEM"),
        ("actor_id", "system"),
        ("status", "APPROVED"),
        ("authority_level", "A1_USER_LOCKED"),
        ("next_state", "C07_WRITING"),
        ("approved", True),
        ("version", 99),
    ],
)
def test_http_cannot_forge_server_fields(driver, field, value):
    body = driver.command(event_type="USER_SUBMITTED", **{field: value})
    assert driver.post("/events", body).status_code == 422
    assert driver.workflow["state_version"] == 1


@pytest.mark.parametrize("actor", [ActorType.AGENT, ActorType.SYSTEM])
def test_non_user_cannot_approve_gate(driver, core_database, actor):
    driver.advance_to("C06_PLAN_APPROVAL")
    gate = driver.gate()
    from novel_os.domain.workflow import GateDecision

    with core_database.session() as session, pytest.raises(DomainError, match="requires a user"):
        WorkflowRuntime(session).decide_gate(
            UUID(gate["id"]),
            uuid4(),
            driver.workflow["state_version"],
            gate["artifact_version"],
            GateDecision.APPROVE,
            "fake approval",
            CommandContext("test", "agent", actor),
        )
    assert driver.gate()["status"] == "WAITING"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None


def test_event_payload_cannot_bypass_actual_approval(driver, core_database):
    driver.advance_to("C06_PLAN_APPROVAL")
    with core_database.session() as session:
        runtime = WorkflowRuntime(session)
        with pytest.raises(DomainError) as error:
            runtime.dispatch_event(
                UUID(driver.workflow["id"]),
                EventCommand(
                    event_id=uuid4(),
                    event_type="USER_APPROVED",
                    expected_state_version=driver.workflow["state_version"],
                    payload={"approved": True},
                ),
                CommandContext("guard-test", "user"),
            )
        assert error.value.code == "HUMAN_GATE_REQUIRED"
        with session.begin():
            instance = runtime.repo.get(UUID(driver.workflow["id"]))
            failure = runtime.guards.check("plan_approved", instance)
            assert failure.code == "APPROVAL_REQUIRED"
    assert driver.refresh()["current_state"] == "C06_PLAN_APPROVAL"
    assert driver.decide().status_code == 200
    assert driver.workflow["current_state"] == "C07_WRITING"
    with core_database.session() as session:
        record = session.scalar(select(ChapterPlanModel))
        assert record.status == Status.APPROVED
        assert record.approved_by == "local-user"
        assert record.approved_at is not None


def test_stale_gate_approval_is_conflict_and_recovers_through_replanning(driver):
    driver.advance_to("C06_PLAN_APPROVAL")
    gate = driver.gate()
    body = driver.command(decision="APPROVE", expected_artifact_version=1)
    response = driver.client.post(
        driver.chapter_api + "/plans",
        json={
            "objective": "Plan v2",
            "required_outcome": "Another plan",
            "expected_version": 1,
            "reason": "new proposal",
        },
    )
    assert response.status_code == 201, response.text
    path = "/api/v1/human-gates/" + gate["id"] + "/decision"
    assert driver.client.post(path, json=body).status_code == 409
    assert driver.refresh()["current_state"] == "C90_BLOCKED"
    assert driver.client.get(driver.url + "/human-gates").json()[0]["status"] == "STALE"
    assert driver.client.post(path, json=body).status_code == 409
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    driver.advance_to("C16_COMPLETED")
    assert driver.workflow["plan_version"] == 3


def test_changed_plan_blocks_writing_even_with_previously_approved_plan(driver):
    driver.advance_to("C07_WRITING")
    response = driver.client.post(
        driver.chapter_api + "/plans",
        json={
            "objective": "new",
            "required_outcome": "new",
            "expected_version": 1,
            "reason": "revise",
        },
    )
    assert response.status_code == 201, response.text
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["approved_plan_version"] == 1
    assert chapter["current_version"] is None


def test_duplicate_events_and_gate_decisions_have_no_duplicate_effects(driver, core_database):
    before = counts(core_database)
    created = driver.client.post("/api/v1/workflows/chapter", json=driver.creation)
    assert created.status_code == 201
    assert created.json()["duplicate"] is True
    assert counts(core_database) == before
    driver.advance_to("C04_CHAPTER_PLANNING")
    body = driver.command(origin_state=driver.workflow["current_state"])
    first = driver.post("/fake-execute", body)
    assert first.status_code == 200
    before = counts(core_database)
    second = driver.post("/fake-execute", body)
    assert second.json()["duplicate"] is True
    assert second.json()["workflow"] == first.json()["workflow"]
    assert counts(core_database) == before
    driver.advance_to("C06_PLAN_APPROVAL")
    gate = driver.gate()
    body = driver.command(decision="APPROVE", expected_artifact_version=gate["artifact_version"])
    path = "/api/v1/human-gates/" + gate["id"] + "/decision"
    first = driver.client.post(path, json=body)
    assert first.status_code == 200
    before = counts(core_database)
    second = driver.client.post(path, json=body)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert counts(core_database) == before
    body["event_id"] = str(uuid4())
    body["expected_state_version"] = first.json()["workflow"]["state_version"]
    assert driver.client.post(path, json=body).status_code == 409


def test_event_id_cannot_be_reused_for_different_command(driver):
    body = driver.command(event_type="USER_SUBMITTED")
    assert driver.post("/events", body).status_code == 200
    body["event_type"] = "CANCEL"
    response = driver.post("/events", body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("control", ["cancel", "pause"])
def test_stale_executor_result_cannot_advance_or_create_artifact(driver, core_database, control):
    driver.advance_to("C04_CHAPTER_PLANNING")
    with core_database.session() as session:
        result = FakeExecutor().execute(WorkflowRuntime(session).get(UUID(driver.workflow["id"])))
    driver.post("/" + control, driver.command())
    before = counts(core_database)
    with core_database.session() as session:
        result = WorkflowRuntime(session).dispatch_event(
            UUID(driver.workflow["id"]),
            result,
            CommandContext("late-result", "fake", ActorType.AGENT),
        )
    assert result.outcome == "STALE_IGNORED"
    after = counts(core_database)
    assert after["workflow_events"] == before["workflow_events"] + 1
    for table in before.keys() - {"workflow_events"}:
        assert after[table] == before[table]
    assert driver.refresh()["current_state"] == (
        "C92_CANCELLED" if control == "cancel" else "C04_CHAPTER_PLANNING"
    )


def test_old_result_after_leaving_and_returning_same_state_is_stale(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    with core_database.session() as session:
        old = FakeExecutor().execute(WorkflowRuntime(session).get(UUID(driver.workflow["id"])))
    driver.fake()
    driver.fake("review_failure")
    assert driver.workflow["current_state"] == old.origin_state
    with core_database.session() as session:
        ignored = WorkflowRuntime(session).dispatch_event(
            UUID(driver.workflow["id"]), old, CommandContext("old", "fake", ActorType.AGENT)
        )
    assert ignored.outcome == "STALE_IGNORED"
    assert driver.refresh()["plan_version"] == 1


def test_transaction_rolls_back_artifact_transition_and_all_audits(
    driver, core_database, monkeypatch
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    before = counts(core_database)
    with core_database.session() as session:
        runtime = WorkflowRuntime(session)
        with session.begin():
            command = FakeExecutor().execute(runtime.get(UUID(driver.workflow["id"])))

        def fail(*args, **kwargs):
            raise RuntimeError("Simulated audit storage failure")

        monkeypatch.setattr(runtime.audit, "record", fail)
        with pytest.raises(RuntimeError, match="audit storage failure"):
            runtime.dispatch_event(
                UUID(driver.workflow["id"]),
                command,
                CommandContext("rollback", "fake", ActorType.AGENT),
            )
    assert counts(core_database) == before
    assert driver.refresh()["current_state"] == "C04_CHAPTER_PLANNING"
    assert driver.client.get(driver.chapter_api).json()["current_plan_version"] is None


def test_gate_approval_rollback_restores_domain_and_gate(driver, core_database, monkeypatch):
    from novel_os.domain.workflow import GateDecision

    driver.advance_to("C06_PLAN_APPROVAL")
    gate = driver.gate()
    before = counts(core_database)
    with core_database.session() as session:
        runtime = WorkflowRuntime(session)

        def fail(*args, **kwargs):
            raise RuntimeError("Transition storage failure")

        monkeypatch.setattr(runtime.audit, "record", fail)
        with pytest.raises(RuntimeError, match="Transition storage failure"):
            runtime.decide_gate(
                UUID(gate["id"]),
                uuid4(),
                driver.workflow["state_version"],
                1,
                GateDecision.APPROVE,
                "approve",
                CommandContext("rollback", "user"),
            )
    assert counts(core_database) == before
    assert driver.gate()["status"] == "WAITING"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None


def test_fake_executor_disabled_by_default(core_client, driver):
    response = core_client.post(
        driver.url + "/fake-execute", json=driver.command(origin_state="C00_CREATED")
    )
    assert response.status_code == 404


def test_service_cannot_accept_executor_next_state(driver, core_database):
    driver.advance_to("C01_REQUIREMENT_INTAKE")
    with core_database.session() as session:
        with session.begin():
            command = FakeExecutor().execute(
                WorkflowRuntime(session).get(UUID(driver.workflow["id"]))
            )
        command = replace(command, payload={"next_state": "C16_COMPLETED"})
        with pytest.raises(DomainError) as error:
            WorkflowRuntime(session).dispatch_event(
                UUID(driver.workflow["id"]),
                command,
                CommandContext("fake", "fake", ActorType.AGENT),
            )
        assert error.value.code == "VALIDATION_ERROR"
    assert driver.refresh()["current_state"] == ChapterState.C01_REQUIREMENT_INTAKE


def test_changed_accepted_draft_goes_back_through_review(driver):
    driver.advance_to("C14_MEMORY_PREPARATION")
    response = driver.client.post(
        driver.chapter_api + "/versions",
        json={"content": "New body", "change_reason": "User revision", "expected_version": 1},
    )
    assert response.status_code == 201, response.text
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["current_version"] == 2
    assert chapter["approved_version"] == 1
    driver.advance_to("C16_COMPLETED")
    assert driver.client.get(driver.chapter_api).json()["approved_version"] == 2
    history = driver.client.get(driver.chapter_api + "/versions").json()
    assert len(history) == 2


def test_stale_fake_http_result_reports_version_conflict(driver):
    driver.advance_to("C04_CHAPTER_PLANNING")
    body = driver.command(origin_state="C04_CHAPTER_PLANNING")
    driver.post("/cancel", driver.command())
    response = driver.post("/fake-execute", body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    assert driver.refresh()["current_state"] == "C92_CANCELLED"
