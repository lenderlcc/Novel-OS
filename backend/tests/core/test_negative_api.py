from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "APPROVED"),
        ("authority_level", "A1_USER_LOCKED"),
        ("approved_at", "2026-09-10T00:00:00Z"),
        ("version", 99),
        ("actor_type", "SYSTEM"),
        ("created_by", "system"),
        ("locked", True),
    ],
)
def test_client_cannot_supply_authority(core_client, project_api, field, value):
    response = core_client.post(
        project_api + "/requirements", json={"content": "Required", field: value}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert core_client.get(project_api + "/requirements").json() == []
    assert len(core_client.get(project_api + "/audit").json()) == 1


@pytest.mark.parametrize(
    "path,body",
    [
        ("", {"name": "Fake project"}),
        ("/decisions", {"question": "Why?", "decision": "Yes"}),
        ("/chapters", {"sequence": 1, "title": "Fake"}),
    ],
)
def test_all_creation_schemas_reject_server_fields(core_client, project_api, path, body):
    target = "/api/v1/projects" if not path else project_api + path
    response = core_client.post(target, json={**body, "authority_level": "A0_SYSTEM_RULE"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "path,body",
    [
        ("/plans", {"objective": "Enter", "required_outcome": "Meet", "expected_version": 0}),
        ("/versions", {"content": "Text", "change_reason": "Draft", "expected_version": 0}),
    ],
)
def test_artifact_creation_cannot_fake_approval(core_client, chapter_api, path, body):
    response = core_client.post(chapter_api + path, json={**body, "status": "APPROVED"})
    assert response.status_code == 422
    assert core_client.get(chapter_api + path).json() == []


def test_actor_headers_are_not_authority(core_client, project_api):
    response = core_client.post(
        project_api + "/decisions",
        json={"question": "Why?", "decision": "Yes"},
        headers={
            "X-Actor-Type": "SYSTEM",
            "X-Actor-ID": "system",
            "X-Authority-Level": "A0_SYSTEM_RULE",
        },
    )
    assert response.status_code == 201
    assert response.json()["source"] == "USER"
    assert response.json()["created_by"] == "local-user"
    assert response.json()["authority_level"] == "A5_USER_PREFERENCE"


@pytest.mark.parametrize("expected", [None, -1, 0, True, "1", 1.5])
def test_approval_requires_explicit_valid_version(core_client, project_api, expected):
    requirement = core_client.post(project_api + "/requirements", json={"content": "Must"}).json()
    body = {} if expected is None else {"expected_version": expected}
    response = core_client.post(
        project_api + "/requirements/" + requirement["logical_id"] + "/approve", json=body
    )
    assert response.status_code == 422


def test_cross_project_targets_are_rejected(core_client, project_api, chapter_api):
    other = core_client.post("/api/v1/projects", json={"name": "Other"}).json()["id"]
    other_path = "/api/v1/projects/" + other
    chapter = chapter_api.rsplit("/", 1)[1]
    response = core_client.post(
        other_path + "/requirements",
        json={
            "content": "Cross-project",
            "scope_type": "CHAPTER",
            "scope_id": chapter,
        },
    )
    assert response.status_code == 404
    response = core_client.post(
        other_path + "/chapters/" + chapter + "/versions",
        json={
            "content": "Bad",
            "change_reason": "Bad",
            "expected_version": 0,
        },
    )
    assert response.status_code == 404
    response = core_client.post(
        other_path + "/locks",
        json={
            "target_type": "CHAPTER",
            "target_id": chapter,
            "expected_version": 1,
        },
    )
    assert response.status_code == 404
    assert core_client.get(other_path + "/chapters/" + chapter + "/plans").status_code == 404


def test_project_lock_blocks_descendant_mutations(core_client, project_api, chapter_api):
    project = project_api.rsplit("/", 1)[1]
    lock = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "PROJECT",
            "target_id": project,
            "expected_version": 1,
        },
    )
    assert lock.status_code == 201
    for path, body in [
        (project_api + "/requirements", {"content": "Must"}),
        (project_api + "/decisions", {"question": "Why?", "decision": "Yes"}),
        (project_api + "/chapters", {"sequence": 2, "title": "Chapter 2"}),
        (
            chapter_api + "/plans",
            {"objective": "Meet", "required_outcome": "Arrive", "expected_version": 0},
        ),
        (
            chapter_api + "/versions",
            {"content": "Text", "change_reason": "Draft", "expected_version": 0},
        ),
    ]:
        response = core_client.post(path, json=body)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LOCKED_OBJECT"
    project_version = core_client.get(project_api).json()["version"]
    response = core_client.post(
        project_api + "/locks/" + lock.json()["id"] + "/release",
        json={"expected_version": project_version},
    )
    assert response.status_code == 200
    assert (
        core_client.post(project_api + "/requirements", json={"content": "Must"}).status_code == 201
    )


def test_chapter_lock_covers_scoped_requirement_and_unlock(core_client, project_api, chapter_api):
    chapter = chapter_api.rsplit("/", 1)[1]
    requirement = core_client.post(
        project_api + "/requirements",
        json={
            "content": "Stay",
            "scope_type": "CHAPTER",
            "scope_id": chapter,
        },
    ).json()
    req_path = project_api + "/requirements/" + requirement["logical_id"]
    req_lock = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "REQUIREMENT",
            "target_id": requirement["logical_id"],
            "expected_version": 1,
        },
    ).json()
    chapter_lock = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "CHAPTER",
            "target_id": chapter,
            "expected_version": 1,
        },
    ).json()
    response = core_client.post(
        project_api + "/locks/" + req_lock["id"] + "/release", json={"expected_version": 1}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "LOCKED_OBJECT"
    version = core_client.get(chapter_api).json()["version"]
    assert (
        core_client.post(
            project_api + "/locks/" + chapter_lock["id"] + "/release",
            json={"expected_version": version},
        ).status_code
        == 200
    )
    assert (
        core_client.post(
            project_api + "/locks/" + req_lock["id"] + "/release", json={"expected_version": 1}
        ).status_code
        == 200
    )
    assert core_client.post(req_path + "/approve", json={"expected_version": 1}).status_code == 200


def test_null_project_update_and_missing_objects(core_client, project_api):
    assert (
        core_client.patch(project_api, json={"name": None, "expected_version": 1}).status_code
        == 422
    )
    assert core_client.get("/api/v1/projects/" + str(uuid4())).status_code == 404
    assert core_client.get(project_api + "/requirements/" + str(uuid4())).status_code == 404
