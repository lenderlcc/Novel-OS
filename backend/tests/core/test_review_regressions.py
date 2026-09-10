import pytest

pytestmark = pytest.mark.integration


def test_project_update_rejects_too_many_tags_without_persisting(core_client, project_api):
    before = core_client.get(project_api).json()
    audit_before = core_client.get(project_api + "/audit").json()
    response = core_client.patch(
        project_api,
        json={"tags": [f"tag-{index}" for index in range(101)], "expected_version": 1},
    )
    assert response.status_code == 422
    assert core_client.get(project_api).json() == before
    assert core_client.get(project_api + "/audit").json() == audit_before


def test_project_update_preserves_user_reason_in_audit(core_client, project_api):
    reason = "用户确认修改项目标题"
    response = core_client.patch(
        project_api, json={"name": "New title", "expected_version": 1, "reason": reason}
    )
    assert response.status_code == 200
    audit = core_client.get(project_api + "/audit").json()
    assert audit[-1]["action"] == "UPDATE"
    assert audit[-1]["reason"] == reason


@pytest.mark.parametrize("sequence,status", [(2**31, 422), (2**31 - 1, 201)])
def test_chapter_sequence_matches_storage_range(core_client, project_api, sequence, status):
    response = core_client.post(
        project_api + "/chapters", json={"title": "Boundary", "sequence": sequence}
    )
    assert response.status_code == status
    chapters = core_client.get(project_api + "/chapters").json()
    assert [chapter["sequence"] for chapter in chapters] == ([] if status == 422 else [sequence])
