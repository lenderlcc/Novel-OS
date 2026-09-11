"""Regressions for upstream invalidation, compound recovery and definition isolation."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from novel_os.models.core import AuditRecordModel
from novel_os.models.workflow import WorkflowInstanceModel
from novel_os.workflow import definitions

pytestmark = pytest.mark.integration


def replace_plan(driver, *, approve=False):
    response = driver.client.post(
        driver.chapter_api + "/plans",
        json={
            "objective": "A different plan",
            "required_outcome": "A different ending",
            "expected_version": 1,
        },
    )
    assert response.status_code == 201, response.text
    if approve:
        response = driver.client.post(
            driver.chapter_api + "/plans/approve",
            json={"expected_version": 2, "reason": "Replace the approved plan"},
        )
        assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "stage,outcome",
    [
        ("C08_DETERMINISTIC_CHECK", "success"),
        ("C08_DETERMINISTIC_CHECK", "review_failure"),
        ("C09_INTERNAL_REVIEW", "success"),
        ("C09_INTERNAL_REVIEW", "review_failure"),
        ("C11_INTERNAL_PASS", "success"),
        ("C12_USER_REVIEW", "success"),
        ("C14_MEMORY_PREPARATION", "success"),
        ("C15_MEMORY_COMMIT", "success"),
    ],
)
def test_approved_plan_change_blocks_old_draft_and_requires_replanning(
    driver, core_database, stage, outcome
):
    driver.advance_to(stage)
    original_draft = driver.client.get(driver.chapter_api + "/versions/1").json()
    original_approved = driver.client.get(driver.chapter_api).json()["approved_version"]
    replace_plan(driver, approve=True)
    if stage == "C12_USER_REVIEW":
        gate = driver.gate()
        url = "/api/v1/human-gates/" + gate["id"] + "/decision"
        body = driver.command(expected_artifact_version=1, decision="APPROVE")
        expected_status = 409
    else:
        url = driver.url + "/fake-execute"
        body = driver.command(origin_state=stage, outcome=outcome)
        expected_status = 200
    response = driver.client.post(url, json=body)
    assert response.status_code == expected_status, response.text
    if expected_status == 409:
        assert response.json()["error"]["code"] == "VERSION_CONFLICT"
        old_gate = next(
            g
            for g in driver.client.get(driver.url + "/human-gates").json()
            if g["id"] == gate["id"]
        )
        assert old_gate["status"] == "STALE"
        assert old_gate["decision"] is None
    blocked = driver.refresh()
    assert blocked["current_state"] == "C90_BLOCKED"
    assert blocked["resume_state"] == "C04_CHAPTER_PLANNING"
    assert blocked["block_reason"] == "VERSION_CONFLICT"
    assert blocked["revision_count"] == 0
    assert driver.client.get(driver.chapter_api + "/versions/1").json() == original_draft
    assert driver.client.get(driver.chapter_api).json()["approved_version"] == original_approved
    history = driver.client.get(driver.url + "/history").json()
    with core_database.session() as session:
        audit_ids = set(session.scalars(select(AuditRecordModel.id)))
    assert driver.client.post(url, json=body).status_code == expected_status
    assert driver.refresh() == blocked
    assert driver.client.get(driver.url + "/history").json() == history
    with core_database.session() as session:
        assert set(session.scalars(select(AuditRecordModel.id))) == audit_ids
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["planning_iteration_count"] == 2
    driver.advance_to("C12_USER_REVIEW")
    chapter = driver.client.get(driver.chapter_api).json()
    assert chapter["current_plan_version"] == chapter["approved_plan_version"] == 3
    assert chapter["current_version"] == 2
    assert chapter["approved_version"] == original_approved
    driver.advance_to("C16_COMPLETED")
    assert driver.client.get(driver.chapter_api).json()["approved_version"] == 2
    old_draft = driver.client.get(driver.chapter_api + "/versions/1").json()
    assert old_draft["id"] == original_draft["id"]
    assert old_draft["content"] == original_draft["content"]
    assert old_draft["approved_at"] == original_draft["approved_at"]


@pytest.mark.parametrize("new_stage", [False, True])
def test_recovery_intent_survives_repeated_lock_blocks(driver, core_database, new_stage):
    driver.advance_to("C07_WRITING")
    for _ in range(2):
        assert driver.fake("technical_failure").status_code == 200
    if new_stage:
        replace_plan(driver)
        assert driver.fake().status_code == 200
    else:
        assert driver.event("BLOCK").status_code == 200
    project_url = "/api/v1/projects/" + driver.workflow["project_id"]
    project = driver.client.get(project_url).json()
    locked = driver.client.post(
        project_url + "/locks",
        json={
            "target_type": "PROJECT",
            "target_id": project["id"],
            "expected_version": project["version"],
            "reason": "Additional blocking condition",
        },
    )
    assert locked.status_code == 201, locked.text
    for _ in range(2):
        body = driver.command()
        assert driver.post("/resume", body).status_code == 200
        blocked = driver.workflow.copy()
        assert blocked["current_state"] == "C90_BLOCKED"
        assert driver.post("/resume", body).status_code == 200
        assert driver.refresh() == blocked
        with core_database.session() as session:
            stored = session.get(WorkflowInstanceModel, UUID(blocked["id"]))
            assert stored.resume_new_stage == new_stage
    project = driver.client.get(project_url).json()
    response = driver.client.post(
        project_url + "/locks/" + locked.json()["id"] + "/release",
        json={"expected_version": project["version"], "reason": "Condition resolved"},
    )
    assert response.status_code == 200, response.text
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["retry_count"] == 2
    assert driver.workflow["planning_iteration_count"] == (2 if new_stage else 1)
    assert driver.workflow["state_retry_count"] == (0 if new_stage else 2)
    assert driver.workflow["current_state"] == (
        "C04_CHAPTER_PLANNING" if new_stage else "C07_WRITING"
    )
    assert driver.fake("technical_failure").status_code == 200
    assert driver.workflow["current_state"] == (
        "C04_CHAPTER_PLANNING" if new_stage else "C91_FAILED"
    )


@pytest.mark.parametrize("definition_file", ["missing", "invalid"])
@pytest.mark.parametrize("finish", ["complete", "cancel"])
def test_persisted_workflow_runs_without_current_yaml(
    driver, monkeypatch, tmp_path, definition_file, finish
):
    driver.advance_to("C06_PLAN_APPROVAL")
    # Redirect only the current packaged YAML, leaving from_body validation intact.
    resource = tmp_path / "definitions" / "chapter-production.v1.yaml"
    if definition_file == "invalid":
        resource.parent.mkdir()
        resource.write_text("transitions: [", encoding="utf-8")
    monkeypatch.setattr(definitions, "files", lambda package: tmp_path)
    original = driver.workflow.copy()
    assert driver.refresh() == original
    assert driver.client.get(driver.url + "/history").status_code == 200
    assert driver.gate()["status"] == "WAITING"
    replay = driver.client.post("/api/v1/workflows/chapter", json=driver.creation)
    assert replay.status_code == 201, replay.text
    assert replay.json()["duplicate"] is True
    assert driver.refresh() == original
    if finish == "complete":
        driver.advance_to("C16_COMPLETED")
    else:
        assert driver.post("/cancel", driver.command()).status_code == 200
        assert driver.workflow["current_state"] == "C92_CANCELLED"
    response = driver.client.post(
        "/api/v1/workflows/chapter", json={**driver.creation, "event_id": str(uuid4())}
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "INVALID_DEFINITION"
