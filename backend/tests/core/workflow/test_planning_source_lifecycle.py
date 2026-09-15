"""Regression tests for derived-source validity, approval and recovery boundaries."""

import pytest

from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider


def post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code < 300, response.text
    return response.json()


def requirement(d, content="全章只能使用第一人称"):
    project = d.chapter_api.split("/chapters/")[0]
    record = post(
        d.client, project + "/requirements", {"content": content, "requirement_type": "MUST"}
    )
    url = project + "/requirements/" + record["logical_id"]
    post(d.client, url + "/approve", {"expected_version": 1})
    return url


def test_brief_source_change_blocks_before_model_and_regenerates(planning_driver, core_database):
    d = planning_driver
    url = requirement(d)
    run_one(core_database, d)
    old = d.read("/creative-brief")
    post(d.client, url + "/supersede", {"expected_version": 1, "content": "全章只能使用第三人称"})
    post(d.client, url + "/approve", {"expected_version": 2})
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
    assert provider.requests == []
    assert d.read("/planning/history")["plans"] == []
    assert d.event("RESUME").status_code == 200
    run_one(core_database, d)
    brief = d.read("/creative-brief")
    assert brief["version"] == 2 and brief["supersedes_id"] == old["id"]
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    constraints = d.read("/planning/plan")["generation"]["body"]["constraints"]
    assert "全章只能使用第三人称" in constraints
    assert "全章只能使用第一人称" not in constraints
    assert d.decide().status_code == 200


def test_gate_source_change_is_stale_and_approval_rolls_back(planning_driver, core_database):
    d = planning_driver
    for _ in range(3):
        run_one(core_database, d)
    gate = d.gate()
    requirement(d)
    response = d.decide()
    assert response.status_code == 409, response.text
    d.refresh()
    assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] is None
    assert d.read("/planning/plan")["plan"]["status"] == "PROPOSED"
    assert next(g for g in d.read("/human-gates") if g["id"] == gate["id"])["status"] == "STALE"
    assert d.event("RESUME").status_code == 200
    for _ in range(3):
        run_one(core_database, d)
    assert d.gate()["id"] != gate["id"]
    assert d.decide().status_code == 200
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] == 2


@pytest.mark.parametrize("stage", ["C05", "C06", "FAIL"])
def test_generated_plan_cannot_use_generic_approval(planning_driver, core_database, stage):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)
    if stage != "C05":
        run_one(core_database, d, "QUALITY_FAIL" if stage == "FAIL" else "SUCCESS")
    response = d.client.post(d.chapter_api + "/plans/approve", json={"expected_version": 1})
    assert response.status_code == 403, response.text
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] is None
    assert d.read("/planning/plan")["plan"]["status"] == "PROPOSED"
    if stage == "C06":
        assert d.decide().status_code == 200


@pytest.mark.parametrize("during_model", [True, False])
def test_plan_drift_recovers_to_replanning(planning_driver, core_database, during_model):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)

    def replace_plan(*_):
        post(
            d.client,
            d.chapter_api + "/plans",
            {"expected_version": 1, "objective": "用户新的计划", "required_outcome": "获得新线索"},
        )

    if not during_model:
        replace_plan()
    provider = RecordedProvider(replace_plan if during_model else None)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.read("/planning/history")["reviews"] == []
    assert d.event("RESUME").status_code == 200
    assert d.workflow["plan_version"] == 2
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.workflow["plan_version"] == 3
    assert d.read("/planning/metrics")["technical_retry_count"] == 0


def locked_previous(client, chapter_api):
    project = chapter_api.split("/chapters/")[0]
    post(
        client,
        chapter_api + "/versions",
        {"expected_version": 0, "content": "主角无法说话。", "change_reason": "Established fact"},
    )
    post(client, chapter_api + "/versions/approve", {"expected_version": 1})
    lock = post(
        client,
        project + "/locks",
        {
            "target_type": "CHAPTER_VERSION",
            "target_id": chapter_api.rsplit("/", 1)[1],
            "expected_version": 1,
        },
    )
    target = post(client, project + "/chapters", {"sequence": 2, "title": "Next chapter"})
    return PlanningDriver(client, project + "/chapters/" + target["id"]), lock


