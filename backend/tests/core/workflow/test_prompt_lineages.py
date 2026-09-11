import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import httpx
import pytest
from agent_test_support import claim, complete, pending_task, runs, start, task_record, worker
from prompt_test_support import add_role_v2, edit_manifest
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import RunStatus, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.models.prompts import PromptLineageModel
from novel_os.prompts.contracts import digest
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import ERROR_RETRYABLE, ProviderError
from novel_os.providers.openai import OpenAIModelProvider
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.prompt_lineages import PromptLineageService
from novel_os.services.task_history import TaskHistory
from novel_os.worker import AgentWorker

pytestmark = pytest.mark.integration


def lineage(database, run_id):
    with database.session() as session:
        return PromptLineageService(session).get(run_id)


@pytest.fixture
def copied_library(tmp_path):
    import novel_os.prompts

    path = tmp_path / "prompts"
    shutil.copytree(Path(novel_os.prompts.__file__).parent / "library", path)
    return path


def test_worker_persists_exact_lineage_before_provider_and_inspector_hides_bodies(
    driver, core_database
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])

    class InspectingMock(MockModelProvider):
        def generate(self, request):
            assert core_database.engine.pool.checkedout() == 0
            with core_database.session() as session:
                row = session.scalar(
                    select(PromptLineageModel).where(PromptLineageModel.task_id == task_id)
                )
                assert row is not None  # Visible from an independent transaction before RPC.
                assert row.compiled_prompt_hash == request.prompt.compiled_hash
            return super().generate(request)

    assert AgentWorker(core_database, AgentRuntime(InspectingMock())).run_once()
    run = runs(core_database, task_id)[0]
    assert run.status == RunStatus.SUCCEEDED
    bound = lineage(core_database, run.run_id)
    response = driver.client.get(f"/api/v1/agent-runs/{run.run_id}/prompt-lineage")
    assert response.status_code == 200
    body = response.json()
    assert body["agent_run_id"] == str(run.run_id)
    assert body["task_id"] == str(task_id)
    assert body["lineage_id"] == str(bound.lineage_id)
    assert body["agent_role"]["version"] == 1
    assert body["compiler_version"] == 2
    assert len(body["agent_role"]["execution_hash"]) == 64
    assert body["skills"][0]["module_id"] == "structured-reporting"
    assert not {"content", "messages", "context", "api_key"} & set(body)
    assert "You execute bounded" not in response.text
    assert run.output_metadata["model"]["finish_reason"] == "stop"
    assert driver.client.get(f"/api/v1/agent-runs/{uuid4()}/prompt-lineage").status_code == 404


def test_old_run_without_lineage_returns_explicit_not_found(driver, core_database):
    driver.event("USER_SUBMITTED")
    lease = claim(core_database)
    assert driver.client.get(f"/api/v1/agent-runs/{lease.run_id}/prompt-lineage").status_code == 404


def test_legacy_pins_remain_readable_but_cannot_certify_execution_metadata(driver, core_database):
    driver.event("USER_SUBMITTED")
    lease = claim(core_database)
    task = start(core_database, lease)
    runtime = AgentRuntime(MockModelProvider("FORMAT_ERROR_ONCE"))
    prepared = runtime.prepare(task)
    with core_database.session() as session:
        assert PromptLineageService(session).bind(lease, prepared)
    original = lineage(core_database, lease.run_id)
    assert complete(core_database, lease, runtime.execute(task, prepared)) == "RETRY_SCHEDULED"
    second = claim(core_database)
    start(core_database, second)

    def legacy_pin(pin):
        return {key: value for key, value in pin.items() if key != "execution_hash"}

    legacy = replace(
        original,
        lineage_id=uuid4(),
        agent_run_id=second.run_id,
        compiler_version=1,
        compiled_prompt_hash=digest("legacy compiler fixture"),
        system_policy=legacy_pin(original.system_policy),
        agent_role=legacy_pin(original.agent_role),
        task_template=legacy_pin(original.task_template),
        skills=[legacy_pin(pin) for pin in original.skills],
        quality_profile=legacy_pin(original.quality_profile),
    )
    with core_database.session() as session, session.begin():
        PromptLineageRepository(session).add(legacy)
    response = driver.client.get(f"/api/v1/agent-runs/{second.run_id}/prompt-lineage")
    assert response.status_code == 200
    assert response.json()["compiler_version"] == 1
    assert response.json()["agent_role"]["execution_hash"] is None
    with core_database.session() as session, session.begin():
        pins = [item.module.pin().model_dump() for item in prepared.prompt.modules]
        assert not PromptLineageRepository(session).matches_historical_pins(pins)
    assert lineage(core_database, lease.run_id) == original
    assert lineage(core_database, second.run_id) == legacy


