from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from novel_os.repositories.revision import RevisionRepository
from tests.core.quality.test_revision import finish_review, request_revision
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.core.writing.test_lifecycle import deliver, prepare
from tests.planning_support import RecordedProvider
from tests.writing_support import plan, post


@pytest.fixture
def revision_driver(revision_quality_driver, core_database):
    d = revision_quality_driver
    request_revision(d, finish_review(d, core_database))
    return d


@pytest.mark.parametrize("phase", ["plan", "execution"])
@pytest.mark.parametrize("scenario", ["BLOCKED", "NEEDS_HUMAN"])
def test_safe_block_is_terminal_evidence_not_provider_retry(
    revision_driver, core_database, phase, scenario
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    worker = run_one(core_database, d, scenario)
    task = d.read("/agent-tasks")[-1]
    assert task["status"] == "BLOCKED" and task["last_error_code"] is None
    assert d.workflow["current_state"] == "C90_BLOCKED"
    record = d.read("/revisions")[0][phase if phase == "plan" else "candidate"]
    assert record["body"]["blocked_reasons"]
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert d.post("/resume", d.command()).status_code == 409
    assert not worker.run_once()


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_low_confidence_cannot_resume_into_duplicate_artifact(
    revision_driver, core_database, phase
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    run_one(
        core_database, d, provider=RecordedProvider(lambda _, body: body.update(confidence=0.1))
    )
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.post("/resume", d.command()).status_code == 409
    assert d.client.get(d.chapter_api).json()["current_version"] == 1


@pytest.mark.parametrize("phase", ["plan", "execution"])
@pytest.mark.parametrize(
    "field", ["source_review_id", "source_chapter_version_id", "source_refs", "preserve", "issue"]
)
def test_forged_revision_output_rejected(revision_driver, core_database, phase, field):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    before = d.read("/revisions")

    def corrupt(_, body):
        result = body["result"]
        if field in {"source_review_id", "source_chapter_version_id"}:
            result[field] = str(uuid4())
        elif field == "source_refs":
            result[field][0]["source_id"] = str(uuid4())
        elif field == "preserve":
            result["preserve_items" if phase == "plan" else "preserved_items"] = [
                "invented commitment"
            ]
        elif phase == "plan":
            result["revision_targets"][0]["issue_id"] = str(uuid4())
        else:
            result["addressed_issue_ids"] = [str(uuid4())]

    run_one(core_database, d, provider=RecordedProvider(corrupt))
    assert d.read("/revisions") == before
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "SCHEMA_PARSE_ERROR"
    assert d.client.get(d.chapter_api).json()["current_version"] == 1


@pytest.mark.parametrize(
    "capability",
    ["PROPOSE_PLAN", "PROPOSE_REQUIREMENT", "COMMIT_CANON", "LOCK", "APPROVE", "PROPOSE_DRAFT"],
)
def test_revision_cannot_write_authority_domains(revision_driver, core_database, capability):
    d = revision_driver
    before_plan = d.client.get(d.chapter_api + "/plans/1").json()
    before_brief = d.read("/creative-brief")

    def corrupt(request, body):
        body["proposed_changes"] = [dict(capability=capability, target_ref=str(request.target_ref))]

    run_one(core_database, d, provider=RecordedProvider(corrupt))
    assert d.read("/revisions")[0]["plan"] is None
    assert d.read("/agent-tasks")[-1]["last_error_code"] in {
        "AUTHORITY_DENIED",
        "SCHEMA_PARSE_ERROR",
    }
    assert d.client.get(d.chapter_api + "/plans/1").json() == before_plan
    assert d.read("/creative-brief") == before_brief


@pytest.mark.parametrize("phase", ["plan", "execution"])
@pytest.mark.parametrize("during_model", [False, True])
@pytest.mark.parametrize("change_kind", ["draft", "plan", "profile", "lock"])
def test_changed_authority_rejects_pending_or_returned_result(
    revision_driver, core_database, phase, during_model, change_kind
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    before = d.read("/revisions")

    def change(*_):
        if change_kind == "draft":
            post(
                d.client,
                d.chapter_api + "/versions",
                dict(expected_version=1, content="新的人工作品", change_reason="测试版本变更"),
            )
        elif change_kind == "plan":
            plan(d.client, d.chapter_api, 2)
            post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
        elif change_kind == "profile":
            from tests.core.test_writing_profiles import approve, draft

            project = d.chapter_api.split("/chapters/")[0]
            draft(d.client, project, 1, target_audience="新批准受众")
            approve(d.client, project, 2)
        else:
            chapter = d.client.get(d.chapter_api).json()
            post(
                d.client,
                d.chapter_api.split("/chapters/")[0] + "/locks",
                dict(
                    expected_version=chapter["version"],
                    target_type="CHAPTER",
                    target_id=chapter["id"],
                    reason="用户锁定",
                ),
            )

    if not during_model:
        change()
    provider = RecordedProvider(change if during_model else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(during_model)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/revisions") == before
    assert d.client.get(d.chapter_api).json()["current_version"] == (
        2 if change_kind == "draft" else 1
    )


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_retry_then_duplicate_delivery_creates_one_artifact(revision_driver, core_database, phase):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    run_one(core_database, d, "MODEL_ERROR_ONCE")
    assert d.read("/agent-tasks")[-1]["status"] == "PENDING"
    lease, task, execution = prepare(core_database)
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert deliver(core_database, lease, execution) == "DUPLICATE"
    d.refresh()
    records = d.read("/revisions")
    assert len(records) == 1 and records[0]["plan"] is not None
    assert (records[0]["candidate"] is not None) == (phase == "execution")
    assert d.client.get(d.chapter_api).json()["current_version"] == (1)


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_worker_recovery_fences_old_result(revision_driver, core_database, phase):

    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    old_lease, _, old_output = prepare(core_database)
    with core_database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_tasks SET lease_expires_at=clock_timestamp()-INTERVAL '1 second', "
                "version=version+1 WHERE task_id=:id"
            ),
            {"id": old_lease.task_id},
        )
    lease, _, output = prepare(core_database)
    assert old_lease.task_id == lease.task_id and lease.token != old_lease.token
    assert deliver(core_database, lease, output) == "APPLIED"
    assert deliver(core_database, old_lease, old_output) == "LEASE_LOST"
    d.refresh()
    assert len(d.read("/revisions")) == 1
    assert d.client.get(d.chapter_api).json()["current_version"] == (1)


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_transaction_rollback_and_repository_no_commit(
    revision_driver, core_database, monkeypatch, phase
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    before = d.read("/revisions")
    history = d.read("/history")
    lease, _, output = prepare(core_database)
    original = RevisionRepository.add

    def fail(self, record):
        with monkeypatch.context() as patch:
            patch.setattr(self.session, "commit", lambda: pytest.fail("Repository must not commit"))
            original(self, record)
        raise RuntimeError("injected rollback")

    with monkeypatch.context() as patch:
        patch.setattr(RevisionRepository, "add", fail)
        with pytest.raises(RuntimeError, match="injected"):
            deliver(core_database, lease, output)
    assert d.read("/revisions") == before
    assert d.read("/history") == history
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert deliver(core_database, lease, output) == "APPLIED"


def test_concurrent_requests_and_results_are_idempotent(revision_quality_driver, core_database):
    from threading import Barrier

    from novel_os.domain.core import CommandContext
    from novel_os.domain.errors import DomainError
    from novel_os.domain.workflow import EventCommand
    from novel_os.workflow.runtime import WorkflowRuntime

    d = revision_quality_driver
    review = finish_review(d, core_database)
    barrier = Barrier(2)

    def trigger(_):
        with core_database.session() as session:
            barrier.wait()
            try:
                return (
                    WorkflowRuntime(session)
                    .dispatch_event(
                        UUID(d.workflow["id"]),
                        EventCommand(
                            event_id=uuid4(),
                            event_type="REQUEST_REVISION",
                            expected_state_version=d.workflow["state_version"],
                            payload=dict(
                                source_review_id=review["id"],
                                expected_draft_version=1,
                                reason="explicit request",
                            ),
                        ),
                        CommandContext(str(uuid4()), "local-user"),
                    )
                    .outcome
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(trigger, range(2))) == ["APPLIED", "VERSION_CONFLICT"]
    d.refresh()
    run_one(core_database, d)
    lease, _, output = prepare(core_database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: deliver(core_database, lease, output), range(2))) == [
            "APPLIED",
            "DUPLICATE",
        ]
    d.refresh()
    assert len(d.read("/revisions")) == 1
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    run_one(core_database, d)
    assert d.client.get(d.chapter_api).json()["current_version"] == 2


def test_all_revision_evidence_append_only_and_bound_to_lineage(revision_driver, core_database):
    d = revision_driver
    run_one(core_database, d)
    run_one(core_database, d)
    run_one(core_database, d)
    record = d.read("/revisions")[0]
    assert record["request"]["source_context_package_id"]
    assert record["source_binding"]["draft_version"] == 1
    for phase in ["plan", "candidate", "result"]:
        assert all(
            record[phase][key]
            for key in ["task_id", "run_id", "context_package_id", "prompt_lineage_id"]
        )
    for table in ["revision_requests", "revision_plans", "revision_candidates", "revision_results"]:
        for mutation in [f"DELETE FROM {table}", f"UPDATE {table} SET created_at=now()"]:
            with pytest.raises(IntegrityError), core_database.engine.begin() as conn:
                conn.execute(text(mutation))
    assert d.read("/revisions")[0] == record


def test_stale_review_and_pass_cannot_request_revision(revision_quality_driver, core_database):
    d = revision_quality_driver
    passing = finish_review(d, core_database, "SUCCESS")
    assert passing["body"]["overall_verdict"] == "PASS"
    response = d.client.post(
        d.url + "/revision",
        json=d.command(source_review_id=passing["id"], expected_draft_version=1),
    )
    assert response.status_code == 409
    post(d.client, d.url + "/quality-review", d.command(expected_draft_version=1))
    run_one(core_database, d)
    run_one(core_database, d, "QUALITY_FAIL")
    response = d.client.post(
        d.url + "/revision",
        json=d.command(source_review_id=passing["id"], expected_draft_version=1),
    )
    assert response.status_code == 409
    assert d.read("/revisions") == []


def test_revision_preserves_exact_approved_profile_and_plan(
    core_client, chapter_api, core_database
):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.test_writing_profiles import approve, draft

    d = QualityDriver(core_client, chapter_api)
    project = chapter_api.split("/chapters/")[0]
    draft(
        core_client, project, target_audience="历史冒险读者", narrative_perspective="THIRD_PERSON"
    )
    approved = approve(core_client, project)
    d.approve_plan(core_database)
    review = finish_review(d, core_database)
    draft(core_client, project, 1, target_audience="UNAPPROVED_PROFILE_SECRET")
    plan(core_client, chapter_api, 2, objective="UNAPPROVED_PLAN_SECRET")
    request_revision(d, review)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    run_one(core_database, d, provider=provider)
    for request in provider.requests:
        items = {i.selector_id: i for i in request.context_package.items}
        profile = next(i for i in items.values() if i.source_type == "PROJECT_WRITING_PROFILE")
        assert str(profile.source_id) == approved["id"] and profile.source_version == 1
        assert items["approved-plan"].source_version == 1
        assert "UNAPPROVED_" not in str(request.context_package)
        contract = items["revision-contract"].structured_payload
        assert any("narrative_perspective" in str(v) for v in contract["do_not_change"].values())
        assert contract["preserve_items"] and contract["review_authority"] == "DIAGNOSIS_ONLY"
    assert d.client.get(chapter_api).json()["approved_plan_version"] == 1
    assert d.client.get(project + "/writing-profile/approved").json() == approved


@pytest.mark.parametrize("tamper", ["hash", "source"])
def test_database_rejects_forged_successor_provenance(
    revision_driver, core_database, monkeypatch, tamper
):
    from dataclasses import replace

    from novel_os.domain.core import CommandContext
    from novel_os.domain.enums import ActorType
    from novel_os.domain.revision import RevisionResult
    from novel_os.services.versioning import ChapterVersionService

    d = revision_driver
    run_one(core_database, d)
    run_one(core_database, d)
    lease, _, output = prepare(core_database)
    add = RevisionRepository.add
    create = ChapterVersionService.create_version_in_transaction

    def forged_add(self, record):
        if isinstance(record, RevisionResult):
            record = replace(record, body={**record.body, "content_hash": "0" * 64})
        return add(self, record)

    def forged_create(self, project, chapter, payload, expected, context, reason):
        return create(
            self,
            project,
            chapter,
            payload,
            expected,
            CommandContext(context.request_id, "local-user", ActorType.USER),
            reason,
        )

    with monkeypatch.context() as patch:
        if tamper == "hash":
            patch.setattr(RevisionRepository, "add", forged_add)
        else:
            patch.setattr(ChapterVersionService, "create_version_in_transaction", forged_create)
        with pytest.raises(
            IntegrityError, match="Revision (successor|fidelity acceptance) mismatch"
        ):
            deliver(core_database, lease, output)
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert d.read("/revisions")[0]["result"] is None
    assert deliver(core_database, lease, output) == "APPLIED"


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_safe_block_explicit_rereview_abandons_cycle_without_rewriting(
    revision_driver, core_database, phase
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    run_one(core_database, d, "BLOCKED")
    before = d.read("/revisions")
    command = d.command(expected_draft_version=1)
    post(d.client, d.url + "/quality-review", command)
    d.refresh()
    assert d.workflow["revision_request_id"] is None
    run_one(core_database, d)
    worker = run_one(core_database, d, "QUALITY_FAIL")
    assert not worker.run_once()
    assert d.read("/revisions") == before
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert len(d.reviews()) == 2


def test_revision_migration_roundtrip_preserves_prior_draft_review(
    revision_quality_driver, core_database, migration_config
):
    from alembic import command

    d = revision_quality_driver
    before = finish_review(d, core_database)
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0012_targeted_revision")
        command.downgrade(migration_config, "-1")
        assert connection.scalar(text("SELECT to_regclass('revision_requests')")) is None
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    assert d.reviews()[0] == before
    request_revision(d, before)
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    run_one(core_database, d)
    assert d.client.get(d.chapter_api).json()["current_version"] == 2


@pytest.mark.parametrize("during_model", [False, True])
def test_relevant_decision_change_stales_revision(
    core_client, chapter_api, core_database, during_model
):
    from tests.core.quality.conftest import QualityDriver

    d = QualityDriver(core_client, chapter_api)
    project = chapter_api.split("/chapters/")[0]
    from tests.core.test_writing_profiles import approve, draft

    draft(core_client, project, narrative_perspective="THIRD_PERSON")
    approve(core_client, project)
    decision = post(
        core_client, project + "/decisions", dict(question="结尾方向", decision="沿河继续寻找")
    )
    url = project + "/decisions/" + decision["logical_id"]
    post(core_client, url + "/approve", dict(expected_version=1))
    d.approve_plan(core_database)
    request_revision(d, finish_review(d, core_database))

    def change(*_):
        response = core_client.post(
            url + "/versions",
            json=dict(expected_version=1, question="结尾方向", decision="批准的新方向"),
        )
        assert response.status_code == 201, response.text
        post(core_client, url + "/approve", dict(expected_version=2))

    if not during_model:
        change()
    provider = RecordedProvider(change if during_model else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(during_model)
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/revisions")[0]["plan"] is None
    assert d.client.get(chapter_api).json()["current_version"] == 1


@pytest.mark.parametrize("phase", ["plan", "execution"])
def test_technical_exhaustion_then_changed_source_has_explicit_escape(
    revision_driver, core_database, phase
):
    d = revision_driver
    if phase == "execution":
        run_one(core_database, d)
    from novel_os.agents.provider import MockModelProvider
    from novel_os.agents.runtime import AgentRuntime
    from novel_os.worker import AgentWorker

    worker = AgentWorker(
        core_database, AgentRuntime(MockModelProvider("ALWAYS_FAIL")), max_attempts=1
    )
    assert worker.run_once()
    d.refresh()
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/agent-tasks")[-1]["status"] == "FAILED"
    post(
        d.client,
        d.chapter_api + "/versions",
        dict(
            expected_version=1,
            content="人工修改后的第二版正文。\n\n第二段保留人物的决定和行动。",
            change_reason="修改依据已变化",
        ),
    )
    assert d.post("/resume", d.command()).status_code == 409
    post(d.client, d.url + "/quality-review", d.command(expected_draft_version=2))
    d.refresh()
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    assert d.workflow["revision_request_id"] is None
    run_one(core_database, d)
    worker = run_one(core_database, d)
    assert d.workflow["status"] == "WAITING_HUMAN"
    assert not worker.run_once()
    assert d.client.get(d.chapter_api).json()["current_version"] == 2
    assert d.read("/revisions")[0]["result"] is None


def test_profileless_review_cannot_start_revision_even_after_profile_approval(
    quality_driver, core_database, monkeypatch
):
    from novel_os.services.revision_binding import RevisionBindingService
    from tests.core.test_writing_profiles import approve, draft

    d = quality_driver
    review = finish_review(d, core_database)
    before = d.workflow.copy()
    tasks = d.read("/agent-tasks")
    payload = d.command(source_review_id=review["id"], expected_draft_version=1)
    project = d.chapter_api.split("/chapters/")[0]
    for stage in ("absent", "draft", "approved"):
        if stage == "draft":
            draft(d.client, project, narrative_perspective="THIRD_PERSON")
        if stage == "approved":
            approve(d.client, project)
        response = d.client.post(d.url + "/revision", json=payload)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "CONTEXT_MISSING"
        d.refresh()
        assert d.workflow == before
        assert d.read("/agent-tasks") == tasks
        assert d.read("/revisions") == []
    # The DB independently rejects the profile-less source even if a caller skips validation.
    with monkeypatch.context() as patch:
        patch.setattr(RevisionBindingService, "check_source", lambda *args: None)
        response = d.client.post(d.url + "/revision", json=payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    d.refresh()
    assert d.workflow == before
    assert d.read("/revisions") == []
    assert d.read("/agent-tasks") == tasks
    post(d.client, d.url + "/quality-review", d.command(expected_draft_version=1))
    run_one(core_database, d)
    run_one(core_database, d, "QUALITY_FAIL")
    request_revision(d, d.reviews()[0])
    assert d.read("/revisions")[0]["source_binding"]["profile_version"] == 1
