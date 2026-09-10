import pytest

pytestmark = pytest.mark.integration


def test_decision_reference_ownership_and_lock_scope(core_client, project_api, chapter_api):
    chapter_id = chapter_api.rsplit("/", 1)[1]
    reference = {"object_type": "CHAPTER", "object_id": chapter_id}
    other_id = core_client.post("/api/v1/projects", json={"name": "Other"}).json()["id"]
    body = {"question": "Direction?", "decision": "Stay", "affected_objects": [reference]}
    response = core_client.post(f"/api/v1/projects/{other_id}/decisions", json=body)
    assert response.status_code == 404
    decision = core_client.post(project_api + "/decisions", json=body)
    assert decision.status_code == 201, decision.text
    path = project_api + "/decisions/" + decision.json()["logical_id"]
    lock = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "CHAPTER",
            "target_id": chapter_id,
            "expected_version": 1,
        },
    ).json()
    assert core_client.post(project_api + "/decisions", json=body).status_code == 409
    response = core_client.post(path + "/approve", json={"expected_version": 1})
    assert response.status_code == 409 and response.json()["error"]["code"] == "LOCKED_OBJECT"
    response = core_client.post(
        path + "/versions",
        json={
            "question": "Escape?",
            "decision": "Change",
            "affected_objects": [],
            "expected_version": 1,
        },
    )
    assert response.status_code == 409
    current = core_client.get(chapter_api).json()["version"]
    assert (
        core_client.post(
            project_api + "/locks/" + lock["id"] + "/release", json={"expected_version": current}
        ).status_code
        == 200
    )
    assert core_client.post(path + "/approve", json={"expected_version": 1}).status_code == 200


def test_plan_locked_dependencies_are_checked_again_at_approval(
    core_client, project_api, chapter_api
):
    decision = core_client.post(
        project_api + "/decisions", json={"question": "Voice?", "decision": "First person"}
    ).json()
    reference = {"object_type": "DECISION", "object_id": decision["logical_id"]}
    lock = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "DECISION",
            "target_id": decision["logical_id"],
            "expected_version": 1,
        },
    ).json()
    plan = core_client.post(
        chapter_api + "/plans",
        json={
            "objective": "Arrive",
            "required_outcome": "Meet",
            "expected_version": 0,
            "locked_dependencies": [reference],
        },
    )
    assert plan.status_code == 201, plan.text
    assert (
        core_client.post(
            project_api + "/locks/" + lock["id"] + "/release", json={"expected_version": 1}
        ).status_code
        == 200
    )
    response = core_client.post(chapter_api + "/plans/approve", json={"expected_version": 1})
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"
    assert core_client.get(chapter_api).json()["approved_plan_version"] is None
