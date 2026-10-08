import pytest

from tests.core.workflow.test_planning_vertical_slice import run_one


@pytest.mark.parametrize(
    "scenario,state,verdict",
    [("SUCCESS", "C11_INTERNAL_PASS", "PASS"), ("QUALITY_FAIL", "C10_REVISION", "FAIL")],
)
def test_two_pass_review_stops_for_human_without_revision(
    quality_driver, core_database, scenario, state, verdict
):
    d = quality_driver
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW", d.workflow
    draft = d.client.get(d.chapter_api + "/versions/1").json()
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW", d.workflow
    assert d.reviews() == []
    worker = run_one(core_database, d, scenario)
    assert d.workflow["current_state"] == state, d.workflow
    assert d.workflow["status"] == "WAITING_HUMAN"
    review = d.reviews()[0]
    assert review["body"]["overall_verdict"] == verdict
    assert review["chapter_version_id"] == draft["id"]
    assert review["body"]["chapter_version_id"] == draft["id"]
    assert review["freshness"] == "CURRENT"
    assert d.client.get(d.chapter_api + "/versions/1").json() == draft
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    tasks = d.read("/agent-tasks")
    assert (
        len(
            [
                t
                for t in tasks
                if t["task_type"].startswith("REVIEW_CHAPTER_")
                and t["task_type"] != "REVIEW_CHAPTER_PLAN"
            ]
        )
        == 2
    )
    assert not any(t["agent_id"] == "A06_REVISION" for t in tasks)
    assert worker.run_once() is False


def test_retry_produces_one_pass_and_no_duplicate_review(quality_driver, core_database):
    d = quality_driver
    run_one(core_database, d)
    run_one(core_database, d, "MODEL_ERROR_ONCE")
    assert d.workflow["current_state"] == "C09_INTERNAL_REVIEW"
    task = d.read("/agent-tasks")[-1]
    assert task["status"] == "PENDING" and task["attempt_count"] == 1
    run_one(core_database, d)
    run_one(core_database, d)
    assert len(d.reviews()) == 1
    runs = d.client.get("/api/v1/agent-tasks/" + task["task_id"] + "/runs").json()
    assert len(runs) == 2
    assert {r["status"] for r in runs} == {"SUCCEEDED", "FAILED"}


@pytest.mark.parametrize("during_model", [False, True])
@pytest.mark.parametrize("changed", ["draft", "profile"])
def test_queued_and_inflight_review_rejects_changed_sources(
    quality_driver, core_database, changed, during_model
):
    from tests.core.test_writing_profiles import approve, draft
    from tests.planning_support import RecordedProvider
    from tests.writing_support import post

    d = quality_driver
    run_one(core_database, d)

    def change(*_):
        if changed == "draft":
            post(
                d.client,
                d.chapter_api + "/versions",
                dict(expected_version=1, content="新的草稿内容", change_reason="人工修改"),
            )
        else:
            url = d.chapter_api.split("/chapters/")[0]
            draft(d.client, url, target_audience="新的批准受众")
            approve(d.client, url)

    if not during_model:
        change()
    provider = RecordedProvider(change if during_model else None)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED", d.workflow
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"
    assert d.reviews() == []
    assert len(provider.requests) == int(during_model)


def test_exact_profile_and_new_unapproved_profile_isolated(core_client, chapter_api, core_database):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.test_writing_profiles import approve, draft
    from tests.planning_support import RecordedProvider

    d = QualityDriver(core_client, chapter_api)
    url = chapter_api.split("/chapters/")[0]
    draft(core_client, url, target_audience="历史冒险读者", narrative_perspective="THIRD_PERSON")
    approved = approve(core_client, url)
    draft(core_client, url, 1, target_audience="UNAPPROVED_PROFILE_SECRET")
    d.approve_plan(core_database)
    run_one(core_database, d)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    run_one(core_database, d, provider=provider)
    binding = d.reviews()[0]["binding"]
    assert binding["profile_record_id"] == approved["id"]
    assert binding["profile_hash"] == approved["profile_hash"]
    assert binding["profile_version"] == 1
    for request in provider.requests:
        selected = [
            i for i in request.context_package.items if i.source_type == "PROJECT_WRITING_PROFILE"
        ]
        assert len(selected) == 1 and selected[0].source_id.hex == approved["id"].replace("-", "")
        assert selected[0].authority_level == "A5_USER_PREFERENCE"
        assert "UNAPPROVED_PROFILE_SECRET" not in str(request.context_package)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE quality_review_bindings SET plan_version=99",
        "DELETE FROM quality_review_bindings",
        "UPDATE quality_review_passes SET body='{}'",
        "DELETE FROM quality_review_passes",
        "UPDATE chapter_quality_reviews SET body='{}'",
        "DELETE FROM chapter_quality_reviews",
    ],
)
def test_review_evidence_is_immutable_in_database(quality_driver, core_database, sql):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    d = quality_driver
    for _ in range(3):
        run_one(core_database, d)
    before = d.reviews()
    with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
        connection.execute(text(sql))
    assert d.reviews() == before


