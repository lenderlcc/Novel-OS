from uuid import uuid4

from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def finish_review(d, database, scenario="QUALITY_FAIL"):
    run_one(database, d)
    run_one(database, d)
    run_one(database, d, scenario)
    assert d.workflow["status"] == "WAITING_HUMAN"
    return d.reviews()[0]


def request_revision(d, review):
    body = dict(
        event_id=str(uuid4()),
        expected_state_version=d.workflow["state_version"],
        expected_draft_version=d.workflow["draft_version"],
        source_review_id=review["id"],
    )
    response = d.client.post(d.url + "/revision", json=body)
    assert response.status_code == 200, response.text
    d.refresh()
    return body


def test_revision_full_slice_stops_after_rereview(revision_quality_driver, core_database):
    d = revision_quality_driver
    review = finish_review(d, core_database)
    before = d.client.get(d.chapter_api + "/versions/1").json()
    chapters_api = d.chapter_api.rsplit("/", 1)[0]
    original_chapter_ids = {item["id"] for item in d.client.get(chapters_api).json()}
    body = request_revision(d, review)
    assert d.workflow["current_state"] == "C10_REVISION" and d.workflow["status"] == "WAITING_AGENT"
    again = d.client.post(d.url + "/revision", json=body)
    assert again.status_code == 200 and again.json()["duplicate"]
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C10_REVISION", d.workflow
    history = d.read("/revisions")
    assert history[0]["plan"]["body"]["preserve_items"]
    assert history[0]["plan"]["body"]["do_not_change"]
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C10_REVISION", d.workflow
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW", d.workflow
    newer = d.client.get(d.chapter_api + "/versions/2").json()
    assert newer["chapter_id"] == before["chapter_id"] == d.workflow["chapter_id"]
    assert newer["id"] != before["id"]
    assert newer["supersedes_id"] == before["id"]
    assert d.client.get(d.chapter_api + "/versions/1").json() == before
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    assert len(d.reviews()) == 1
    run_one(core_database, d)
    worker = run_one(core_database, d, "QUALITY_FAIL")
    assert d.workflow["current_state"] == "C10_REVISION" and d.workflow["status"] == "WAITING_HUMAN"
    assert d.workflow["revision_request_id"] is None
    assert not worker.run_once()
    reviews = d.reviews()
    assert len(reviews) == 2 and reviews[0]["chapter_version_id"] == newer["id"]
    assert reviews[1]["body"] == review["body"]
    assert len(d.read("/revisions")) == 1
    record = d.read("/revisions")[0]
    assert record["request"]["source_chapter_version_id"] == before["id"]
    assert record["request"]["source_review_id"] == review["id"]
    assert {item["id"] for item in d.client.get(chapters_api).json()} == original_chapter_ids
    assert {item["id"] for item in d.client.get(d.chapter_api + "/versions").json()} == {
        before["id"],
        newer["id"],
    }
    assert d.client.get(d.chapter_api).json()["current_version"] == 2
    assert len(d.client.get(d.chapter_api + "/versions").json()) == 2
    for request in provider.requests:
        inputs = {i.selector_id: i for i in request.context_package.items}
        assert inputs["source-quality-review"].structured_payload["strengths"]
        assert (
            inputs["revision-contract"].structured_payload["review_authority"] == "DIAGNOSIS_ONLY"
        )
        assert inputs["target-version"].source_id.hex == before["id"].replace("-", "")
