import pytest

from novel_os.agents.planning_schemas import REQUIREMENT_FIELDS
from novel_os.agents.registry import BUSINESS_STAGE_TASKS
from novel_os.repositories.agent_tasks import AgentTaskRepository
from tests.core.workflow.test_context_engine import chapter, post
from tests.core.workflow.test_planning_regressions import reach_gate
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.core.workflow.workflow_test_support import Driver
from tests.planning_support import RecordedProvider


def requirement(driver, category, *, locked=False):
    project = driver.chapter_api.split("/chapters/")[0]
    result = post(
        driver.client,
        project + "/requirements",
        {"content": "保持第一人称叙事，但允许局部视角实验", "requirement_type": category},
    )
    post(
        driver.client,
        project + "/requirements/" + result["logical_id"] + "/approve",
        {"expected_version": 1},
    )
    if locked:
        post(
            driver.client,
            project + "/locks",
            {
                "target_type": "REQUIREMENT",
                "target_id": result["logical_id"],
                "expected_version": 1,
            },
        )
    return result


@pytest.mark.parametrize(
    "field,raw",
    [
        ("must", "必须在本章找到关键线索"),
        ("should", "尽量让冲突通过含蓄的对话展开"),
        ("preferences", "如果合适，可以采用雨夜氛围"),
        ("forbidden", "不能让主角在本章死亡"),
        ("preserve", "保留人物之间已有的信任"),
    ],
)
def test_recorded_language_interpretations_keep_all_five_categories(
    core_client, chapter_api, core_database, field, raw
):
    d = PlanningDriver(core_client, chapter_api, raw)

    def interpretation(request, body):
        brief = body["result"]
        constraint = brief["must"].pop()
        brief[field].append(constraint)

    run_one(core_database, d, provider=RecordedProvider(interpretation))
    brief = d.read("/creative-brief")
    assert brief["body"][field][0]["text"] == raw
    assert brief["raw_requirement"] == raw and brief["status"] == "READY"
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"


@pytest.mark.parametrize("mutation", ["level", "operations"])
def test_planning_cannot_expand_granted_creative_freedom(planning_driver, core_database, mutation):
    d = planning_driver
    run_one(core_database, d)

    def expand(request, body):
        freedom = body["result"]["creative_freedom"]
        if mutation == "level":
            freedom["level"] = "HIGH"
        else:
            freedom["allowed_operations"].append("LOCAL_CONFLICT")

    run_one(core_database, d, provider=RecordedProvider(expand))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "AUTHORITY_DENIED"


@pytest.mark.parametrize(
    "category,field",
    [
        ("MUST", "must"),
        ("SHOULD", "should"),
        ("PREFERENCE", "preferences"),
        ("FORBIDDEN", "forbidden"),
        ("PRESERVE", "preserve"),
        ("QUALITY_EXPECTATION", "quality_expectations"),
        ("CHANGE_REQUEST", "change_requests"),
    ],
)
@pytest.mark.parametrize("mutation", ["omit", "reclassify", "truncate"])
def test_effective_requirement_cannot_be_dropped_or_reinterpreted(
    planning_driver, core_database, category, field, mutation
):
    d = planning_driver
    requirement(d, category, locked=True)

    def mutate(request, body):
        brief = body["result"]
        value = next(c for c in brief[field] if c["source_ref"]["source_type"] == "REQUIREMENT")
        if mutation == "truncate":
            value["text"] = value["quote"] = "保持第一人称叙事"
        else:
            brief[field].remove(value)
            if mutation == "reclassify":
                brief["preferences" if field == "must" else "must"].append(value)

    run_one(core_database, d, provider=RecordedProvider(mutate))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["briefs"] == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "AUTHORITY_DENIED"


@pytest.mark.parametrize("category", list(REQUIREMENT_FIELDS))
def test_all_existing_requirement_types_survive_the_complete_slice(
    planning_driver, core_database, category
):
    d = planning_driver
    source = requirement(d, category)
    reach_gate(core_database, d)
    brief = d.read("/creative-brief")["body"]
    constraint = next(
        c
        for c in brief[REQUIREMENT_FIELDS[category]]
        if c["source_ref"]["source_type"] == "REQUIREMENT"
    )
    assert constraint["text"] == source["content"]
    plan = d.read("/planning/plan")["generation"]["body"]
    assert any(
        c["constraint_id"] == constraint["id"] and c["covered"]
        for c in plan["requirement_coverage"]
    )
    assert d.read("/planning/review")["verdict"] == "PASS"


