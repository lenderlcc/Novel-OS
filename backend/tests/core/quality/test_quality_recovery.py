from uuid import UUID, uuid4

import pytest

from novel_os.domain.workflow import ChapterState
from novel_os.models.quality import QualityPassModel
from novel_os.repositories.quality import QualityRepository
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import plan, post


def new_draft(d):
    return post(
        d.client,
        d.chapter_api + "/versions",
        dict(expected_version=1, content="新的正文。\n\n第二段正文。", change_reason="人工修改"),
    )


def request_review(d, version=2, **extra):
    return d.client.post(
        d.url + "/quality-review",
        json=d.command(expected_draft_version=version, reason="人工复审", **extra),
    )


def pass_ids(database):
    from sqlalchemy import select

    with database.session() as session:
        return list(session.scalars(select(QualityPassModel.id)))


@pytest.mark.parametrize("first_pass_complete", [False, True])
@pytest.mark.parametrize("during_model", [False, True])
def test_changed_draft_requires_explicit_version_and_preserves_old_passes(
    quality_driver, core_database, first_pass_complete, during_model
):
    d = quality_driver
    run_one(core_database, d)
    original = d.client.get(d.chapter_api + "/versions/1").json()
    if first_pass_complete:
        run_one(core_database, d)
    old_passes = pass_ids(core_database)
    if not during_model:
        updated = new_draft(d)
    provider = RecordedProvider((lambda *_: new_draft(d)) if during_model else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(during_model)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["draft_version"] == 1
    assert d.reviews() == []
    before = d.refresh()
    assert d.post("/resume", d.command()).status_code == 409
    assert d.post("/resume", d.command(expected_draft_version=1)).status_code == 409
    assert d.refresh() == before

    result = d.post("/resume", d.command(expected_draft_version=2))
    assert result.status_code == 200, result.text
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    assert d.workflow["draft_version"] == 2
    assert d.workflow["resume_state"] is None
    assert d.read("/agent-tasks")[-1]["task_type"] == "REVIEW_CHAPTER_COMPLIANCE"
    for _ in range(2):
        run_one(core_database, d)
    review = d.reviews()[0]
    assert review["binding"]["draft_version"] == 2
    assert review["freshness"] == "CURRENT"
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS"
    assert set(old_passes) <= set(pass_ids(core_database))
    assert review["compliance_pass_id"] not in {str(i) for i in old_passes}
    assert d.client.get(d.chapter_api + "/versions/1").json() == original
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    if not during_model:
        assert review["chapter_version_id"] == updated["id"]


@pytest.mark.parametrize("scenario", ["SUCCESS", "QUALITY_FAIL"])
def test_explicit_rereview_binds_new_draft_and_keeps_old_report(
    quality_driver, core_database, scenario
):
    d = quality_driver
    run_one(core_database, d)
    run_one(core_database, d)
    run_one(core_database, d, scenario)
    first = d.reviews()[0]
    updated = new_draft(d)
    before = d.refresh()
    assert request_review(d, 1).status_code == 409
    assert d.refresh() == before
    command = d.command(expected_draft_version=2, reason="人工复审最新正文")
    result = d.client.post(d.url + "/quality-review", json=command)
    assert result.status_code == 200, result.text
    assert result.json()["workflow"]["draft_version"] == 2
    assert d.client.post(d.url + "/quality-review", json=command).json()["duplicate"]
    for _ in range(2):
        run_one(core_database, d)
    current, historical = d.reviews()
    assert current["freshness"] == "CURRENT"
    assert current["chapter_version_id"] == updated["id"]
    assert historical["id"] == first["id"]
    assert historical["body"] == first["body"]
    assert historical["freshness"] == "STALE"


@pytest.mark.parametrize("phase", ["queued", "between_passes", "completed"])
def test_unapproved_plan_isolated_from_review_freshness(quality_driver, core_database, phase):
    d = quality_driver
    for _ in range({"queued": 1, "between_passes": 2, "completed": 3}[phase]):
        run_one(core_database, d)
    plan(d.client, d.chapter_api, 2, objective="UNAPPROVED_PLAN_SECRET")
    provider = RecordedProvider()
    for _ in range({"queued": 2, "between_passes": 1, "completed": 0}[phase]):
        run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS"
    assert d.reviews()[0]["freshness"] == "CURRENT"
    assert d.reviews()[0]["binding"]["plan_version"] == 1
    for request in provider.requests:
        assert "UNAPPROVED_PLAN_SECRET" not in str(request.context_package)
        assert [
            i.source_version
            for i in request.context_package.items
            if i.selector_id == "approved-plan"
        ] == [1]


def test_changed_approved_plan_still_requires_replanning(quality_driver, core_database):
    d = quality_driver
    run_one(core_database, d)
    plan(d.client, d.chapter_api, 2)
    post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.workflow["current_state"] == "C90_BLOCKED"
    result = d.post("/resume", d.command(expected_draft_version=1))
    assert result.status_code == 200, result.text
    assert result.json()["outcome"] == "BLOCKED"
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.workflow["plan_version"] == 1
    assert d.reviews() == []
    result = d.post("/resume", d.command())
    assert result.status_code == 200, result.text
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"


def test_chapter_title_still_invalidates_review(quality_driver, core_database):
    from dataclasses import replace

    from novel_os.domain.core import now
    from novel_os.repositories.core import CoreRepository

    d = quality_driver
    run_one(core_database, d)
    with core_database.session() as session, session.begin():
        repo = CoreRepository(session)
        current = repo.get_chapter(UUID(d.creation["project_id"]), UUID(d.creation["chapter_id"]))
        repo.save(replace(current, version=current.version + 1, title="新标题", updated_at=now()))
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.reviews() == []


def test_resume_recovers_old_guard_block_without_changing_writing_only_handoff(
    quality_driver, core_database
):
    from dataclasses import replace

    from novel_os.domain.core import now
    from novel_os.repositories.workflows import WorkflowRepository

    d = quality_driver
    run_one(core_database, d)
    new_draft(d)
    run_one(core_database, d)
    # Existing persisted instances from before this fix pointed at C08 on REQUEST_REVIEW.
    with core_database.session() as session, session.begin():
        repo = WorkflowRepository(session)
        w = repo.get(UUID(d.workflow["id"]))
        repo.save(
            replace(
                w,
                resume_state=ChapterState.C08_DETERMINISTIC_CHECK,
                state_version=w.state_version + 1,
                updated_at=now(),
            )
        )
    d.refresh()
    result = d.post("/resume", d.command(expected_draft_version=2))
    assert result.status_code == 200, result.text
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    assert d.workflow["draft_version"] == 2


def test_rebind_rolls_back_state_binding_and_audit_on_failure(
    quality_driver, core_database, monkeypatch
):
    d = quality_driver
    for _ in range(3):
        run_one(core_database, d)
    new_draft(d)
    before = d.refresh()
    history = d.read("/history")
    tasks = d.read("/agent-tasks")
    add = QualityRepository.add

    def fail(self, record):
        add(self, record)
        raise RuntimeError("injected rebind failure")

    command = d.command(expected_draft_version=2)
    with monkeypatch.context() as patch:
        patch.setattr(QualityRepository, "add", fail)
        assert d.client.post(d.url + "/quality-review", json=command).status_code == 500
    assert d.refresh() == before
    assert d.read("/history") == history
    assert d.read("/agent-tasks") == tasks
    result = d.client.post(d.url + "/quality-review", json=command)
    assert result.status_code == 200, result.text
    assert result.json()["workflow"]["draft_version"] == 2


def test_concurrent_explicit_rebind_creates_only_one_review(quality_driver, core_database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from novel_os.domain.core import CommandContext
    from novel_os.domain.errors import DomainError
    from novel_os.domain.workflow import EventCommand
    from novel_os.workflow.runtime import WorkflowRuntime

    d = quality_driver
    for _ in range(3):
        run_one(core_database, d)
    new_draft(d)
    barrier = Barrier(2)

    def rebind(_):
        with core_database.session() as session:
            barrier.wait()
            try:
                result = WorkflowRuntime(session).dispatch_event(
                    UUID(d.workflow["id"]),
                    EventCommand(
                        event_id=uuid4(),
                        event_type="REQUEST_REVIEW",
                        expected_state_version=d.workflow["state_version"],
                        payload={
                            "expected_draft_version": 2,
                            "reason": "explicit concurrent request",
                        },
                    ),
                    CommandContext(str(uuid4()), "local-user"),
                )
                return result.outcome
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(rebind, range(2))) == ["APPLIED", "VERSION_CONFLICT"]
    d.refresh()
    tasks = [
        t
        for t in d.read("/agent-tasks")
        if t["workflow_state_version"] == d.workflow["state_version"]
    ]
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "REVIEW_CHAPTER_COMPLIANCE"


@pytest.mark.parametrize("target", ["PROJECT", "CHAPTER", "CHAPTER_VERSION"])
def test_explicit_review_rebind_honors_locks(quality_driver, core_database, target):
    d = quality_driver
    for _ in range(3):
        run_one(core_database, d)
    updated = new_draft(d)
    project = d.chapter_api.split("/chapters/")[0]
    entity = (
        d.client.get(project if target == "PROJECT" else d.chapter_api).json()
        if target != "CHAPTER_VERSION"
        else updated
    )
    post(
        d.client,
        project + "/locks",
        dict(
            expected_version=entity["version"],
            target_type=target,
            target_id=d.creation["project_id"] if target == "PROJECT" else d.creation["chapter_id"],
            reason="explicit user lock",
        ),
    )
    tasks = d.read("/agent-tasks")
    response = request_review(d)
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "BLOCKED"
    assert response.json()["workflow"]["block_reason"] == "LOCKED_OBJECT"
    assert d.refresh()["draft_version"] == 1
    assert d.read("/agent-tasks") == tasks
    with core_database.session() as session:
        assert QualityRepository(session).latest_binding(UUID(d.workflow["id"])).draft_version == 1
    assert d.client.get(d.chapter_api).json()["approved_version"] is None


def test_legacy_writing_resume_cannot_adopt_a_draft_with_review_token(
    core_client, chapter_api, core_database
):
    from tests.core.writing.conftest import WritingDriver

    d = WritingDriver(core_client, chapter_api).approve_plan(core_database)
    run_one(core_database, d)
    new_draft(d)
    assert d.event("PAUSE").status_code == 200
    before = d.refresh()
    result = d.post("/resume", d.command(expected_draft_version=2))
    assert result.status_code == 422, result.text
    assert d.refresh() == before
    assert d.post("/resume", d.command()).status_code == 200
    assert d.workflow["draft_version"] == 1
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
