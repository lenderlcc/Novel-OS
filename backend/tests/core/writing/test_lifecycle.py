from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from novel_os.agents.runtime import AgentRuntime
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.agent_results import AgentResultHandler
from novel_os.worker import AgentWorker
from tests.core.workflow.test_planning_source_lifecycle import requirement
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import plan, post


def prepare(database, provider=None):
    runtime = AgentRuntime(provider or RecordedProvider())
    with database.session() as session:
        lease = AgentQueue(session).claim("writing-test", profile_for_task=runtime.profile_for_task)
    with database.session() as session:
        task = AgentQueue(session).start(lease)
    execution = AgentWorker(database, runtime).prepare_and_execute(task, lease)
    assert execution.error_code is None, execution
    return lease, task, execution


def deliver(database, lease, execution):
    with database.session() as session:
        return AgentResultHandler(session, retry_seconds=0).complete(lease, execution)


@pytest.mark.parametrize("during_model", [False, True])
def test_exact_approved_plan_survives_new_current_draft(ready_writer, core_database, during_model):
    d = ready_writer

    def propose(*_):
        plan(d.client, d.chapter_api, 2, objective="UNAPPROVED_PLAN_V2_SECRET")

    if not during_model:
        propose()
    provider = RecordedProvider(propose if during_model else None)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK", d.workflow
    package = provider.requests[0].context_package
    selected = [i for i in package.items if i.source_type == "CHAPTER_PLAN"]
    assert len(selected) == 1 and selected[0].source_version == 1
    assert "UNAPPROVED_PLAN_V2_SECRET" not in str(package)
    assert d.read("/writing/history")[0]["plan_id"] == str(selected[0].source_id)
    chapter = d.client.get(d.chapter_api).json()
    assert chapter["current_plan_version"] == 2 and chapter["approved_plan_version"] == 1


def test_e2e_b_new_draft_preserves_approved_body_then_regeneration(writing_driver, core_database):
    d = writing_driver
    post(
        d.client,
        d.chapter_api + "/versions",
        dict(expected_version=0, content="APPROVED_BODY_V1", change_reason="prior draft"),
    )
    post(d.client, d.chapter_api + "/versions/approve", dict(expected_version=1))
    d.approve_plan(core_database)
    run_one(core_database, d)
    c = d.client.get(d.chapter_api).json()
    assert (c["current_version"], c["approved_version"]) == (2, 1)
    v2 = d.client.get(d.chapter_api + "/versions/2").json()
    command = dict(
        event_id=str(uuid4()),
        expected_state_version=d.workflow["state_version"],
        expected_draft_version=2,
        reason="再生成一个版本",
    )
    result = d.client.post(d.url + "/writing/regenerate", json=command)
    assert result.status_code == 200, result.text
    assert d.client.post(d.url + "/writing/regenerate", json=command).json()["duplicate"] is True
    run_one(core_database, d)
    c = d.client.get(d.chapter_api).json()
    assert (c["current_version"], c["approved_version"]) == (3, 1)
    assert d.client.get(d.chapter_api + "/versions/2").json() == v2
    assert d.client.get(d.chapter_api + "/versions/1").json()["content"] == "APPROVED_BODY_V1"
    records = d.read("/writing/history")
    assert len(records) == 2
    assert len({r["agent_task_id"] for r in records}) == 2
    assert len({r["chapter_version_id"] for r in records}) == 2


@pytest.mark.parametrize("scenario", ["FORMAT_ERROR_ONCE", "MODEL_ERROR_ONCE"])
def test_technical_retry_same_task_new_runs_one_version(ready_writer, core_database, scenario):
    d = ready_writer
    run_one(core_database, d, scenario)
    task = d.read("/agent-tasks")[-1]
    assert task["status"] == "PENDING" and task["attempt_count"] == 1
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []
    run_one(core_database, d, scenario)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    done = d.read("/agent-tasks")[-1]
    assert done["task_id"] == task["task_id"] and done["attempt_count"] == 2
    assert len(d.read("/writing/history")) == 1
    with core_database.session() as session:
        assert (
            session.scalar(
                text("SELECT count(*) FROM agent_runs WHERE task_id=:task"),
                {"task": UUID(task["task_id"])},
            )
            == 2
        )
    assert len(d.client.get(d.chapter_api + "/versions").json()) == 1