def test_stale_read_and_explicit_rereview_never_overwrites_history(quality_driver, core_database):
    from uuid import uuid4

    from tests.writing_support import post

    d = quality_driver
    for _ in range(3):
        run_one(core_database, d)
    first = d.reviews()[0]
    command = dict(
        event_id=str(uuid4()),
        expected_state_version=d.workflow["state_version"],
        expected_draft_version=1,
        reason="人工明确重新审阅",
    )
    result = d.client.post(d.url + "/quality-review", json=command)
    assert result.status_code == 200, result.text
    assert d.client.post(d.url + "/quality-review", json=command).json()["duplicate"]
    for _ in range(2):
        run_one(core_database, d)
    history = d.reviews()
    assert len(history) == 2 and history[1] == first
    post(
        d.client,
        d.chapter_api + "/versions",
        dict(expected_version=1, content="新的正文", change_reason="人工新版本"),
    )
    assert all(r["freshness"] == "STALE" for r in d.reviews())
    assert d.reviews()[1]["body"] == first["body"]


def test_pass_and_audit_rollback_then_exact_redelivery(quality_driver, core_database, monkeypatch):
    from novel_os.repositories.quality import QualityRepository
    from tests.core.writing.test_lifecycle import deliver, prepare

    d = quality_driver
    run_one(core_database, d)
    lease, task, execution = prepare(core_database)
    add = QualityRepository.add

    def fail(self, record):
        add(self, record)
        raise RuntimeError("injected quality persistence failure")

    with monkeypatch.context() as patch:
        patch.setattr(QualityRepository, "add", fail)
        with pytest.raises(RuntimeError, match="injected"):
            deliver(core_database, lease, execution)
    assert d.reviews() == []
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert deliver(core_database, lease, execution) == "DUPLICATE"
    run_one(core_database, d)
    assert len(d.reviews()) == 1


@pytest.mark.parametrize("capability", ["PROPOSE_DRAFT", "PROPOSE_PLAN", "APPROVE", "COMMIT_CANON"])
def test_reviewer_cannot_mutate_other_domains(quality_driver, core_database, capability):
    import json

    from novel_os.agents.provider import MockModelProvider
    from novel_os.providers.base import ModelResponse

    class Forged(MockModelProvider):
        def generate(self, request):
            response = super().generate(request)
            body = json.loads(response.content)
            body["proposed_changes"] = [
                dict(capability=capability, target_ref=str(request.target_ref))
            ]
            return ModelResponse(json.dumps(body))

    d = quality_driver
    run_one(core_database, d)
    original = d.client.get(d.chapter_api + "/versions/1").json()
    run_one(core_database, d, provider=Forged())
    assert d.reviews() == []
    assert d.client.get(d.chapter_api + "/versions/1").json() == original
    task = d.read("/agent-tasks")[-1]
    assert task["last_error_code"] in {"AUTHORITY_DENIED", "SCHEMA_PARSE_ERROR"}
    assert d.client.get(d.chapter_api).json()["approved_version"] is None


def test_quality_repository_never_commits(quality_driver, core_database, monkeypatch):
    from novel_os.repositories.quality import QualityRepository

    d = quality_driver
    run_one(core_database, d)
    add = QualityRepository.add

    def guarded(self, record):
        with monkeypatch.context() as patch:
            patch.setattr(self.session, "commit", lambda: pytest.fail("Repository commit"))
            patch.setattr(self.session, "rollback", lambda: pytest.fail("Repository rollback"))
            return add(self, record)

    monkeypatch.setattr(QualityRepository, "add", guarded)
    for _ in range(2):
        run_one(core_database, d)
    assert len(d.reviews()) == 1