def test_review_reads_exact_locked_previous_body(core_client, chapter_api, core_database):
    d, _ = locked_previous(core_client, chapter_api)
    run_one(core_database, d)
    run_one(core_database, d)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    items = provider.requests[0].context_package.items
    previous = [i for i in items if i.source_type == "CHAPTER_VERSION"]
    assert len(previous) == 1
    assert previous[0].source_version == 1 and previous[0].locked
    assert previous[0].structured_payload["content"] == "主角无法说话。"
    assert previous[0].ref in provider.requests[0].context_package.request.required_refs
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.decide().status_code == 200


@pytest.mark.parametrize("stage", ["before_review", "during_review", "gate"])
def test_released_dependency_blocks_and_can_replan(core_client, chapter_api, core_database, stage):
    d, lock = locked_previous(core_client, chapter_api)
    run_one(core_database, d)
    run_one(core_database, d)
    project = chapter_api.split("/chapters/")[0]

    def release(*_):
        post(d.client, project + "/locks/" + lock["id"] + "/release", {"expected_version": 1})

    if stage == "gate":
        run_one(core_database, d)
        release()
        assert d.decide().status_code == 409
        d.refresh()
        assert d.client.get(d.chapter_api).json()["approved_plan_version"] is None
    else:
        provider = RecordedProvider(release if stage == "during_review" else None)
        if stage == "before_review":
            release()
        run_one(core_database, d, provider=provider)
        if stage == "before_review":
            assert provider.requests == []
        assert d.read("/planning/history")["reviews"] == []
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.event("RESUME").status_code == 200
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.workflow["plan_version"] == 2
    assert d.decide().status_code == 200


@pytest.mark.parametrize("source", ["requirements", "decisions"])
@pytest.mark.parametrize("mutation", ["add", "replace", "remove"])
def test_brief_invalidates_on_effective_source_set_changes(
    planning_driver, core_database, source, mutation
):
    d = planning_driver
    project = d.chapter_api.split("/chapters/")[0]
    fields = (
        {"content": "必须遵守原有约束", "requirement_type": "MUST"}
        if source == "requirements"
        else {"question": "叙事人称", "decision": "第一人称"}
    )
    record = post(d.client, project + "/" + source, fields)
    url = project + "/" + source + "/" + record["logical_id"]
    if mutation == "remove":
        lock = post(
            d.client,
            project + "/locks",
            {
                "target_type": "REQUIREMENT" if source == "requirements" else "DECISION",
                "target_id": record["logical_id"],
                "expected_version": 1,
            },
        )
    elif mutation == "replace":
        post(d.client, url + "/approve", {"expected_version": 1})
    run_one(core_database, d)
    if mutation == "remove":
        post(d.client, project + "/locks/" + lock["id"] + "/release", {"expected_version": 1})
    else:
        version = 1
        if mutation == "replace":
            version = 2
            post(
                d.client,
                url + ("/supersede" if source == "requirements" else "/versions"),
                {
                    "expected_version": 1,
                    **(
                        {"content": "必须遵守新的约束"}
                        if source == "requirements"
                        else {"question": "叙事人称", "decision": "第三人称"}
                    ),
                },
            )
        post(d.client, url + "/approve", {"expected_version": version})
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
    assert provider.requests == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"


def test_unapproved_requirement_draft_does_not_invalidate_brief(planning_driver, core_database):
    d = planning_driver
    url = requirement(d)
    run_one(core_database, d)
    post(d.client, url + "/supersede", {"expected_version": 1, "content": "尚未批准的第三人称"})
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.read("/creative-brief")["version"] == 1
    assert d.decide().status_code == 200
    assert "全章只能使用第一人称" in d.read("/planning/plan")["generation"]["body"]["constraints"]
