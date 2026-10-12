import pytest

from novel_os.agents.runtime import AgentRuntime
from novel_os.worker import AgentWorker
from tests.core.quality.test_revision import finish_review, request_revision
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_illegal_proposal_stops_at_contract_before_persistence(
    revision_quality_driver,
    core_database,
    phase,
):
    d = revision_quality_driver
    request_revision(d, finish_review(d, core_database))
    for _ in range(phase):
        run_one(core_database, d)
    before = d.read("/revisions")

    def corrupt(request, body):
        body["proposed_changes"] = [
            dict(capability="PROPOSE_DRAFT", target_ref=str(request.target_ref))
        ]

    provider = RecordedProvider(corrupt)
    worker = AgentWorker(core_database, AgentRuntime(provider), max_attempts=1)
    assert worker.run_once()
    d.refresh()
    task = d.read("/agent-tasks")[-1]
    assert task["last_error_code"] == "SCHEMA_PARSE_ERROR"
    assert task["status"] == "FAILED"
    assert d.workflow["status"] == "BLOCKED"
    assert d.read("/revisions") == before
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert not worker.run_once()
    assert len(provider.requests) == 1


def test_absent_proposals_complete_revision_with_exact_new_draft_review_binding(
    revision_quality_driver,
    core_database,
):
    d = revision_quality_driver
    review = finish_review(d, core_database)
    source = d.client.get(d.chapter_api + "/versions/1").json()
    request_revision(d, review)

    def absent(_, body):
        body.pop("proposed_changes")
        body.pop("memory_proposals")

    provider = RecordedProvider(absent)
    for phase in range(3):
        run_one(core_database, d, provider=provider)
        task = d.read("/agent-tasks")[-1 if phase == 2 else -2]
        assert task["last_error_code"] is None
    record = d.read("/revisions")[0]
    successor = d.client.get(d.chapter_api + "/versions/2").json()
    assert record["result"]["body"]["fidelity"]["verdict"] == "PASS"
    assert successor["id"] != source["id"]
    assert successor["chapter_id"] == source["chapter_id"]
    assert record["result"]["chapter_version_id"] == successor["id"]
    run_one(core_database, d)
    worker = run_one(core_database, d, "QUALITY_FAIL")
    assert not worker.run_once()
    assert d.reviews()[0]["version"] == 2
    assert d.reviews()[0]["chapter_version_id"] == successor["id"]
    assert d.reviews()[1] == {**review, "freshness": "STALE"}
    assert d.client.get(d.chapter_api + "/versions/1").json() == source
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
