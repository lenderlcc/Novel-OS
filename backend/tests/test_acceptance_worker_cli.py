"""Manual execution stays on the standard Worker with an exact audited task set."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novel_os import worker
from novel_os.core.config import Settings

RUNNER_PATH = Path(__file__).resolve().parents[2] / "evals/e2e/multi-chapter/run.py"
SPEC = importlib.util.spec_from_file_location("acceptance_worker_cli_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.parametrize("count", [1, 2])
def test_manual_attempt_passes_all_audited_ids_to_standard_worker(monkeypatch, tmp_path, count):
    pending = [{"task_id": str(uuid4()), "attempt_count": 0} for _ in range(count)]
    flow = {"id": str(uuid4()), "status": "WAITING_AGENT", "current_state": "C09_REVIEWING"}
    state = {"project_id": str(uuid4())}
    args = SimpleNamespace(
        allow_real_provider=True,
        worker_stopped=True,
        stage=flow["current_state"],
        config=tmp_path / "not-read.toml",
    )
    settings = SimpleNamespace(
        agent_execution_scope="chapter-quality",
        agent_max_attempts=1,
        agent_model_profile="lingzhi-structured",
    )
    monkeypatch.setattr(Settings, "from_file", classmethod(lambda *args: settings))
    monkeypatch.setattr(runner, "ensure_idle_queue", lambda *args: pending)
    monkeypatch.setattr(
        runner,
        "get",
        lambda *args: {
            "model_profile": settings.agent_model_profile,
            "provider": "lingzhi",
        },
    )
    preflight = []
    monkeypatch.setattr(runner, "verify_worker_database", lambda *args: preflight.append(args))
    commands = []

    def dispatch(command, **kwargs):
        assert preflight, "No Worker dispatch before the database scope check"
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", dispatch)
    after = [{**pending[0], "attempt_count": 1}, *pending[1:]]
    monkeypatch.setattr(runner, "pages", lambda *args: after)

    consumed = runner.one_task(None, args, state, flow)

    assert consumed["task_id"] == pending[0]["task_id"]
    assert len(commands) == 1
    command = commands[0]
    assert command[:4] == [runner.sys.executable, "-m", "novel_os.worker", "--once"]
    ids = [command[index + 1] for index, value in enumerate(command) if value == "--task-id"]
    assert ids == [task["task_id"] for task in pending]


def test_task_id_filter_requires_once_before_settings_or_provider(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["worker", "--task-id", str(uuid4())])
    monkeypatch.setattr(
        Settings, "from_file", classmethod(lambda *args: pytest.fail("No configuration read"))
    )

    with pytest.raises(SystemExit) as error:
        worker.main()

    assert error.value.code == 2
    assert "--task-id requires --once" in capsys.readouterr().err


@pytest.mark.parametrize("restricted", [False, True])
def test_once_cli_preserves_exact_ids_and_existing_execution_policy(monkeypatch, restricted):
    task_ids = [uuid4(), uuid4()] if restricted else None
    argv = ["worker", "--once", "--config", "not-read.toml"]
    for task_id in task_ids or []:
        argv.extend(("--task-id", str(task_id)))
    monkeypatch.setattr(sys, "argv", argv)
    settings = SimpleNamespace(
        log_level="INFO",
        agent_lease_seconds=30,
        agent_heartbeat_seconds=5,
        agent_retry_seconds=0,
        agent_task_types={"REVIEW_CHAPTER_NARRATIVE", "REVIEW_CHAPTER_COMPLIANCE"},
        agent_max_attempts=1,
    )
    monkeypatch.setattr(Settings, "from_file", classmethod(lambda *args: settings))
    monkeypatch.setattr(worker, "configure_logging", lambda *args: None)
    monkeypatch.setattr(worker.signal, "signal", lambda *args: None)
    disposed = []
    database = SimpleNamespace(dispose=lambda: disposed.append(True))
    runtime = object()
    monkeypatch.setattr(worker, "Database", lambda *args: database)
    monkeypatch.setattr(worker, "build_agent_runtime", lambda *args: runtime)
    calls = []

    def make_worker(actual_database, actual_runtime, **kwargs):
        assert actual_database is database and actual_runtime is runtime
        assert kwargs["task_ids"] == task_ids
        assert kwargs["task_types"] == settings.agent_task_types
        assert kwargs["max_attempts"] == 1
        return SimpleNamespace(run_once=lambda: calls.append(True))

    monkeypatch.setattr(worker, "AgentWorker", make_worker)

    worker.main()

    assert calls == [True]
    assert disposed == [True]
