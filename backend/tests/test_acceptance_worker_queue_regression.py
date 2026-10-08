"""Acceptance checks use isolated test DBs and the existing Mock Worker only."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from novel_os.core.config import Settings
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.task_scheduling import TaskScheduler
from tests.core.conftest import core_client as core_client
from tests.core.conftest import core_database as core_database
from tests.core.conftest import core_settings as core_settings
from tests.core.conftest import migration_config as migration_config
from tests.core.workflow.agent_test_support import runs, task_record, worker
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver

pytestmark = pytest.mark.integration
RUNNER_PATH = Path(__file__).resolve().parents[2] / "evals/e2e/multi-chapter/run.py"
SPEC = importlib.util.spec_from_file_location("acceptance_worker_queue_regression", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def acceptance_scope(core_client, core_database, core_settings, tmp_path):
    owned_project_id = None
    owned_chapter_id = None

    def transport(request):
        if request.url.path == "/agent-execution/config":
            return httpx.Response(
                200, json={"model_profile": "lingzhi-structured", "provider": "lingzhi"}
            )
        result = core_client.request(
            request.method,
            "/api/v1" + str(request.url.raw_path, "utf-8"),
            content=request.content,
            headers={"content-type": "application/json"},
        )
        if owned_project_id and request.method == "GET" and request.url.path == "/projects":
            # Simulate an API DB containing the owned scope while the Worker DB is a superset.
            return httpx.Response(
                result.status_code,
                json=[project for project in result.json() if project["id"] == owned_project_id],
            )
        if (
            owned_chapter_id
            and request.method == "GET"
            and request.url.path == f"/projects/{owned_project_id}/chapters"
        ):
            return httpx.Response(
                result.status_code,
                json=[chapter for chapter in result.json() if chapter["id"] == owned_chapter_id],
            )
        return httpx.Response(result.status_code, content=result.content)

    args = SimpleNamespace(
        state=tmp_path / "acceptance.json",
        config=tmp_path / "not-read.toml",
        chapter=1,
        allow_real_provider=True,
        worker_stopped=True,
    )
    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.initialize(client, args)
        state = runner.load(args.state)
        runner.request(
            client,
            "POST",
            f"/projects/{state['project_id']}/writing-profile/approve",
            {"expected_version": 1},
        )
        runner.start_chapter(client, args, state)
        flow = runner.workflow(client, state, 1)
        owned_project_id = state["project_id"]
        owned_chapter_id = flow["chapter_id"]
        args.stage = flow["current_state"]
        settings = core_settings.model_copy(
            update={
                "agent_model_profile": "lingzhi-structured",
                "agent_execution_scope": "chapter-quality",
                "agent_max_attempts": 1,
            }
        )
        yield SimpleNamespace(
            client=client,
            api=core_client,
            database=core_database,
            settings=settings,
            args=args,
            state=state,
            flow=flow,
            pending=runner.ensure_idle_queue(client, flow["id"]),
        )


def foreign_driver(scope, *, same_project=False):
    project_id = (
        scope.state["project_id"]
        if same_project
        else runner.request(scope.client, "POST", "/projects", {"name": "Foreign queue"})["id"]
    )
    chapter = runner.request(
        scope.client,
        "POST",
        f"/projects/{project_id}/chapters",
        {"sequence": 2 if same_project else 1, "title": "Foreign chapter"},
    )
    return PlanningDriver(scope.api, f"/api/v1/projects/{project_id}/chapters/{chapter['id']}")


def foreign_task(scope, monkeypatch, *, same_project=False):
    synchronize = TaskScheduler.synchronize

    def high_priority(*args, **kwargs):
        return synchronize(*args, **{**kwargs, "priority": 100})

    with monkeypatch.context() as patch:
        patch.setattr(TaskScheduler, "synchronize", high_priority)
        driver = foreign_driver(scope, same_project=same_project)
    return UUID(driver.read("/agent-tasks")[0]["task_id"])


def test_actual_worker_database_accepts_the_exact_audited_queue(acceptance_scope):
    scope = acceptance_scope
    before = task_record(scope.database, UUID(scope.pending[0]["task_id"]))
    runner.verify_worker_database(scope.settings, scope.state, scope.flow, scope.pending)
    assert task_record(scope.database, before.task_id) == before
    assert runs(scope.database, before.task_id) == []


@pytest.mark.parametrize(
    ("status", "expired", "same_project"),
    [
        ("PENDING", False, False),
        ("PENDING", False, True),
        ("CLAIMED", False, False),
        ("RUNNING", False, False),
        ("CLAIMED", True, False),
        ("RUNNING", True, False),
    ],
)
def test_actual_worker_database_extra_task_blocks_before_worker_launch(
    acceptance_scope, monkeypatch, status, expired, same_project
):
    scope = acceptance_scope
    task_id = foreign_task(scope, monkeypatch, same_project=same_project)
    if status != "PENDING":
        with scope.database.session() as session:
            lease = AgentQueue(session).claim("foreign-fixture", task_ids=(task_id,))
        assert lease.task_id == task_id
        if status == "RUNNING":
            with scope.database.session() as session:
                assert AgentQueue(session).start(lease) is not None
        if expired:
            with scope.database.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE agent_tasks SET lease_expires_at=clock_timestamp()-"
                        "INTERVAL '1 second', version=version+1 WHERE task_id=:id"
                    ),
                    {"id": task_id},
                )
    # The API audit cannot see a foreign Project, or another chapter of the owned Project.
    assert runner.ensure_idle_queue(scope.client, scope.flow["id"]) == scope.pending
    monkeypatch.setattr(Settings, "from_file", classmethod(lambda cls, path: scope.settings))
    worker_calls = []

    def unexpected_worker(*args, **kwargs):
        worker_calls.append(args)
        pytest.fail("Failed queue preflight must not launch a Worker or real Provider")

    monkeypatch.setattr(runner.subprocess, "run", unexpected_worker)
    before = task_record(scope.database, task_id)
    with pytest.raises(ValueError, match="outside the audited API scope"):
        runner.verify_worker_database(scope.settings, scope.state, scope.flow, scope.pending)
    with pytest.raises(ValueError, match="outside the audited API scope"):
        runner.one_task(scope.client, scope.args, scope.state, scope.flow)
    assert worker_calls == []
    assert task_record(scope.database, task_id) == before
    assert runs(scope.database, UUID(scope.pending[0]["task_id"])) == []


def test_standard_worker_claim_stays_on_audited_ids_after_foreign_task_arrives(
    acceptance_scope, monkeypatch
):
    scope = acceptance_scope
    runner.verify_worker_database(scope.settings, scope.state, scope.flow, scope.pending)
    task_id = UUID(scope.pending[0]["task_id"])
    foreign_id = foreign_task(scope, monkeypatch)
    with scope.database.session() as session:
        # Confirm the concurrent foreign task would win the original global claim.
        assert (
            AgentTaskRepository(session)
            .next_claimable(task_types=scope.settings.agent_task_types)
            .task_id
            == foreign_id
        )
    foreign_before = task_record(scope.database, foreign_id)
    scoped = worker(
        scope.database,
        task_types=scope.settings.agent_task_types,
        task_ids=(task_id,),
        max_attempts=1,
    )
    assert scoped.run_once()
    assert scoped.run_once() is False
    owned_runs = runs(scope.database, task_id)
    assert len(owned_runs) == 1 and owned_runs[0].provider == "mock"
    assert task_record(scope.database, task_id).status == "SUCCEEDED"
    assert task_record(scope.database, foreign_id) == foreign_before
    assert runs(scope.database, foreign_id) == []


def test_empty_audited_task_ids_cannot_backfill_a_waiting_workflow(acceptance_scope, monkeypatch):
    scope = acceptance_scope
    runner.request(
        scope.client,
        "POST",
        f"/workflows/{scope.flow['id']}/cancel",
        runner.command_body(scope.flow, "Cancel the existing target before backfill regression"),
    )
    with monkeypatch.context() as patch:
        # Reproduce a legacy WAITING_AGENT workflow without its scheduled task.
        patch.setattr(TaskScheduler, "synchronize", lambda *args, **kwargs: None)
        legacy = foreign_driver(scope)
    with scope.database.session() as session:
        assert AgentQueue(session).claim("empty-audit", task_ids=()) is None
    with scope.database.session() as session:
        assert AgentTaskRepository(session).list_tasks(UUID(legacy.workflow["id"])) == []
    with scope.database.session() as session:
        # The same fixture is genuinely eligible for the standard legacy backfill.
        assert AgentQueue(session).claim("default-backfill") is not None
