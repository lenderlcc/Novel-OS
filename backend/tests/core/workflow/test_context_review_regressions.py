"""Review regressions through Core services, PostgreSQL and the production Worker."""

from shutil import copytree
from uuid import UUID

import pytest
from agent_test_support import complete, pending_task, task_record
from sqlalchemy import text

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.context import ContextStatus, SourceType
from novel_os.domain.enums import Authority
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.services.context import ContextService
from novel_os.services.versioning import PlanningService
from novel_os.worker import AgentWorker
from tests.core.workflow.test_context_engine import begin_context, chapter, plan, post

pytestmark = pytest.mark.integration


def writing_with_locked_artifact(driver, database, monkeypatch, kind):
    project_url = driver.chapter_api.split("/chapters/")[0]
    future = chapter(driver.client, project_url, 2)
    dependency_id = future.split("/")[-1]
    if kind == "CHAPTER_PLAN":
        plan(driver.client, future, objective="Explicitly locked future direction")
    else:
        post(
            driver.client,
            future + "/versions",
            {"expected_version": 0, "content": "Explicitly locked body", "change_reason": "Pin"},
        )
    lock = post(
        driver.client,
        project_url + "/locks",
        {"target_type": kind, "target_id": dependency_id, "expected_version": 1},
    )
    assert lock["previous_status"] in {"DRAFT", "PROPOSED"}
    original = PlanningService.create_version_in_transaction

    def with_dependency(service, project_id, chapter_id, payload, *args):
        if chapter_id == UUID(driver.workflow["chapter_id"]):
            payload = {
                **payload,
                "locked_dependencies": [{"object_type": kind, "object_id": dependency_id}],
            }
        return original(service, project_id, chapter_id, payload, *args)

    # Supply a plan fixture through the existing transaction, then approve via the human gate.
    with monkeypatch.context() as patch:
        patch.setattr(PlanningService, "create_version_in_transaction", with_dependency)
        driver.advance_to("C07_WRITING")
    lease, task, built = begin_context(driver, database, "C07_WRITING")
    assert built.status == ContextStatus.READY
    package = built.package
    assert package.profile_version == 2
    dependency = next(i for i in package.items if i.logical_id == UUID(dependency_id))
    assert dependency.source_type == SourceType(kind)
    assert dependency.source_version == 1 and dependency.locked
    assert dependency.status == "LOCKED"
    assert dependency.authority_level == Authority.A1_USER_LOCKED
    assert dependency.future_knowledge
    assert dependency.ref in package.request.required_refs
    # Publishing v2 must not relax the APPROVED policy of historical v1 profiles.
    with database.session() as session:
        service = ContextService(session)
        v1 = service.registry.resolve("CP-005", 1)
        batch = service.query.query(package.request, v1, service.tasks.clock(), task.created_at)
        old_result = service.engine.build(package.request, v1, batch)
        assert old_result.error_code == "CONTEXT_MISSING"
        assert not any(i.logical_id == UUID(dependency_id) for i in old_result.package.items)
    return project_url, lock, lease, task, package


@pytest.mark.parametrize("kind", ["CHAPTER_PLAN", "CHAPTER_VERSION"])
def test_locked_unapproved_dependency_can_drive_writing(driver, core_database, monkeypatch, kind):
    _, _, lease, task, package = writing_with_locked_artifact(
        driver, core_database, monkeypatch, kind
    )
    runtime = AgentRuntime(MockModelProvider())
    result = runtime.execute(task, runtime.prepare(task, package))
    assert result.error_code is None
    assert complete(core_database, lease, result) == "APPLIED"
    assert task_record(core_database, task.task_id).status == "SUCCEEDED"
    assert len(driver.client.get(driver.chapter_api + "/versions").json()) == 1


@pytest.mark.parametrize("kind", ["CHAPTER_PLAN", "CHAPTER_VERSION"])
def test_unlocking_unapproved_dependency_invalidates_package_and_result(
    driver, core_database, monkeypatch, kind
):
    project_url, lock, lease, task, package = writing_with_locked_artifact(
        driver, core_database, monkeypatch, kind
    )
    runtime = AgentRuntime(MockModelProvider())
    result = runtime.execute(task, runtime.prepare(task, package))
    assert result.error_code is None
    post(driver.client, project_url + "/locks/" + lock["id"] + "/release", {"expected_version": 1})
    with core_database.session() as session:
        assert (
            ContextService(session).validate_before_model(lease, package).status
            == ContextStatus.STALE
        )
    assert complete(core_database, lease, result) == "BLOCKED"
    assert driver.client.get(driver.chapter_api + "/versions").json() == []


def test_historical_v1_package_remains_usable_after_v2_publication(
    driver, core_database, monkeypatch
):
    def pinned_v1(registry, task_type):
        assert task_type == "MOCK_WRITE"
        return registry.resolve("CP-005", 1)

    driver.advance_to("C07_WRITING")
    with monkeypatch.context() as patch:
        patch.setattr(ContextProfileRegistry, "for_task", pinned_v1)
        lease, task, built = begin_context(driver, core_database, "C07_WRITING")
    package = built.package
    snapshot = ContextSerializer.snapshot(package)
    assert package.profile_version == 1
    assert ContextProfileRegistry().for_task(task.task_type).version == 2
    with core_database.session() as session:
        assert (
            ContextService(session).validate_before_model(lease, package).status
            == ContextStatus.READY
        )
        assert (
            ContextSerializer.snapshot(ContextPackageRepository(session).for_run(lease.run_id))
            == snapshot
        )
    runtime = AgentRuntime(MockModelProvider())
    result = runtime.execute(task, runtime.prepare(task, package))
    assert result.error_code is None
    assert complete(core_database, lease, result) == "APPLIED"


def test_profile_library_failure_during_model_call_finishes_without_retry(
    driver, core_database, monkeypatch, tmp_path
):
    library = copytree(ContextProfileRegistry().root, tmp_path / "profiles")
    original = ContextProfileRegistry.__init__

    def local_library(registry, root=None):
        original(registry, root or library)

    monkeypatch.setattr(ContextProfileRegistry, "__init__", local_library)
    driver.advance_to("C07_WRITING")
    task_id = UUID(pending_task(driver)["task_id"])

    class ChangedLibraryProvider(MockModelProvider):
        calls = 0

        def generate(self, request):
            self.calls += 1
            result = super().generate(request)
            (library / "broken.json").write_text("invalid JSON")
            return result

    provider = ChangedLibraryProvider()
    assert AgentWorker(core_database, AgentRuntime(provider)).run_once()
    task = task_record(core_database, task_id)
    assert provider.calls == 1
    assert task.status == "BLOCKED" and task.attempt_count == 1
    assert task.last_error_code == "CONTEXT_CONFIGURATION_ERROR"
    assert task.completed_at is not None and task.lease_token is None
    assert driver.refresh()["current_state"] == "C90_BLOCKED"
    assert driver.client.get(driver.chapter_api + "/versions").json() == []
    with core_database.session() as session:
        run = AgentTaskRepository(session).run(task.result_ref)
        assert run.status == "FAILED" and run.finished_at is not None
        assert run.error_code == "CONTEXT_CONFIGURATION_ERROR" and run.disposition == "BLOCKED"
        package = ContextPackageRepository(session).for_run(run.run_id)
        assert package.build_status == ContextStatus.READY
        assert (
            session.scalar(
                text("SELECT count(*) FROM agent_runs WHERE task_id=:id"), {"id": task_id}
            )
            == 1
        )