def test_versions_and_each_retry_keep_immutable_exact_history(
    driver, core_database, copied_library
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    registry = PromptRegistry(copied_library)
    runtime = AgentRuntime(MockModelProvider("FORMAT_ERROR_ONCE"), prompts=registry)
    executor = AgentWorker(core_database, runtime, retry_seconds=0)
    assert executor.run_once()
    first_run = runs(core_database, task_id)[0]
    old = lineage(core_database, first_run.run_id)
    assert first_run.error_code == "FORMAT_ERROR"
    manifest = add_role_v2(copied_library)
    registry.reload()
    assert (
        runtime.prepare(task_record(core_database, task_id)).prompt.modules[1].module.version == 1
    )
    edit_manifest(manifest, status="STABLE")
    registry.reload()
    assert executor.run_once()
    second_run = runs(core_database, task_id)[1]
    new = lineage(core_database, second_run.run_id)
    assert old.agent_role["version"] == 1
    assert new.agent_role["version"] == 2
    assert new.agent_run_id != old.agent_run_id
    assert new.task_id == old.task_id
    assert old == lineage(core_database, first_run.run_id)
    assert first_run == runs(core_database, task_id)[0]
    assert old.compiled_prompt_hash != new.compiled_prompt_hash


@pytest.mark.parametrize("mutation", ["body", "dependencies", "agents", "task_types"])
def test_fresh_worker_rejects_in_place_definition_change(
    driver, core_database, copied_library, mutation
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    runtime = AgentRuntime(
        MockModelProvider("FORMAT_ERROR_ONCE"), prompts=PromptRegistry(copied_library)
    )
    assert AgentWorker(core_database, runtime, retry_seconds=0).run_once()
    old_run = runs(core_database, task_id)[0]
    old = lineage(core_database, old_run.run_id)
    path = copied_library / "agents/simulation-role/v1"
    if mutation == "body":
        changed = "Changed same version on a different worker\n"
        (path / "content.md").write_text(changed)
        edit_manifest(path / "manifest.json", content_hash=digest(changed))
    else:
        changes = {
            "dependencies": {"dependencies": [{"module_id": "structured-reporting", "version": 1}]},
            "agents": {"compatible_agents": ["A03_PLANNING"]},
            "task_types": {"compatible_task_types": ["MOCK_PLAN"]},
        }
        edit_manifest(path / "manifest.json", **changes[mutation])

    class NeverExecute(MockModelProvider):
        def generate(self, request):
            pytest.fail("Conflicting historical module must fail before provider call")

    fresh = AgentRuntime(NeverExecute(), prompts=PromptRegistry(copied_library))
    assert AgentWorker(core_database, fresh).run_once()
    history = runs(core_database, task_id)
    assert history[1].error_code == "PROMPT_CONFIGURATION_ERROR"
    assert history[1].status == RunStatus.FAILED
    assert task_record(core_database, task_id).status == TaskStatus.FAILED
    assert old == lineage(core_database, old_run.run_id)


@pytest.mark.parametrize(
    "provider_code,expected",
    [("server_error", "MODEL_UNAVAILABLE"), ("rate_limit_exceeded", "MODEL_RATE_LIMIT")],
)
def test_http_200_temporary_failure_retries_and_recovers(
    driver, core_database, provider_code, expected
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    mock = MockModelProvider()
    valid = mock.generate(AgentRuntime(mock).prepare(task_record(core_database, task_id))).content
    calls = 0

    def respond(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "status": "failed",
                    "error": {"code": provider_code, "message": "Transient upstream failure"},
                    "output": [],
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": valid}]}
                ],
            },
        )

    runtime = AgentRuntime(
        OpenAIModelProvider(SecretStr("test-key"), transport=httpx.MockTransport(respond)),
        tasks=TaskDefinitionRegistry(model_profile="openai-structured"),
    )
    executor = AgentWorker(core_database, runtime, retry_seconds=0)
    assert executor.run_once()
    first = runs(core_database, task_id)[0]
    first_lineage = lineage(core_database, first.run_id)
    assert first.error_code == expected
    assert first.status == RunStatus.FAILED
    assert task_record(core_database, task_id).status == TaskStatus.PENDING
    assert executor.run_once()
    assert calls == 2
    assert task_record(core_database, task_id).status == TaskStatus.SUCCEEDED
    history = runs(core_database, task_id)
    assert history[0] == first
    assert history[1].status == RunStatus.SUCCEEDED
    assert lineage(core_database, first.run_id) == first_lineage
    assert lineage(core_database, history[1].run_id).lineage_id != first_lineage.lineage_id


@pytest.mark.parametrize("code", list(ERROR_RETRYABLE))
def test_provider_error_policy_integrates_with_persisted_worker_attempts(
    driver, core_database, code
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])

    class ErrorProvider(MockModelProvider):
        def generate(self, request):
            raise ProviderError(code)

    executor = AgentWorker(core_database, AgentRuntime(ErrorProvider()), retry_seconds=0)
    assert executor.run_once()
    first = runs(core_database, task_id)[0]
    assert first.error_code == code
    assert first.status == RunStatus.FAILED
    assert lineage(core_database, first.run_id).agent_run_id == first.run_id
    if ERROR_RETRYABLE[code]:
        assert task_record(core_database, task_id).status == TaskStatus.PENDING
        assert worker(core_database).run_once()
        assert runs(core_database, task_id)[1].status == RunStatus.SUCCEEDED
        assert runs(core_database, task_id)[0] == first
    else:
        assert task_record(core_database, task_id).status == TaskStatus.FAILED
        assert not executor.run_once()
        assert len(runs(core_database, task_id)) == 1


