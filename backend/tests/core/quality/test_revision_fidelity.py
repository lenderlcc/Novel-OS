from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from novel_os.domain.revision import RevisionCandidate, RevisionResult
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.repositories.revision import RevisionRepository
from tests.core.quality.test_revision import finish_review, request_revision
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.core.writing.test_lifecycle import deliver, prepare
from tests.planning_support import RecordedProvider
from tests.writing_support import post


@pytest.fixture
def candidate_driver(revision_quality_driver, core_database):
    d = revision_quality_driver
    request_revision(d, finish_review(d, core_database))
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    return d


def test_candidate_is_not_a_draft_and_complete_edit_base_is_p0(candidate_driver, core_database):
    d = candidate_driver
    record = d.read("/revisions")[0]
    assert record["candidate"]["body"]["content"] and record["result"] is None
    assert d.client.get(d.chapter_api + "/versions/2").status_code == 404
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    req = provider.requests[0]
    items = {i.selector_id: i for i in req.context_package.items}
    assert items["target-version"].priority == "P0"
    assert (
        items["target-version"].structured_payload["content"]
        == d.client.get(d.chapter_api + "/versions/1").json()["content"]
    )
    assert items["revision-contract"].structured_payload["edit_base"]["role"] == "EDIT_BASE"
    assert (
        items["revision-candidate"].structured_payload["content"]
        == record["candidate"]["body"]["content"]
    )
    assert (
        next(t for t in d.read("/agent-tasks") if t["task_id"] == str(req.task_id))["agent_id"]
        == "A05_REVIEW"
    )
    assert d.client.get(d.chapter_api).json()["current_version"] == 2
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"


def test_fidelity_window_block_recovers_by_explicit_rereview(
    candidate_driver, core_database, monkeypatch
):
    d = candidate_driver
    before = d.client.get(d.chapter_api + "/versions/1").json()
    provider = RecordedProvider()
    with monkeypatch.context() as patch:
        patch.setattr(ModelProfileRegistry, "context_window", lambda self, model: 8192)
        worker = run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.workflow["status"] == "BLOCKED"
    assert d.workflow["resume_state"] == "C10_REVISION"
    task = d.read("/agent-tasks")[-1]
    assert task["task_type"] == "VALIDATE_REVISION_FIDELITY"
    assert task["agent_id"] == "A05_REVIEW"
    assert task["status"] == "BLOCKED"
    assert task["last_error_code"] == "CONTEXT_BUDGET_EXCEEDED"
    old = d.read("/revisions")[0]
    assert old["candidate"] is not None and old["result"] is None
    assert not worker.run_once()

    post(d.client, d.url + "/quality-review", d.command(expected_draft_version=1))
    d.refresh()
    assert d.workflow["revision_request_id"] is None
    run_one(core_database, d)
    worker = run_one(core_database, d, "QUALITY_FAIL")
    assert not worker.run_once()
    assert d.client.get(d.chapter_api + "/versions/1").json() == before
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert d.read("/revisions") == [old]
    review = d.reviews()[0]
    assert review["chapter_version_id"] == before["id"]
    request_revision(d, review)
    assert d.workflow["revision_request_id"] != old["request"]["id"]
    assert len(d.read("/revisions")) == 2


@pytest.mark.parametrize(
    "code,check",
    [
        ("UNAUTHORIZED_SCENE_REPLACEMENT", "SCENE_PREMISE"),
        ("REVISION_STRENGTH_REGRESSION", "strength:0"),
        ("REVISION_SCOPE_VIOLATION", "STRUCTURAL_SCOPE"),
    ],
)
def test_failed_fidelity_preserves_current_source_and_stops(
    candidate_driver, core_database, code, check
):
    d = candidate_driver
    before = d.client.get(d.chapter_api + "/versions/1").json()

    def fail(_, body):
        out = body["result"]
        out["verdict"] = "FAIL"
        next(c for c in out["checks"] if c["check_id"] == check)["preserved"] = False
        out["violations"] = [dict(code=code, check_ids=[check], description="超出必要修订范围")]

    worker = run_one(core_database, d, provider=RecordedProvider(fail))
    record = d.read("/revisions")[0]
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert d.client.get(d.chapter_api + "/versions/1").json() == before
    assert record["candidate"]["body"]["content"]
    assert record["result"]["chapter_version_id"] is None
    assert record["result"]["body"]["fidelity"]["verdict"] == "FAIL"
    assert record["result"]["body"]["accepted"] is False
    assert record["result"]["body"]["candidate_id"] == record["candidate"]["id"]
    assert d.workflow["status"] == "BLOCKED"
    assert d.post("/resume", d.command()).status_code == 409
    assert not worker.run_once()
    assert len(d.reviews()) == 1