@pytest.mark.parametrize(
    "change", ["approval", "requirement", "lock", "chapter_lock", "cancel", "pause", "draft"]
)
def test_e2e_d_changed_input_or_workflow_discards_inflight_result(
    ready_writer, core_database, change
):
    d = ready_writer
    lease, task, execution = prepare(core_database)
    if change == "approval":
        plan(d.client, d.chapter_api, 2)
        post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
    elif change == "requirement":
        requirement(d)
    elif change in {"lock", "chapter_lock"}:
        c = d.client.get(d.chapter_api).json()
        post(
            d.client,
            d.chapter_api.split("/chapters/")[0] + "/locks",
            dict(
                target_type="CHAPTER_PLAN" if change == "lock" else "CHAPTER",
                target_id=d.workflow["chapter_id"],
                expected_version=1 if change == "lock" else c["version"],
            ),
        )
    elif change == "draft":
        post(
            d.client,
            d.chapter_api + "/versions",
            dict(expected_version=0, content="Concurrent user draft", change_reason="other writer"),
        )
    else:
        assert d.event(change.upper()).status_code == 200
    disposition = deliver(core_database, lease, execution)
    assert disposition == ("STALE_IGNORED" if change in {"cancel", "pause"} else "BLOCKED")
    assert d.read("/writing/history") == []
    versions = d.client.get(d.chapter_api + "/versions").json()
    assert len(versions) == (1 if change == "draft" else 0)
    assert not any(v["source"] == "AGENT" for v in versions)


@pytest.mark.parametrize("when", ["before_build", "before_provider"])
def test_no_model_call_when_approval_disappears(ready_writer, core_database, monkeypatch, when):
    d = ready_writer

    def replace(*_):
        plan(d.client, d.chapter_api, 2)
        post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))

    if when == "before_build":
        replace()
    else:
        from novel_os.services.prompt_lineages import PromptLineageService

        original = PromptLineageService.bind

        def bind(self, *args):
            result = original(self, *args)
            replace()
            return result

        monkeypatch.setattr(PromptLineageService, "bind", bind)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.read("/writing/history") == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"


def test_two_concurrent_deliveries_create_one_draft(ready_writer, core_database):
    d = ready_writer
    lease, _, execution = prepare(core_database)
    barrier = Barrier(2)

    def complete(_):
        barrier.wait(timeout=5)
        return deliver(core_database, lease, execution)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(complete, range(2))) == ["APPLIED", "DUPLICATE"]
    assert len(d.read("/writing/history")) == 1
    assert [v["version"] for v in d.client.get(d.chapter_api + "/versions").json()] == [1]
    assert d.refresh()["current_state"] == "C08_DETERMINISTIC_CHECK"


def test_stale_regeneration_expected_version_rejected(ready_writer, core_database):
    d = ready_writer
    run_one(core_database, d)
    response = d.client.post(
        d.url + "/writing/regenerate",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            expected_draft_version=2,
        ),
    )
    assert response.status_code == 409
    assert len(d.read("/writing/history")) == 1
    assert d.refresh()["current_state"] == "C08_DETERMINISTIC_CHECK"


def test_unapproved_plan_has_no_writing_task(writing_driver, core_database):
    d = writing_driver
    for _ in range(3):
        run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert all(t["task_type"] != "WRITE_CHAPTER" for t in d.read("/agent-tasks"))
    assert d.client.get(d.chapter_api + "/versions").json() == []


