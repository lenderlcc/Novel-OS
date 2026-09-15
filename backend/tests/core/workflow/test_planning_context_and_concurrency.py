from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import select

from novel_os.agents.runtime import AgentRuntime
from novel_os.models.planning import PlanGenerationModel
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.agent_results import AgentResultHandler
from novel_os.worker import AgentWorker
from tests.core.workflow.test_context_engine import chapter, plan, post
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider


def test_previous_approved_body_and_exact_brief_are_selected(
    core_client, chapter_api, core_database
):
    for version in (1, 2, 3):
        post(
            core_client,
            chapter_api + "/versions",
            {
                "expected_version": version - 1,
                "content": f"Body v{version}",
                "change_reason": "Context fixture",
            },
        )
        if version == 2:
            post(core_client, chapter_api + "/versions/approve", {"expected_version": 2})
    project = chapter_api.split("/chapters/")[0]
    target = chapter(core_client, project, 2)
    d = PlanningDriver(core_client, target)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert not any(
        item.source_type == "CHAPTER_VERSION" for item in provider.requests[0].context_package.items
    )
    run_one(core_database, d, provider=provider)
    package = provider.requests[1].context_package
    bodies = [item for item in package.items if item.source_type == "CHAPTER_VERSION"]
    assert (
        len(bodies) == 1
        and bodies[0].source_version == 2
        and bodies[0].structured_payload["content"] == "Body v2"
    )
    briefs = [item for item in package.items if item.source_type == "CREATIVE_BRIEF"]
    assert len(briefs) == 1 and briefs[0].priority == "P0"
    assert package.profile_id == "CP-004" and package.profile_version == 3


def test_locked_decision_is_p0_and_omission_blocks_plan(planning_driver, core_database):
    d = planning_driver
    project = d.chapter_api.split("/chapters/")[0]
    decision = post(
        d.client, project + "/decisions", {"question": "人物边界", "decision": "主角不能背叛同伴"}
    )
    post(
        d.client,
        project + "/locks",
        {"target_type": "DECISION", "target_id": decision["logical_id"], "expected_version": 1},
    )
    run_one(core_database, d)

    def omit_lock(request, body):
        body["result"]["locked_dependencies"] = []

    provider = RecordedProvider(omit_lock)
    run_one(core_database, d, provider=provider)
    locked = next(
        i for i in provider.requests[0].context_package.items if i.source_type == "DECISION"
    )
    assert locked.priority == "P0" and locked.locked and locked.authority_level == "A1_USER_LOCKED"
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "AUTHORITY_DENIED"


def test_superseded_brief_is_never_selected_for_new_plan(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    old = d.read("/creative-brief")
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.decide("MODIFY", reason="过时的旧方向返工指令").status_code == 200
    assert (
        d.post(
            "/requirement",
            d.command(expected_brief_version=1, raw_requirement="寻找证据，但不揭露幕后人物"),
        ).status_code
        == 200
    )
    run_one(core_database, d)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    brief = next(
        i for i in provider.requests[0].context_package.items if i.source_type == "CREATIVE_BRIEF"
    )
    assert brief.source_version == 2 and str(brief.source_id) != old["id"]
    items = provider.requests[0].context_package.items
    assert not any(i.source_type in {"CHAPTER_PLAN", "PLAN_REVIEW_REPORT"} for i in items)
    task = next(i for i in items if i.source_type == "TASK_INPUT")
    assert task.structured_payload["requirements"] == []
    assert d.read("/planning/plan")["plan"]["version"] == 2
    assert len(d.read("/planning/history")["plans"]) == 2


def test_new_current_plan_invalidates_inflight_review_context(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)

    def create_new_plan(request, body):
        plan(d.client, d.chapter_api, 2, objective="Concurrent user proposal")

    run_one(core_database, d, provider=RecordedProvider(create_new_plan))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["reviews"] == []
    assert d.read("/human-gates") == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"


def test_two_deliveries_create_only_one_next_plan_version(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    runtime = AgentRuntime(RecordedProvider())
    with core_database.session() as session:
        lease = AgentQueue(session).claim(
            "concurrent-business-test", profile_for_task=runtime.profile_for_task
        )
    with core_database.session() as session:
        task = AgentQueue(session).start(lease)
    execution = AgentWorker(core_database, runtime).prepare_and_execute(task, lease)
    assert execution.error_code is None
    barrier = Barrier(2)

    def deliver(_):
        barrier.wait(timeout=5)
        with core_database.session() as session:
            return AgentResultHandler(session).complete(lease, execution)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(deliver, range(2))) == ["APPLIED", "DUPLICATE"]
    with core_database.session() as session:
        assert len(session.scalars(select(PlanGenerationModel)).all()) == 1
    assert len(d.client.get(d.chapter_api + "/plans").json()) == 1
    assert d.refresh()["plan_version"] == 1


def test_cross_project_input_and_artifact_reference_rejected(planning_driver, core_database):
    d = planning_driver
    project = post(d.client, "/api/v1/projects", {"name": "Other project"})
    response = d.client.post(
        "/api/v1/workflows/chapter-planning",
        json={**d.creation, "event_id": str(uuid4()), "project_id": project["id"]},
    )
    assert response.status_code == 404

    def foreign_ref(request, body):
        body["result"]["source_refs"][0]["logical_id"] = project["id"]

    run_one(core_database, d, provider=RecordedProvider(foreign_ref))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["briefs"] == []


def test_plan_lock_blocks_business_generation(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.decide("REJECT").status_code == 200
    project = d.chapter_api.split("/chapters/")[0]
    lock = post(
        d.client,
        project + "/locks",
        {
            "target_type": "CHAPTER_PLAN",
            "target_id": d.workflow["chapter_id"],
            "expected_version": 1,
        },
    )
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert len(d.read("/planning/history")["plans"]) == 1
    post(d.client, project + "/locks/" + lock["id"] + "/release", {"expected_version": 1})
    assert d.event("RESUME").status_code == 200
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C05_PLAN_REVIEW"
    assert len(d.read("/planning/history")["plans"]) == 2
