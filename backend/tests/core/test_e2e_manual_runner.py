"""Manual acceptance controls exercise formal APIs without executing any Provider."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.integration
RUNNER_PATH = Path(__file__).resolve().parents[3] / "evals/e2e/multi-chapter/run.py"
SPEC = importlib.util.spec_from_file_location("e2e_manual_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_readonly_planning_export_paginates_exploration_evidence():
    calls = []
    first = [{"id": f"exploration-{index}"} for index in range(200)]
    last = {"id": "exploration-200"}

    def transport(request):
        calls.append((request.method, dict(request.url.params)))
        assert request.url.path == "/workflows/example/planning/history"
        return httpx.Response(
            200,
            json={
                "briefs": [{"id": "brief"}] if request.url.params["offset"] == "0" else [],
                "plans": [] if request.url.params["offset"] == "0" else [{"id": "plan"}],
                "reviews": [],
                "explorations": first if request.url.params["offset"] == "0" else [last],
            },
        )

    with httpx.Client(
        base_url="http://local-e2e", transport=httpx.MockTransport(transport)
    ) as client:
        history = runner.planning_history(client, "/workflows/example/planning/history")

    assert history == {
        "briefs": [{"id": "brief"}],
        "plans": [{"id": "plan"}],
        "reviews": [],
        "explorations": first + [last],
    }
    assert calls == [
        ("GET", {"limit": "200", "offset": "0"}),
        ("GET", {"limit": "200", "offset": "200"}),
    ]


def test_manual_init_start_and_readonly_trace_use_real_api_shapes(
    core_client, core_settings, tmp_path
):
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        result = core_client.request(
            request.method,
            "/api/v1" + str(request.url.raw_path, "utf-8"),
            content=request.content,
            headers={"content-type": "application/json"},
        )
        return httpx.Response(result.status_code, content=result.content)

    args = SimpleNamespace(
        state=tmp_path / "project.json",
        chapter=1,
        allow_real_provider=True,
        worker_stopped=True,
    )
    with httpx.Client(
        base_url="http://local-e2e", transport=httpx.MockTransport(transport)
    ) as client:
        runner.initialize(client, args)
        state = runner.load(args.state)
        project = runner.owned_project(client, state)
        assert project["metadata"]["e2e_scenario"] == "E2E-001"
        assert not state["chapters"]
        assert (
            runner.get(client, f"/projects/{state['project_id']}/writing-profile/approved") is None
        )
        runner.request(
            client,
            "POST",
            f"/projects/{state['project_id']}/writing-profile/approve",
            {"expected_version": 1},
        )
        runner.start_chapter(client, args, state)
        flow = runner.workflow(client, state, 1)
        assert flow["current_state"] == "C01_REQUIREMENT_INTAKE"
        assert flow["workflow_definition_version"] == 3
        pending = runner.ensure_idle_queue(client, flow["id"])
        assert len(pending) == 1
        assert pending[0]["task_type"] == "PARSE_CHAPTER_REQUIREMENT"
        assert pending[0]["attempt_count"] == 0
        # The Worker config's database must contain the exact audited owned scope.
        runner.verify_worker_database(core_settings, state, flow, pending)
        with pytest.raises(ValueError, match="owned E2E scope"):
            runner.verify_worker_database(
                core_settings, {**state, "run_id": "another-run"}, flow, pending
            )
        with pytest.raises(ValueError, match="missing"):
            runner.verify_worker_database(
                core_settings, {**state, "project_id": str(uuid4())}, flow, pending
            )
        with pytest.raises(ValueError, match="differs"):
            runner.verify_worker_database(
                core_settings, state, flow, [{**pending[0], "objective": "unaudited task"}]
            )

        export_start = len(calls)
        output = tmp_path / "before-model.json"
        runner.export(client, state, output)
        assert all(method == "GET" for method, _ in calls[export_start:])
        trace = json.loads(output.read_text())
        assert trace["execution_kind"] == "NO_MODEL_ATTEMPT"
        assert not trace["lineage_errors"]
        assert trace["ai_behavior_acceptance"] == "PENDING_HUMAN_REVIEW"
        assert trace["human_prose_evaluation"] == "PENDING"
        assert len(trace["chapters"]) == 1
        assert trace["chapters"][0]["workflow"]["id"] == flow["id"]
        assert not trace["chapters"][0]["versions"]
        assert not trace["chapters"][0]["runs"]
        assert trace["chapters"][0]["planning"]["explorations"] == []

        # No second chapter can silently bypass the previous human Memory gate.
        args.chapter = 2
        with pytest.raises(ValueError, match="pending/leased"):
            runner.start_chapter(client, args, state)
        runner.request(
            client,
            "POST",
            f"/workflows/{flow['id']}/cancel",
            runner.command_body(flow, "Check chapter completion gate"),
        )
        with pytest.raises(ValueError, match="Previous Chapter"):
            runner.start_chapter(client, args, state)
        chapters = runner.pages(client, f"/projects/{state['project_id']}/chapters")
        assert len(chapters) == 1
        assert not runner.pages(client, f"/agent-tasks/{pending[0]['task_id']}/runs")


def test_manual_memory_confirmation_uses_actual_proposal_candidate_ids(
    core_client, chapter_api, core_database
):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.quality.test_memory_commit import prepare

    driver = QualityDriver(core_client, chapter_api).approve_plan(core_database)
    prepare(driver, core_database)
    proposal = driver.client.get(driver.url + "/memory").json()[0]["proposal"]
    assert proposal["candidates"]
    assert "id" in proposal["candidates"][0]
    assert "candidate_id" not in proposal["candidates"][0]
    selected = proposal["candidates"][0]["id"]

    def transport(request):
        result = core_client.request(
            request.method,
            "/api/v1" + str(request.url.raw_path, "utf-8"),
            content=request.content,
            headers={"content-type": "application/json"},
        )
        return httpx.Response(result.status_code, content=result.content)

    args = SimpleNamespace(
        action="confirm-memory",
        proposal_id=proposal["id"],
        candidate=[selected],
        confirm_empty=False,
    )
    with httpx.Client(
        base_url="http://local-e2e", transport=httpx.MockTransport(transport)
    ) as client:
        runner.mutate_workflow(client, args, driver.workflow)
        committed = runner.get(client, f"/workflows/{driver.workflow['id']}/memory")[0]
    assert committed["status"] == "COMMITTED"
    assert committed["batch"]["selected_candidate_ids"] == [selected]
    assert committed["entries"][0]["candidate_id"] == selected


def test_manual_worker_refuses_stale_migration_before_model(core_settings, monkeypatch):
    from alembic.runtime.migration import MigrationContext

    monkeypatch.setattr(
        MigrationContext,
        "configure",
        lambda *args, **kwargs: SimpleNamespace(get_current_heads=lambda: ("old-head",)),
    )
    # Missing Project/Workflow identities cannot be reached before the head check.
    with pytest.raises(ValueError, match="migration differs"):
        runner.verify_worker_database(core_settings, {}, {}, [])


@pytest.mark.parametrize("failure", ["wrong-database", "stale-head"])
def test_manual_paid_step_never_starts_worker_with_failed_preflight(
    core_settings, monkeypatch, tmp_path, failure
):
    from alembic.runtime.migration import MigrationContext

    from novel_os.core.config import Settings

    settings = core_settings.model_copy(
        update={
            "agent_model_profile": "lingzhi-structured",
            "agent_execution_scope": "chapter-quality",
            "agent_max_attempts": 1,
        }
    )
    monkeypatch.setattr(Settings, "from_file", classmethod(lambda cls, path: settings))
    monkeypatch.setattr(runner, "ensure_idle_queue", lambda *args: [{"task_id": str(uuid4())}])
    worker_calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: worker_calls.append(args))
    if failure == "stale-head":
        monkeypatch.setattr(
            MigrationContext,
            "configure",
            lambda *args, **kwargs: SimpleNamespace(get_current_heads=lambda: ("old-head",)),
        )
    flow = {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "chapter_id": str(uuid4()),
        "current_state": "C01_REQUIREMENT_INTAKE",
        "status": "WAITING_AGENT",
        "state_version": 2,
    }
    state = {"project_id": flow["project_id"], "run_id": str(uuid4())}
    args = SimpleNamespace(
        allow_real_provider=True,
        worker_stopped=True,
        stage=flow["current_state"],
        config=tmp_path / "unused-by-mocked-settings.toml",
    )
    with (
        httpx.Client(
            base_url="http://local-e2e",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"model_profile": "lingzhi-structured"})
            ),
        ) as client,
        pytest.raises(ValueError, match="migration differs|missing"),
    ):
        runner.one_task(client, args, state, flow)
    assert not worker_calls


def test_selected_character_preparation_uses_real_ids_drafts_and_explicit_approval(
    core_client, tmp_path
):
    calls = []

    def transport(request):
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        response = core_client.request(
            request.method,
            "/api/v1" + str(request.url.raw_path, "utf-8"),
            content=request.content,
            headers={"content-type": "application/json"},
        )
        return httpx.Response(response.status_code, content=response.content)

    args = SimpleNamespace(
        state=tmp_path / "characters.json",
        test_id="014R",
        case="CDV-01-same-pressure",
        variant="A",
        chapter=1,
        allow_real_provider=True,
        worker_stopped=True,
    )
    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.prepare_case(client, args)
        state = runner.load(args.state)
        base = f"/projects/{state['project_id']}"
        assert len(state["character_id_mapping"]) == 3
        assert all(
            fixture_id != actual_id
            for fixture_id, actual_id in state["character_id_mapping"].items()
        )
        assert len(state["required_profiles"]) == 1
        character_id = next(iter(state["required_profiles"]))
        profile_base = base + f"/characters/{character_id}/behavior-profile"
        profile = runner.get(client, profile_base)["current"]
        assert (
            profile["status"] == "DRAFT" and runner.get(client, profile_base + "/approved") is None
        )
        assert {
            modifier["other_character_id"] for modifier in profile["relationship_modifiers"]
        } <= set(state["character_id_mapping"].values())
        runner.request(client, "POST", base + "/writing-profile/approve", {"expected_version": 1})
        with pytest.raises(ValueError, match="Human approval"):
            runner.start_chapter(client, args, state)
        assert not state["chapters"]
        runner.request(client, "POST", profile_base + "/approve", {"expected_version": 1})
        runner.start_chapter(client, args, state)
        flow = runner.workflow(client, state, 1)
        assert flow["workflow_definition_version"] == 4
        submitted = next(
            body
            for method, path, body in calls
            if method == "POST" and path == "/workflows/chapter-exploration"
        )
        assert submitted["raw_requirement"] == state["selected_input"]["raw_requirement"]
        assert set(submitted) == {"project_id", "chapter_id", "event_id", "raw_requirement"}
        runner.request(
            client,
            "POST",
            profile_base + "/drafts",
            {"expected_version": 1, "profile": {"communication_style": "更简短"}},
        )
        readonly_start = len(calls)
        runner.export(client, state, tmp_path / "evidence.json")
        assert all(method == "GET" for method, _, _ in calls[readonly_start:])
        evidence = runner.load(tmp_path / "evidence.json")
        exported = next(
            row for row in evidence["character_profiles"] if row["character"]["id"] == character_id
        )
        assert exported["state"]["current_profile_version"] == 2
        assert exported["state"]["approved_profile_version"] == 1
        assert {version["version"] for version in exported["versions"]} == {1, 2}
        assert not exported["runs"] and evidence["execution_kind"] == "NO_MODEL_ATTEMPT"
