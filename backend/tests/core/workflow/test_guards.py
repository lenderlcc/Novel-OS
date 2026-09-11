from uuid import UUID, uuid4

import pytest

from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType
from novel_os.domain.workflow import ChapterState, EventCommand
from novel_os.workflow.runtime import WorkflowRuntime

pytestmark = pytest.mark.integration


def lock(driver, kind, target, version):
    project = "/api/v1/projects/" + driver.workflow["project_id"]
    response = driver.client.post(
        project + "/locks",
        json={
            "target_type": kind,
            "target_id": target,
            "expected_version": version,
            "reason": "Guard test lock",
        },
    )
    assert response.status_code == 201, response.text
    return project + "/locks/" + response.json()["id"]


def unlock(driver, lock_url, version):
    response = driver.client.post(
        lock_url + "/release", json={"expected_version": version, "reason": "Guard test unlock"}
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("target", ["PROJECT", "CHAPTER", "CHAPTER_PLAN"])
def test_real_lock_blocks_mutation_until_released(driver, target):
    if target == "CHAPTER_PLAN":
        driver.advance_to("C05_PLAN_REVIEW")
        target_id = driver.workflow["chapter_id"]
        version = 1
    else:
        driver.advance_to("C04_CHAPTER_PLANNING")
        target_id = (
            driver.workflow["project_id"] if target == "PROJECT" else driver.workflow["chapter_id"]
        )
        endpoint = "/api/v1/projects/" + target_id if target == "PROJECT" else driver.chapter_api
        version = driver.client.get(endpoint).json()["version"]
    lock_url = lock(driver, target, target_id, version)
    before_state = driver.workflow["current_state"]
    assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    assert driver.workflow["block_reason"] == "LOCKED_OBJECT"
    response = driver.post("/resume", driver.command())
    assert response.status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    # NOVEL-002 Lock changes Project/Chapter version, while artifact version remains immutable.
    if target in {"PROJECT", "CHAPTER"}:
        version = driver.client.get(endpoint).json()["version"]
    unlock(driver, lock_url, version)
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == before_state
    driver.advance_to("C16_COMPLETED")


def test_locked_declared_dependency_is_read_from_domain(driver, core_database):
    project = "/api/v1/projects/" + driver.workflow["project_id"]
    response = driver.client.post(
        project + "/requirements", json={"content": "Preserve this invariant"}
    )
    assert response.status_code == 201, response.text
    requirement = response.json()
    lock_url = lock(driver, "REQUIREMENT", requirement["logical_id"], 1)
    driver.advance_to("C04_CHAPTER_PLANNING")
    with core_database.session() as session:
        result = WorkflowRuntime(session).dispatch_event(
            UUID(driver.workflow["id"]),
            EventCommand(
                event_id=uuid4(),
                event_type="PLAN_READY",
                expected_state_version=driver.workflow["state_version"],
                origin_state=ChapterState.C04_CHAPTER_PLANNING,
                payload={
                    "objective": "Preserve dependency",
                    "required_outcome": "Dependency is locked",
                    "locked_dependencies": [
                        {"object_type": "REQUIREMENT", "object_id": requirement["logical_id"]}
                    ],
                },
            ),
            CommandContext("dependency", "fake", ActorType.AGENT),
        )
    assert result.workflow["current_state"] == "C05_PLAN_REVIEW"
    driver.refresh()
    driver.advance_to("C06_PLAN_APPROVAL")
    unlock(driver, lock_url, 1)
    assert driver.decide().status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None
    lock(driver, "REQUIREMENT", requirement["logical_id"], 1)
    assert driver.post("/resume", driver.command()).status_code == 200
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL"
    driver.advance_to("C16_COMPLETED")