def test_concurrent_user_regeneration_creates_only_one_next_version(ready_writer, core_database):
    from novel_os.domain.core import CommandContext
    from novel_os.domain.errors import DomainError
    from novel_os.domain.workflow import EventCommand
    from novel_os.workflow.runtime import WorkflowRuntime

    d = ready_writer
    run_one(core_database, d)
    barrier = Barrier(2)

    def regenerate(index):
        barrier.wait(timeout=5)
        try:
            with core_database.session() as session:
                result = WorkflowRuntime(session).dispatch_event(
                    UUID(d.workflow["id"]),
                    EventCommand(
                        event_id=uuid4(),
                        event_type="REGENERATE_DRAFT",
                        expected_state_version=d.workflow["state_version"],
                        payload={"expected_draft_version": 1, "reason": "another draft"},
                    ),
                    CommandContext(str(uuid4()), "user"),
                )
            return result.outcome
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(regenerate, range(2))) == ["APPLIED", "VERSION_CONFLICT"]
    run_one(core_database, d)
    assert sorted(v["version"] for v in d.client.get(d.chapter_api + "/versions").json()) == [1, 2]
    assert len(d.read("/writing/history")) == 2


def test_changed_approved_plan_recovers_through_replanning(ready_writer, core_database):
    d = ready_writer
    plan(d.client, d.chapter_api, 2)
    post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
    run_one(core_database, d)
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.event("RESUME").status_code == 200
    assert d.workflow["plan_version"] == 2
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.decide().status_code == 200
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert d.read("/writing/history")[0]["plan_version"] == 3


@pytest.mark.parametrize("suspend", ["BLOCK", "PAUSE"])
def test_plan_changed_while_suspended_routes_to_replanning(ready_writer, core_database, suspend):
    d = ready_writer
    assert d.event(suspend).status_code == 200
    plan(d.client, d.chapter_api, 2)
    post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
    # First resume records the newly discovered stale dependency and recovery stage.
    assert d.event("RESUME").status_code == 200
    d.refresh()
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.event("RESUME").status_code == 200
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.workflow["plan_version"] == 2


def test_requirement_correction_cannot_restart_c08(ready_writer, core_database):
    d = ready_writer
    run_one(core_database, d)
    response = d.post(
        "/requirement", d.command(expected_brief_version=1, raw_requirement="后续章节需求")
    )
    assert response.status_code == 409
    assert d.refresh()["current_state"] == "C08_DETERMINISTIC_CHECK"


def test_regeneration_can_read_locked_approved_plan(ready_writer, core_database):
    d = ready_writer
    run_one(core_database, d)
    post(
        d.client,
        d.chapter_api.split("/chapters/")[0] + "/locks",
        dict(target_type="CHAPTER_PLAN", target_id=d.workflow["chapter_id"], expected_version=1),
    )
    response = d.client.post(
        d.url + "/writing/regenerate",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            expected_draft_version=1,
        ),
    )
    assert response.status_code == 200, response.text
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    plan_item = next(
        i for i in provider.requests[0].context_package.items if i.selector_id == "approved-plan"
    )
    assert plan_item.source_version == 1 and plan_item.locked
    assert len(d.read("/writing/history")) == 2


@pytest.mark.parametrize(
    "field", ["status", "authority_level", "approved_at", "version", "actor_type"]
)
def test_user_cannot_inject_authority_into_writing_workflow(writing_driver, field):
    d = writing_driver
    response = d.client.post(
        "/api/v1/workflows/chapter-writing",
        json={**d.creation, "event_id": str(uuid4()), field: "APPROVED"},
    )
    assert response.status_code == 422
    response = d.client.post(
        d.url + "/writing/regenerate",
        json={
            "event_id": str(uuid4()),
            "expected_state_version": d.workflow["state_version"],
            "expected_draft_version": 1,
            field: "APPROVED",
        },
    )
    assert response.status_code == 422