def test_declared_addressed_issues_do_not_bypass_gate(candidate_driver, core_database):
    d = candidate_driver
    assert d.read("/revisions")[0]["candidate"]["body"]["addressed_issue_ids"]
    worker = run_one(core_database, d, "QUALITY_FAIL")
    assert not worker.run_once()
    assert d.client.get(d.chapter_api).json()["current_version"] == 1


@pytest.mark.parametrize("when", ["before", "during"])
def test_source_changed_before_fidelity_persist_rejects_stale(
    candidate_driver, core_database, when
):
    d = candidate_driver

    def change(*_):
        post(
            d.client,
            d.chapter_api + "/versions",
            dict(expected_version=1, content="用户编辑的新正文。", change_reason="用户编辑"),
        )

    if when == "before":
        change()
    provider = RecordedProvider(change if when == "during" else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == (1 if when == "during" else 0)
    assert d.read("/revisions")[0]["result"] is None
    assert d.client.get(d.chapter_api).json()["current_version"] == 2
    assert d.workflow["status"] == "BLOCKED"


def test_fidelity_rollback_and_duplicate_delivery(candidate_driver, core_database, monkeypatch):
    d = candidate_driver
    lease, _, output = prepare(core_database)
    original = RevisionRepository.add

    def rollback(self, record):
        with monkeypatch.context() as patch:
            patch.setattr(
                self.session, "commit", lambda: pytest.fail("Repository commit forbidden")
            )
            original(self, record)
        raise RuntimeError("force rollback after acceptance")

    with monkeypatch.context() as patch:
        patch.setattr(RevisionRepository, "add", rollback)
        with pytest.raises(RuntimeError, match="force rollback"):
            deliver(core_database, lease, output)
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert d.read("/revisions")[0]["result"] is None
    assert deliver(core_database, lease, output) == "APPLIED"
    assert deliver(core_database, lease, output) == "DUPLICATE"
    assert d.client.get(d.chapter_api).json()["current_version"] == 2


def test_database_cannot_accept_failed_verdict(candidate_driver, core_database, monkeypatch):
    lease, _, output = prepare(core_database)
    original = RevisionRepository.add

    def forge(self, record):
        if isinstance(record, RevisionResult):
            record = replace(
                record,
                body={**record.body, "fidelity": {**record.body["fidelity"], "verdict": "FAIL"}},
            )
        return original(self, record)

    with monkeypatch.context() as patch:
        patch.setattr(RevisionRepository, "add", forge)
        with pytest.raises(IntegrityError, match="Revision fidelity acceptance mismatch"):
            deliver(core_database, lease, output)
    assert candidate_driver.client.get(candidate_driver.chapter_api).json()["current_version"] == 1


def test_candidate_immutable_and_not_upgradable_in_place(candidate_driver, core_database):
    for sql in ["UPDATE revision_candidates SET body=body", "DELETE FROM revision_candidates"]:
        with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
            connection.execute(text(sql))
    with core_database.session() as session:
        from uuid import UUID

        assert RevisionRepository(session).evidence(
            UUID(candidate_driver.workflow["revision_request_id"]), RevisionCandidate
        )


def test_fidelity_migration_upgrade_downgrade_upgrade_check(core_database, migration_config):
    from alembic import command

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0022_feedback_before_review"
        )
        command.downgrade(migration_config, "0013_revision_fidelity")
        command.downgrade(migration_config, "-1")
        assert connection.scalar(text("SELECT to_regclass('revision_candidates')")) is None
        assert connection.scalar(text("SELECT to_regclass('revision_results')")) is not None
        command.upgrade(migration_config, "head")
        command.check(migration_config)
