"""Historical acceptance profile pins are checked before API writes or Worker dispatch."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

RUNNER_PATH = Path(__file__).resolve().parents[2] / "evals/e2e/multi-chapter/run.py"
SPEC = importlib.util.spec_from_file_location("acceptance_profile_binding_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def historical_case(tmp_path):
    args = SimpleNamespace(
        test_id="013R",
        case="case-03-historical-small-setback",
        state=tmp_path / "state.json",
        project_id="comparison-project",
        chapter=1,
        allow_real_provider=True,
        worker_stopped=True,
        config=tmp_path / "unused-config.toml",
    )
    runner.prepare_case(None, args)
    state = runner.load(args.state)
    historical = runner.load(runner.ROOT / "evals/creative-exploration/case-03.json")
    baseline, pins = historical["A"], historical["comparable_inputs"]
    approved = {
        "id": "comparison-profile-v1",
        "version": pins["writing_profile_version"],
        "profile_hash": pins["writing_profile_hash"],
        "status": "APPROVED",
        "target_audience": "主流中文网络小说读者",
        "narrative_perspective": None,
    }
    api = SimpleNamespace(approved=approved, draft=None, calls=[])
    project_path = f"/projects/{args.project_id}"

    def transport(request):
        api.calls.append((request.method, request.url.path))
        if request.method == "POST":
            if request.url.path == project_path + "/chapters":
                return httpx.Response(200, json={"id": "comparison-chapter"})
            if request.url.path == "/workflows/chapter-exploration":
                return httpx.Response(
                    200, json={"workflow": {"id": "comparison-workflow", "state_version": 1}}
                )
            if request.url.path == "/workflows/comparison-workflow/events":
                return httpx.Response(200, json={})
            pytest.fail(f"Unexpected API mutation: {request.method} {request.url.path}")
        responses = {
            "/projects": [],
            project_path: {
                "id": args.project_id,
                "metadata": {
                    "e2e_run_id": state["run_id"],
                    "e2e_scenario": state["scenario_id"],
                    "e2e_fixture_hash": state["fixture_hash"],
                },
            },
            project_path + "/writing-profile/approved": api.approved,
            project_path + "/writing-profile": {
                "current_profile_version": (api.draft or api.approved)["version"],
                "approved_profile_version": api.approved["version"],
                "current": api.draft or api.approved,
                "approved": api.approved,
            },
            project_path + "/writing-profile/versions": [api.approved]
            + ([api.draft] if api.draft else []),
            project_path + "/chapters": [],
            project_path + "/requirements": [],
            project_path + "/decisions": [],
            project_path + "/memory": [],
            project_path + "/locks": [],
            f"/context-packages/{baseline['context_package_id']}": {
                "package": {
                    "project_id": baseline["project_id"],
                    "items": [
                        {
                            "source_type": "PROJECT_WRITING_PROFILE",
                            "source_version": pins["writing_profile_version"],
                            "payload_json": json.dumps(
                                {"writing_profile_hash": pins["writing_profile_hash"]}
                            ),
                        }
                    ],
                }
            },
            f"/projects/{baseline['project_id']}/writing-profile/versions": [
                {**approved, "id": "historical-profile-v1"}
            ],
            f"/projects/{baseline['project_id']}/chapters/{baseline['chapter_id']}/plans": [
                {"id": baseline["plan_id"]}
            ],
        }
        if request.url.path not in responses:
            pytest.fail(f"Unexpected API read: {request.url.path}")
        return httpx.Response(200, json=responses[request.url.path])

    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.check_prerequisites(client, args, state)
        assert state["blocked_reasons"] == []
        assert state["prerequisite_evidence"]["writing_profile"] == {
            "id": approved["id"],
            "version": approved["version"],
            "profile_hash": approved["profile_hash"],
        }
        assert all(method == "GET" for method, _ in api.calls)
        api.calls.clear()
        yield client, args, state, api


@pytest.mark.parametrize(
    "replacement",
    [
        {"id": "replacement-profile-v1"},
        {"version": 2},
        {"profile_hash": "replacement-hash"},
        {
            "id": "comparison-profile-v2",
            "version": 2,
            "profile_hash": "approved-v2-hash",
            "narrative_perspective": "THIRD_PERSON",
        },
    ],
    ids=["id-changed", "version-changed", "hash-changed", "approved-v2-new-pov"],
)
def test_historical_start_rejects_changed_approved_profile_before_api_writes(
    historical_case, monkeypatch, replacement
):
    client, args, state, api = historical_case
    api.approved = {**api.approved, **replacement}
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("No paid dispatch")
    )

    with pytest.raises(ValueError, match="Approved Writing Profile changed"):
        runner.start_chapter(client, args, state)

    assert all(method == "GET" for method, _ in api.calls)
    assert state["chapters"] == {}
    assert runner.load(args.state)["chapters"] == {}


@pytest.mark.parametrize("new_draft", [False, True], ids=["same-approved", "new-unapproved-draft"])
def test_historical_start_accepts_pinned_approved_profile_with_optional_new_draft(
    historical_case, new_draft
):
    client, args, state, api = historical_case
    if new_draft:
        api.draft = {
            **api.approved,
            "id": "comparison-profile-v2",
            "version": 2,
            "status": "DRAFT",
            "profile_hash": "draft-v2-hash",
            "narrative_perspective": "THIRD_PERSON",
        }

    runner.start_chapter(client, args, state)

    assert state["chapters"]["1"]["chapter_id"] == "comparison-chapter"
    assert [(method, path) for method, path in api.calls if method == "POST"] == [
        ("POST", "/projects/comparison-project/chapters"),
        ("POST", "/workflows/chapter-exploration"),
        ("POST", "/workflows/comparison-workflow/events"),
    ]


def test_historical_paid_step_rechecks_profile_pin_before_settings_database_or_dispatch(
    historical_case, monkeypatch
):
    from novel_os.core.config import Settings

    client, args, state, api = historical_case
    api.approved = {
        **api.approved,
        "id": "comparison-profile-v2",
        "version": 2,
        "profile_hash": "approved-v2-hash",
        "narrative_perspective": "THIRD_PERSON",
    }
    flow = {
        "id": "comparison-workflow",
        "current_state": "C04_CHAPTER_PLANNING",
        "status": "WAITING_AGENT",
    }
    args.stage = flow["current_state"]
    monkeypatch.setattr(
        runner, "ensure_idle_queue", lambda *args: [{"task_id": "task", "attempt_count": 0}]
    )
    monkeypatch.setattr(
        Settings,
        "from_file",
        classmethod(lambda *args: pytest.fail("Changed Profile must stop before Worker config")),
    )
    monkeypatch.setattr(
        runner,
        "verify_worker_database",
        lambda *args: pytest.fail("Changed Profile must stop before database preflight"),
    )
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: pytest.fail("No paid dispatch")
    )

    with pytest.raises(ValueError, match="Approved Writing Profile changed"):
        runner.one_task(client, args, state, flow)

    assert all(method == "GET" for method, _ in api.calls)
    assert state["started_at"] is None
    assert runner.load(args.state)["started_at"] is None
