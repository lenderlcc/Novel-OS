import pytest

from novel_os.agents.runtime import AgentRuntime
from novel_os.quality.policy import indexed_paragraphs
from novel_os.worker import AgentWorker
from tests.core.quality.test_revision import finish_review, request_revision
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


@pytest.mark.parametrize("phase", [0, 2])
def test_wrong_paragraph_stops_plan_or_fidelity_without_changing_current(
    revision_quality_driver,
    core_database,
    phase,
):
    d = revision_quality_driver
    request_revision(d, finish_review(d, core_database))
    for _ in range(phase):
        run_one(core_database, d)
    before = d.read("/revisions")

    def wrong_index(_, body):
        if phase == 0:
            body["result"]["preserve_scene_elements"][0]["evidence"][0]["paragraph_index"] = 999
        else:
            body["result"]["checks"][0]["revised_evidence"][0]["paragraph_index"] = 999

    provider = RecordedProvider(wrong_index)
    worker = AgentWorker(core_database, AgentRuntime(provider), max_attempts=1)
    assert worker.run_once()
    d.refresh()
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "REVISION_EVIDENCE_MISMATCH"
    assert d.workflow["status"] == "BLOCKED"
    assert d.read("/revisions") == before
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert len(provider.requests) == 1
    assert not worker.run_once()


def test_all_revision_stages_receive_full_indexed_source_and_independent_candidate(
    revision_quality_driver,
    core_database,
):
    d = revision_quality_driver
    review = finish_review(d, core_database)
    source = d.client.get(d.chapter_api + "/versions/1").json()
    request_revision(d, review)

    def verify(request, _):
        items = {item.selector_id: item for item in request.context_package.items}
        payload = items["target-version"].structured_payload
        assert payload["content"] == source["content"]
        assert payload["paragraphs"] == indexed_paragraphs(source["content"])
        assert items["target-version"].priority == "P0"
        if request.task_type == "VALIDATE_REVISION_FIDELITY":
            candidate = items["revision-candidate"].structured_payload
            assert candidate["paragraphs"] == indexed_paragraphs(candidate["content"])
            assert candidate["paragraphs"] != payload["paragraphs"]
            assert items["revision-candidate"].priority == "P0"

    provider = RecordedProvider(verify)
    for _ in range(3):
        run_one(core_database, d, provider=provider)
    successor = d.client.get(d.chapter_api + "/versions/2").json()
    assert successor["id"] != source["id"]
    assert d.client.get(d.chapter_api + "/versions/1").json() == source
    run_one(core_database, d)
    worker = run_one(core_database, d)
    assert d.reviews()[0]["chapter_version_id"] == successor["id"]
    assert not worker.run_once()