def test_historical_offline_evaluation_keeps_expectations_out_of_prompts(
    quality_driver, core_database, core_settings, tmp_path
):
    import importlib.util
    import json
    from pathlib import Path
    from uuid import UUID

    source = Path(__file__).resolve().parents[4] / "evals/quality/run.py"
    spec = importlib.util.spec_from_file_location("quality_eval", source)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    d = quality_driver
    run_one(core_database, d)
    parts = d.chapter_api.split("/")
    inputs = harness.export_inputs(core_settings, UUID(parts[4]), UUID(parts[6]), 1)
    assert inputs["draft_version"] == 1
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps({"theme": "HUMAN_EXPECTATION_NOT_PROMPT"}))
    harness.evaluate(core_settings, inputs, tmp_path / "evaluation", expected=expected)
    comparison = json.loads((tmp_path / "evaluation/comparison.json").read_text())
    assert comparison["mode"] == "MOCK_CONTRACT_ONLY"
    for file in (tmp_path / "evaluation").glob("*.lineage.json"):
        assert "HUMAN_EXPECTATION_NOT_PROMPT" not in file.read_text()
    assert d.reviews() == []  # Harness never writes the runtime review tables.


def test_concurrent_delivery_schedules_one_next_pass(quality_driver, core_database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from tests.core.writing.test_lifecycle import deliver, prepare

    d = quality_driver
    run_one(core_database, d)
    lease, task, execution = prepare(core_database)
    barrier = Barrier(2)

    def delivery():
        barrier.wait()
        return deliver(core_database, lease, execution)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: delivery(), range(2)))
    assert sorted(results) == ["APPLIED", "DUPLICATE"]
    assert (
        len([t for t in d.read("/agent-tasks") if t["task_type"] == "REVIEW_CHAPTER_NARRATIVE"])
        == 1
    )
    run_one(core_database, d)
    assert len(d.reviews()) == 1


def test_quality_migration_roundtrip_and_metadata_match(core_database, migration_config):
    from sqlalchemy import inspect

    from alembic import command

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
        assert "chapter_quality_reviews" in inspect(connection).get_table_names()
        command.downgrade(migration_config, "0011_quality_review")
        command.downgrade(migration_config, "-1")
        assert "chapter_quality_reviews" not in inspect(connection).get_table_names()
        command.upgrade(migration_config, "head")
        command.check(migration_config)


def test_profile_change_between_passes_cannot_mix_authority_snapshots(
    quality_driver, core_database
):
    from tests.core.test_writing_profiles import approve, draft
    from tests.planning_support import RecordedProvider

    d = quality_driver
    run_one(core_database, d)
    run_one(core_database, d)
    project = d.chapter_api.split("/chapters/")[0]
    draft(d.client, project, target_audience="第二轮前新批准的受众")
    approve(d.client, project)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.reviews() == []
    narrative = next(
        t for t in d.read("/agent-tasks") if t["task_type"] == "REVIEW_CHAPTER_NARRATIVE"
    )
    assert narrative["last_error_code"] == "CONTEXT_STALE"


def test_quality_recent_history_uses_bounded_approved_versions_only(
    core_client, project_api, core_database
):
    from novel_os.context.serialization import ContextSerializer
    from tests.core.quality.conftest import QualityDriver
    from tests.planning_support import RecordedProvider
    from tests.writing_support import chapter, post

    client = core_client
    for sequence in range(1, 7):
        url = chapter(client, project_api, sequence)
        for version in (1, 2):
            post(
                client,
                url + "/versions",
                dict(
                    expected_version=version - 1,
                    content=f"APPROVED_HISTORY_{sequence}" if version == 1 else "DRAFT_SECRET",
                    change_reason="history fixture",
                ),
            )
            if version == 1:
                post(client, url + "/versions/approve", dict(expected_version=1))
    # Sequence 5 is the target; sequence 6 is future and sequence 1 is outside the window.
    response = client.get(project_api + "/chapters").json()
    target = next(c for c in response if c["sequence"] == 5)
    # The Writer will create v3; both prior target versions stay immutable.
    d = QualityDriver(client, project_api + "/chapters/" + target["id"])
    d.approve_plan(core_database)
    run_one(core_database, d)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == 1
    package = provider.requests[0].context_package
    recent = [i for i in package.items if i.selector_id == "recent-approved-chapters"]
    assert {i.chapter_sequence for i in recent} == {2, 3, 4}
    assert all(i.source_version == 1 for i in recent)
    serialized = str(ContextSerializer.snapshot(package))
    assert "DRAFT_SECRET" not in serialized
    assert "APPROVED_HISTORY_6" not in serialized
    assert "APPROVED_HISTORY_1" not in serialized