def test_31_approved_must_requirements_fit_brief_plan_and_review(planning_driver, core_database):
    d = planning_driver
    sources = {requirement(d, "MUST")["logical_id"] for _ in range(31)}
    reach_gate(core_database, d)
    brief = d.read("/creative-brief")["body"]
    assert {
        c["source_ref"]["logical_id"]
        for c in brief["must"]
        if c["source_ref"]["source_type"] == "REQUIREMENT"
    } == sources
    assert len(d.read("/planning/plan")["generation"]["body"]["requirement_coverage"]) == 32
    assert d.read("/planning/review")["verdict"] == "PASS"


def test_locked_requirement_is_preserved_through_brief_plan_and_review(
    planning_driver, core_database
):
    d = planning_driver
    source = requirement(d, "PRESERVE", locked=True)
    reach_gate(core_database, d)
    assert d.read("/creative-brief")["body"]["preserve"][0]["text"] == source["content"]
    deps = d.read("/planning/plan")["generation"]["body"]["locked_dependencies"]
    assert deps == [
        {"source_type": "REQUIREMENT", "logical_id": source["logical_id"], "version": 1}
    ]
    assert d.read("/planning/review")["verdict"] == "PASS"


def test_plan_cannot_omit_locked_requirement(planning_driver, core_database):
    d = planning_driver
    requirement(d, "PRESERVE", locked=True)
    run_one(core_database, d)

    def omit(request, body):
        body["result"]["locked_dependencies"] = []

    run_one(core_database, d, provider=RecordedProvider(omit))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []


def test_requirement_locked_after_plan_requires_fresh_brief_before_review(
    planning_driver, core_database
):
    d = planning_driver
    source = requirement(d, "PRESERVE")
    run_one(core_database, d)
    run_one(core_database, d)
    project = d.chapter_api.split("/chapters/")[0]
    post(
        d.client,
        project + "/locks",
        {"target_type": "REQUIREMENT", "target_id": source["logical_id"], "expected_version": 1},
    )
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
    assert provider.requests == []
    assert d.read("/planning/history")["reviews"] == []
    assert d.read("/human-gates") == []
    assert d.event("RESUME").status_code == 200
    for _ in range(3):
        run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.read("/planning/plan")["plan"]["version"] == 2
    assert d.read("/planning/plan/versions/1")["plan"]["version"] == 1
    assert d.read("/planning/review")["verdict"] == "PASS"


def test_global_preserve_can_pass_without_inventing_a_scene(planning_driver, core_database):
    d = planning_driver
    requirement(d, "PRESERVE")
    run_one(core_database, d)
    constraint = d.read("/creative-brief")["body"]["preserve"][0]

    def global_coverage(request, body):
        entry = next(
            c
            for c in body["result"]["requirement_coverage"]
            if c["constraint_id"] == constraint["id"]
        )
        entry.update(
            scope="PLAN_GLOBAL",
            scene_ids=[],
            explanation="Applies throughout the plan via preserved_elements",
        )

    run_one(core_database, d, provider=RecordedProvider(global_coverage))
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.read("/planning/review")["verdict"] == "PASS"


def test_c07_is_not_backfilled_and_does_not_starve_legacy_workflow(
    planning_driver, core_database, workflow_client, monkeypatch
):
    from novel_os.services.task_scheduling import TaskScheduler

    d = planning_driver
    reach_gate(core_database, d)
    assert d.decide().status_code == 200
    with core_database.session() as session, session.begin():
        assert (
            AgentTaskRepository(session).unscheduled_workflow(
                business_states=tuple(BUSINESS_STAGE_TASKS)
            )
            is None
        )
    project = d.chapter_api.split("/chapters/")[0]
    legacy_chapter = chapter(d.client, project, 2)
    # Simulate a pre-runtime workflow whose stage has no task record yet.
    with monkeypatch.context() as patch:
        patch.setattr(TaskScheduler, "synchronize", lambda *args, **kwargs: None)
        legacy = Driver(workflow_client, legacy_chapter)
        assert legacy.event("USER_SUBMITTED").status_code == 200
    run_one(core_database, legacy)
    assert legacy.workflow["current_state"] == "C02_CONTEXT_ASSEMBLY"
    assert d.refresh()["current_state"] == "C07_WRITING"