def test_secret_absent_from_run_lineage_audit_api_and_logs(driver, core_database, caplog):
    secret = "sk-fake-secret-database-regression"
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    provider = OpenAIModelProvider(
        SecretStr(secret),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                401,
                json={"error": {"code": "invalid_api_key", "message": secret}},
                headers={"authorization": secret},
            )
        ),
    )
    runtime = AgentRuntime(
        provider, tasks=TaskDefinitionRegistry(model_profile="openai-structured")
    )
    assert AgentWorker(core_database, runtime).run_once()
    run = runs(core_database, task_id)[0]
    assert run.provider == "openai"
    assert run.model == "gpt-4o-mini-2024-07-18"
    assert run.error_code == "MODEL_AUTH_ERROR"
    response = driver.client.get(f"/api/v1/agent-runs/{run.run_id}/prompt-lineage")
    assert response.status_code == 200
    assert response.json()["model_profile"]["provider"] == "openai"
    assert secret not in response.text + caplog.text
    with core_database.engine.connect() as connection:
        for table in ("agent_runs", "agent_tasks", "prompt_lineages", "audit_records"):
            rows = (
                connection.execute(text(f"SELECT to_jsonb(t)::text FROM {table} t")).scalars().all()
            )
            assert all(secret not in row for row in rows)


@pytest.mark.parametrize(
    "mutation", ["UPDATE prompt_lineages SET compiler_version=2", "DELETE FROM prompt_lineages"]
)
def test_lineage_is_immutable_in_database(driver, core_database, mutation):
    driver.event("USER_SUBMITTED")
    worker(core_database).run_once()
    with pytest.raises(DBAPIError), core_database.engine.begin() as connection:
        connection.execute(text(mutation))


def test_lineage_bind_is_idempotent_fenced_and_audit_rollback_is_atomic(
    driver, core_database, monkeypatch
):
    driver.event("USER_SUBMITTED")
    lease = claim(core_database)
    task = start(core_database, lease)
    prepared = AgentRuntime(MockModelProvider()).prepare(task)
    original = TaskHistory.audit

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(TaskHistory, "audit", fail_audit)
    with core_database.session() as session, pytest.raises(RuntimeError):
        PromptLineageService(session).bind(lease, prepared)
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(PromptLineageModel)) == 0
    monkeypatch.setattr(TaskHistory, "audit", original)
    for _ in range(2):
        with core_database.session() as session:
            assert PromptLineageService(session).bind(lease, prepared)
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(PromptLineageModel)) == 1
    with core_database.session() as session:
        assert not PromptLineageService(session).bind(replace(lease, token=uuid4()), prepared)
    assert (
        complete(core_database, lease, AgentRuntime(MockModelProvider()).execute(task, prepared))
        == "APPLIED"
    )
    with core_database.session() as session:
        assert not PromptLineageService(session).bind(lease, prepared)


