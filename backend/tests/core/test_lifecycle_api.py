import pytest

pytestmark = pytest.mark.integration


def post(client, path, data, expected=200):
    response = client.post(path, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def test_requirement_approval_and_supersession(core_client, project_api):
    requirement = post(core_client, project_api + "/requirements", {"content": "Keep mystery"}, 201)
    path = project_api + "/requirements/" + requirement["logical_id"]
    assert requirement["version"] == 1 and requirement["status"] == "PROPOSED"
    approved = post(core_client, path + "/approve", {"expected_version": 1})
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == "local-user" and approved["approved_at"]
    response = core_client.patch(path, json={"content": "Overwrite", "expected_version": 1})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    v2 = post(
        core_client, path + "/supersede", {"content": "New direction", "expected_version": 1}, 201
    )
    assert v2["version"] == 2 and v2["status"] == "PROPOSED"
    assert v2["supersedes_id"] == approved["id"]
    old = core_client.get(path + "/versions/1").json()
    assert old["content"] == "Keep mystery" and old["status"] == "APPROVED"
    effective = core_client.get(project_api + "/requirements?effective=true").json()
    assert [item["id"] for item in effective] == [approved["id"]]
    conflict = post(core_client, path + "/approve", {"expected_version": 1}, 409)
    assert conflict["error"]["code"] == "VERSION_CONFLICT"
    post(core_client, path + "/approve", {"expected_version": 2})
    old = core_client.get(path + "/versions/1").json()
    assert old["status"] == "SUPERSEDED" and old["content"] == "Keep mystery"
    assert old["approved_at"] == approved["approved_at"]
    assert len(core_client.get(path + "/versions").json()) == 2
    audit = core_client.get(project_api + "/audit").json()
    assert [row["action"] for row in audit] == [
        "CREATE",
        "VERSION_CREATE",
        "APPROVE",
        "VERSION_CREATE",
        "SUPERSEDE",
        "APPROVE",
    ]
    assert all(row["actor_type"] == "USER" and row["request_id"] for row in audit)


def test_decision_lock_unlock_and_history(core_client, project_api):
    decision = post(
        core_client,
        project_api + "/decisions",
        {
            "question": "Who narrates?",
            "decision": "First person",
        },
        201,
    )
    path = project_api + "/decisions/" + decision["logical_id"]
    post(core_client, path + "/approve", {"expected_version": 1})
    lock = post(
        core_client,
        project_api + "/locks",
        {
            "target_type": "DECISION",
            "target_id": decision["logical_id"],
            "expected_version": 1,
            "reason": "Keep voice",
        },
        201,
    )
    locked = core_client.get(path).json()
    assert locked["locked"] and locked["authority_level"] == "A1_USER_LOCKED"
    for method, suffix in [("patch", ""), ("post", "/versions")]:
        response = getattr(core_client, method)(
            path + suffix,
            json={
                "question": "Who narrates?",
                "decision": "Third person",
                "expected_version": 1,
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LOCKED_OBJECT"
    released = post(
        core_client,
        project_api + "/locks/" + lock["id"] + "/release",
        {
            "expected_version": 1,
            "reason": "Reconsider",
        },
    )
    assert not released["active"] and released["released_by"] == "local-user"
    unlocked = core_client.get(path).json()
    assert unlocked["status"] == "APPROVED" and unlocked["authority_level"] == "A2_USER_APPROVED"
    v2 = post(
        core_client,
        path + "/versions",
        {
            "question": "Who narrates?",
            "decision": "Third person",
            "expected_version": 1,
        },
        201,
    )
    assert v2["version"] == 2
    post(core_client, path + "/approve", {"expected_version": 2})
    assert core_client.get(path + "/versions/1").json()["decision"] == "First person"
    audit = core_client.get(project_api + "/audit").json()
    assert {"LOCK", "UNLOCK", "VERSION_CREATE", "APPROVE", "SUPERSEDE"} <= {
        r["action"] for r in audit
    }


def test_plan_and_chapter_version_pointers(core_client, project_api, chapter_api):
    duplicate = post(
        core_client, project_api + "/chapters", {"sequence": 1, "title": "Duplicate"}, 409
    )
    assert duplicate["error"]["code"] == "DUPLICATE_CHAPTER_SEQUENCE"
    plan1 = post(
        core_client,
        chapter_api + "/plans",
        {
            "objective": "Arrive",
            "required_outcome": "Find the letter",
            "expected_version": 0,
        },
        201,
    )
    post(core_client, chapter_api + "/plans/approve", {"expected_version": 1})
    plan2 = post(
        core_client,
        chapter_api + "/plans",
        {
            "objective": "Investigate",
            "required_outcome": "Find the author",
            "expected_version": 1,
        },
        201,
    )
    assert plan2["supersedes_id"] == plan1["id"]
    assert core_client.get(chapter_api + "/plans/1").json()["objective"] == "Arrive"
    stale = post(core_client, chapter_api + "/plans/approve", {"expected_version": 1}, 409)
    assert stale["error"]["code"] == "VERSION_CONFLICT"
    chapter = core_client.get(chapter_api).json()
    assert chapter["current_plan_version"] == 2 and chapter["approved_plan_version"] == 1
    post(core_client, chapter_api + "/plans/approve", {"expected_version": 2})
    v1 = post(
        core_client,
        chapter_api + "/versions",
        {
            "content": "Original text",
            "change_reason": "First draft",
            "expected_version": 0,
        },
        201,
    )
    post(core_client, chapter_api + "/versions/approve", {"expected_version": 1})
    v2 = post(
        core_client,
        chapter_api + "/versions",
        {
            "content": "Revised text",
            "change_reason": "Second draft",
            "expected_version": 1,
        },
        201,
    )
    assert v2["version"] == 2 and v2["parent_version_id"] == v1["id"]
    chapter = core_client.get(chapter_api).json()
    assert chapter["current_version"] == 2 and chapter["approved_version"] == 1
    post(core_client, chapter_api + "/versions/approve", {"expected_version": 2})
    chapter = core_client.get(chapter_api).json()
    assert chapter["current_version"] == chapter["approved_version"] == 2
    old = core_client.get(chapter_api + "/versions/1").json()
    assert old["content"] == "Original text" and old["status"] == "SUPERSEDED"
    assert (
        core_client.patch(chapter_api + "/versions/1", json={"content": "overwrite"}).status_code
        == 405
    )
    audit = core_client.get(project_api + "/audit").json()
    for target in (plan1, plan2, v1, v2):
        records = [row for row in audit if row["target_id"] == target["id"]]
        assert {"VERSION_CREATE", "APPROVE"} <= {row["action"] for row in records}
        assert all(row["target_version"] == target["version"] for row in records)
    chapter_updates = [
        row for row in audit if row["target_type"] == "CHAPTER" and row["action"] == "UPDATE"
    ]
    assert len(chapter_updates) == 8
    assert [row["target_version"] for row in chapter_updates] == list(range(2, 10))
    assert chapter_updates[-1]["before"]["approved_version"] == 1
    assert chapter_updates[-1]["after"]["approved_version"] == 2


def test_project_crud_is_versioned_and_soft_delete(core_client, project_api):
    response = core_client.patch(project_api, json={"name": "Renamed", "expected_version": 1})
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        core_client.patch(project_api, json={"name": "Stale", "expected_version": 1}).status_code
        == 409
    )
    response = core_client.request("DELETE", project_api, json={"expected_version": 2})
    assert response.status_code == 200 and response.json()["status"] == "ARCHIVED"
    assert core_client.get(project_api).status_code == 200
    assert (
        post(core_client, project_api + "/requirements", {"content": "New"}, 409)["error"]["code"]
        == "INVALID_STATE"
    )
