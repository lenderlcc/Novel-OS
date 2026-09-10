from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

pytestmark = pytest.mark.integration


def test_two_requests_cannot_create_same_next_chapter_version(core_client, chapter_api):
    response = core_client.post(
        chapter_api + "/versions",
        json={
            "content": "Version 1",
            "change_reason": "Initial",
            "expected_version": 0,
        },
    )
    assert response.status_code == 201
    assert (
        core_client.post(
            chapter_api + "/versions/approve", json={"expected_version": 1}
        ).status_code
        == 200
    )
    barrier = Barrier(2)

    def submit(index):
        barrier.wait(timeout=5)
        return core_client.post(
            chapter_api + "/versions",
            json={
                "content": f"Competing draft {index}",
                "change_reason": "Concurrent edit",
                "expected_version": 1,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, [1, 2]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["error"]["code"] == "VERSION_CONFLICT"
    versions = core_client.get(chapter_api + "/versions").json()
    assert [version["version"] for version in versions] == [1, 2]
    chapter = core_client.get(chapter_api).json()
    assert chapter["current_version"] == 2 and chapter["approved_version"] == 1
