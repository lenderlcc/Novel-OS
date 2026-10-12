"""Normal APIs and offline Worker retain goals only for the exact revised Draft."""

from uuid import UUID, uuid4

from novel_os.quality.policy import indexed_paragraphs
from novel_os.repositories.revision import RevisionRepository
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_revision import finish_review
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import post


def test_revision_review_and_manual_rereview_receive_exact_frozen_goals(
    revision_quality_driver,
    core_database,
):
    d = revision_quality_driver
    finish_review(d, core_database, "SUCCESS")
    original = d.client.get(d.chapter_api + "/versions/1").json()
    raw = "合并中间重复解释，保留开头和结尾，不为补足字数扩写。"
    response, _ = submit(d, raw)
    assert response.status_code == 200, response.text
    d.refresh()
    provider = RecordedProvider()
    for _ in range(6):
        run_one(core_database, d, provider=provider)
    assert d.workflow["draft_version"] == 2 and d.workflow["status"] == "WAITING_HUMAN"
    assert d.workflow["revision_request_id"] is None
    revision = d.read("/revisions")[0]
    current = d.client.get(d.chapter_api + "/versions/2").json()

    def check_review_inputs(request):
        items = {i.selector_id: i for i in request.context_package.items}
        payload = items["review-revision-outcome"].structured_payload
        assert str(items["target-version"].source_id) == current["id"]
        assert payload["chapter_version_id"] == current["id"]
        assert payload["source_chapter_version_id"] == original["id"]
        assert payload["source_paragraphs"] == indexed_paragraphs(original["content"])
        assert payload["raw_feedback"] == raw
        assert payload["interpretation"] == revision["request"]["contract"]["interpretation"]
        assert payload["revision_targets"] == revision["plan"]["body"]["revision_targets"]
        assert payload["assessment_status"] == "NOT_INDEPENDENTLY_VERIFIED"
        assert payload["role"] == "DIAGNOSIS_ONLY"
        assert request.context_package.profile_version == 5

    review_requests = [r for r in provider.requests if r.task_type.startswith("REVIEW_CHAPTER_")]
    assert len(review_requests) == 2
    for request in review_requests:
        check_review_inputs(request)
    reviews_before = d.reviews()
    d.post("/quality-review", d.command(expected_draft_version=2))
    rereview = RecordedProvider()
    for _ in range(2):
        run_one(core_database, d, provider=rereview)
    for request in rereview.requests:
        check_review_inputs(request)
    assert d.reviews()[1:] == reviews_before
    assert d.client.get(d.chapter_api + "/versions/1").json() == original

    ids = tuple(UUID(d.workflow[k]) for k in ("project_id", "chapter_id", "id"))
    with core_database.session() as session:
        repo = RevisionRepository(session)
        assert repo.review_evidence(*ids, 1) is None
        assert repo.review_evidence(*ids, 2)[2].chapter_version_id == UUID(current["id"])
        assert repo.review_evidence(ids[0], uuid4(), ids[2], 2) is None
        assert repo.review_evidence(ids[0], ids[1], uuid4(), 2) is None
        assert repo.review_evidence(uuid4(), ids[1], ids[2], 2) is None
    post(
        d.client,
        d.chapter_api + "/versions",
        dict(
            expected_version=2,
            content="人工独立新稿，不继承旧的修订目标。",
            change_reason="人工编辑",
        ),
    )
    d.post("/quality-review", d.command(expected_draft_version=3))
    manual = RecordedProvider()
    for _ in range(2):
        run_one(core_database, d, provider=manual)
    assert all(
        not any(i.selector_id == "review-revision-outcome" for i in r.context_package.items)
        for r in manual.requests
    )
    assert d.workflow["draft_version"] == 3