def test_repository_does_not_commit_and_composite_fk_rejects_wrong_task(
    driver, core_database, monkeypatch
):
    driver.event("USER_SUBMITTED")
    lease = claim(core_database)
    task = start(core_database, lease)
    prepared = AgentRuntime(MockModelProvider()).prepare(task)
    with core_database.session() as session:
        assert PromptLineageService(session).bind(lease, prepared)
    old = lineage(core_database, lease.run_id)
    # Use a second valid run and exercise repository flush visibility/rollback directly.
    assert (
        complete(
            core_database, lease, AgentRuntime(MockModelProvider("FORMAT_ERROR_ONCE")).execute(task)
        )
        == "RETRY_SCHEDULED"
    )
    second = claim(core_database)
    copied = replace(old, lineage_id=uuid4(), agent_run_id=second.run_id)
    with core_database.session() as session:
        monkeypatch.setattr(session, "commit", lambda: pytest.fail("Repository committed"))
        PromptLineageRepository(session).add(copied)
        with core_database.session() as other:
            assert PromptLineageRepository(other).for_run(second.run_id) is None
        session.rollback()
    with core_database.session() as session, pytest.raises(DBAPIError):
        PromptLineageRepository(session).add(replace(copied, task_id=uuid4()))


def test_two_concurrent_lineage_binds_are_idempotent(driver, core_database):
    driver.event("USER_SUBMITTED")
    lease = claim(core_database)
    task = start(core_database, lease)
    prepared = AgentRuntime(MockModelProvider()).prepare(task)
    barrier = Barrier(2)

    def bind():
        barrier.wait(timeout=5)
        with core_database.session() as session:
            return PromptLineageService(session).bind(lease, prepared)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(bind) for _ in range(2)]
        assert [future.result(timeout=10) for future in futures] == [True, True]
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(PromptLineageModel)) == 1


def test_late_result_with_lineage_cannot_revive_cancelled_workflow(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)
    runtime = AgentRuntime(MockModelProvider())
    prepared = runtime.prepare(task)
    with core_database.session() as session:
        assert PromptLineageService(session).bind(lease, prepared)
    before = asdict(lineage(core_database, lease.run_id))
    assert driver.event("CANCEL").status_code == 200
    assert complete(core_database, lease, runtime.execute(task, prepared)) == "STALE_IGNORED"
    assert asdict(lineage(core_database, lease.run_id)) == before
    assert driver.client.get(driver.chapter_api + "/plans").json() == []


@pytest.mark.parametrize("mutation", ["body", "metadata"])
def test_concurrent_different_projects_cannot_publish_conflicting_module_hashes(
    driver, core_database, copied_library, mutation
):
    driver.event("USER_SUBMITTED")
    first_lease = claim(core_database)
    first_task = start(core_database, first_lease)
    first = AgentRuntime(MockModelProvider(), prompts=PromptRegistry(copied_library)).prepare(
        first_task
    )
    project = driver.client.post(
        "/api/v1/projects", json={"name": "Concurrent prompt binding"}
    ).json()
    chapter_url = f"/api/v1/projects/{project['id']}/chapters"
    chapter = driver.client.post(chapter_url, json={"sequence": 1, "title": "Other project"}).json()
    other = type(driver)(driver.client, chapter_url + "/" + chapter["id"])
    other.event("USER_SUBMITTED")
    second_lease = claim(core_database)
    second_task = start(core_database, second_lease)
    path = copied_library / "agents/simulation-role/v1"
    if mutation == "body":
        changed = "A different body at the same module version\n"
        (path / "content.md").write_text(changed)
        edit_manifest(path / "manifest.json", content_hash=digest(changed))
    else:
        edit_manifest(path / "manifest.json", compatible_agents=["A02_REQUIREMENT"])
    second = AgentRuntime(MockModelProvider(), prompts=PromptRegistry(copied_library)).prepare(
        second_task
    )
    barrier = Barrier(2)

    def bind(lease, prepared):
        barrier.wait(timeout=5)
        try:
            with core_database.session() as session:
                return "BOUND" if PromptLineageService(session).bind(lease, prepared) else "LOST"
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(bind, lease, prepared)
            for lease, prepared in ((first_lease, first), (second_lease, second))
        ]
        assert sorted(f.result(timeout=10) for f in futures) == ["BOUND", "VERSION_CONFLICT"]
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(PromptLineageModel)) == 1
