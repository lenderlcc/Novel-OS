"""Acceptance orchestration fixtures never invoke a Worker, Provider or database."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

RUNNER_PATH = Path(__file__).resolve().parents[2] / "evals/e2e/multi-chapter/run.py"
SPEC = importlib.util.spec_from_file_location("phase2_acceptance_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_manifest_declares_real_pending_suites_and_human_prerequisites():
    manifest = runner.load(runner.MANIFEST)
    assert manifest["default_model_calls"] == 0
    assert manifest["real_provider_opt_in"] == "--allow-real-provider --worker-stopped"
    assert set(manifest["tests"]) == {"E2E-001R", "013R", "014R"}
    for test in manifest["tests"].values():
        assert test["provider_required"] and test["human_gate_required"]
        assert test["required_capabilities"] and test["prerequisites"]
        assert test["current_status"] == "PENDING"
    assert manifest["tests"]["E2E-001R"]["workflow_version"] == 3
    assert manifest["tests"]["014R"]["workflow_version"] == 4


@pytest.mark.parametrize(
    "case", ["case-03-historical-small-setback", "recent-mechanism-repetition"]
)
def test_unprepared_historical_case_is_blocked_without_api_or_model(tmp_path, case):
    def no_api(request):
        pytest.fail("Historical preparation must not fabricate runtime data")

    args = SimpleNamespace(test_id="013R", case=case, state=tmp_path / "state.json")
    with httpx.Client(base_url="http://fixture", transport=httpx.MockTransport(no_api)) as client:
        runner.prepare_case(client, args)
        state = runner.load(args.state)
        assert state["status"] == "BLOCKED" and state["project_id"] is None
        assert state["blocked_reasons"] and state["started_at"] is None
        runner.export(client, state, tmp_path / "blocked.json")
    assert runner.load(tmp_path / "blocked.json")["ai_behavior_acceptance"] == "NOT_RUN"


@pytest.mark.parametrize(
    ("status", "stage", "kind"),
    [
        ("WAITING_HUMAN", "C06_PLAN_APPROVAL", "HUMAN_GATE"),
        ("WAITING_HUMAN", "C15_MEMORY_COMMIT", "HUMAN_GATE"),
        ("RUNNING", "C11_INTERNAL_PASS", "DRAFT_REVIEW"),
        ("WAITING_HUMAN", "C10_REVISION", "DRAFT_REVIEW"),
        ("BLOCKED", "C90_BLOCKED", "BLOCKED"),
        ("FAILED", "C91_FAILED", "FAILED"),
        ("PAUSED", "C07_WRITING", "PAUSED"),
        ("COMPLETED", "C16_COMPLETED", "COMPLETED"),
    ],
)
def test_run_stops_without_worker_at_every_human_or_terminal_boundary(
    tmp_path, monkeypatch, status, stage, kind
):
    flow = {"id": "flow", "status": status, "current_state": stage, "state_version": 7}
    monkeypatch.setattr(runner, "workflow", lambda *args: flow)
    monkeypatch.setattr(runner, "one_task", lambda *args: pytest.fail("No task at this gate"))
    args = SimpleNamespace(
        state=tmp_path / "state.json",
        chapter=1,
        max_tasks=6,
        allow_real_provider=True,
        worker_stopped=True,
    )
    state = {"test_id": "014R"}
    runner.run_to_gate(None, args, state)
    assert runner.load(args.state)["stop"]["kind"] == kind
    assert state["result"] != "PASS"


@pytest.mark.parametrize("attempt_status", ["SUCCEEDED", "FAILED", "BLOCKED"])
def test_run_budget_and_failed_attempt_never_retry_implicitly(
    tmp_path, monkeypatch, attempt_status
):
    flow = {
        "id": "flow",
        "status": "WAITING_AGENT",
        "current_state": "C04_CHAPTER_PLANNING",
        "state_version": 2,
    }
    calls = []
    monkeypatch.setattr(runner, "workflow", lambda *args: flow)

    def task(*args):
        calls.append(args[1].stage)
        return {"status": attempt_status}

    monkeypatch.setattr(runner, "one_task", task)
    args = SimpleNamespace(
        state=tmp_path / "state.json",
        chapter=1,
        max_tasks=2,
        allow_real_provider=True,
        worker_stopped=True,
    )
    state = {}
    runner.run_to_gate(None, args, state)
    assert len(calls) == (2 if attempt_status == "SUCCEEDED" else 1)
    assert (
        state["stop"]["kind"]
        == {"SUCCEEDED": "TASK_BUDGET", "FAILED": "ATTEMPT_FAILED", "BLOCKED": "OUTPUT_BLOCKED"}[
            attempt_status
        ]
    )


@pytest.mark.parametrize("human_actor", ["USER", "SYSTEM"])
def test_continue_requires_persisted_human_transition_before_running(
    tmp_path, monkeypatch, human_actor
):
    flow = {
        "id": "flow",
        "status": "WAITING_AGENT",
        "current_state": "C07_WRITING",
        "state_version": 6,
    }
    transition = {"from_version": 5, "to_version": 6, "audit_record_id": "audit"}
    audit = {
        "id": "audit",
        "actor_type": human_actor,
        "after": {"workflow_id": "flow", "event_type": "USER_APPROVED"},
    }
    monkeypatch.setattr(runner, "workflow", lambda *args: flow)
    monkeypatch.setattr(
        runner, "pages", lambda client, path: [transition] if path.endswith("/history") else [audit]
    )
    calls = []

    def task(*args):
        calls.append("one")
        flow.update(status="WAITING_HUMAN", current_state="C11_INTERNAL_PASS", state_version=9)
        return {"status": "SUCCEEDED"}

    monkeypatch.setattr(runner, "one_task", task)
    args = SimpleNamespace(
        state=tmp_path / "state.json",
        chapter=1,
        max_tasks=6,
        allow_real_provider=True,
        worker_stopped=True,
    )
    state = {
        "project_id": "project",
        "stop": {"workflow_id": "flow", "state_version": 5, "kind": "HUMAN_GATE"},
    }
    if human_actor == "SYSTEM":
        with pytest.raises(ValueError, match="No recorded human"):
            runner.run_to_gate(None, args, state, continuing=True)
        assert not calls
    else:
        runner.run_to_gate(None, args, state, continuing=True)
        assert calls == ["one"]
        assert state["human_gates"][0]["audit_record_id"] == "audit"
        assert state["stop"]["kind"] == "DRAFT_REVIEW"


def test_paid_opt_in_is_required_before_any_orchestration(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "workflow", lambda *args: pytest.fail("No API before opt-in"))
    args = SimpleNamespace(
        state=tmp_path / "state.json", allow_real_provider=False, worker_stopped=True
    )
    with pytest.raises(ValueError, match="Explicit --allow-real-provider"):
        runner.run_to_gate(None, args, {})
    assert not args.state.exists()


def test_readonly_export_preserves_profiles_independent_report_trace_and_blind_mapping(tmp_path):
    task = {
        "task_id": "report",
        "workflow_instance_id": None,
        "report_character_id": "character",
        "expected_output_schema": "character-profile-draft.v1",
    }
    run = {
        "run_id": "report-run",
        "status": "SUCCEEDED",
        "provider": "mock",
        "started_at": "2026-10-07T00:00:00Z",
    }
    lineage = {
        "agent_run_id": "report-run",
        "task_id": "report",
        "output_schema_id": "character-profile-draft",
        "output_schema_version": 1,
        "model_profile_id": "mock-default",
    }
    version = {"id": "draft-v1", "content": "林遥问沈知：遥还能合作吗？", "version": 1}
    calls = []
    base = "/projects/project/characters/character/behavior-profile"
    responses = {
        "/projects/project": {"id": "project"},
        "/agent-execution/config": {"model_profile": "configured-real", "provider": "lingzhi"},
        "/projects/project/writing-profile": {},
        "/projects/project/characters": [
            {"id": "character", "name": "林遥", "aliases": ["遥"]},
            {"id": "other", "name": "沈知"},
        ],
        base: {"current_profile_version": 2, "approved_profile_version": 1},
        base + "/approved": {"id": "profile-v1", "version": 1, "profile_hash": "approved-hash"},
        base + "/versions": [
            {"id": "profile-v2", "version": 2, "status": "DRAFT"},
            {"id": "profile-v1", "version": 1, "status": "APPROVED"},
        ],
        base + "/interpretations": [task],
        "/agent-tasks/report/runs": [run],
        "/agent-runs/report-run/prompt-lineage": lineage,
        "/agent-runs/report-run/context": {"package": {"task_id": "report"}},
        "/workflows/flow": {
            "id": "flow",
            "project_id": "project",
            "chapter_id": "chapter",
            "status": "WAITING_HUMAN",
        },
        "/projects/project/chapters/chapter": {"id": "chapter"},
        "/projects/project/chapters/chapter/versions": [version],
        "/workflows/flow/planning/history": {
            "briefs": [],
            "plans": [],
            "reviews": [],
            "explorations": [{"id": "exploration"}],
        },
    }

    def transport(request):
        calls.append(request.method)
        path = request.url.path
        if path.endswith("/creative-brief"):
            return httpx.Response(404, json={})
        return httpx.Response(200, json=responses.get(path, []))

    state = {
        **runner.metadata("014R", "acceptance-run", "project"),
        "scenario_id": "014R",
        "fixture_hash": "hash",
        "chapters": {"1": {"chapter_id": "chapter", "workflow_id": "flow"}},
    }
    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.export(client, state, tmp_path / "evidence.json", tmp_path / "blind.json")
    evidence = runner.load(tmp_path / "evidence.json")
    blind = runner.load(tmp_path / "blind.json")
    assert set(calls) == {"GET"}
    assert evidence["run_id"] == "acceptance-run" and evidence["test_id"] == "014R"
    assert evidence["provider"] == "mock" and evidence["model_profile"] == "mock-default"
    assert evidence["started_at"] == run["started_at"]
    assert evidence["character_profiles"][0]["state"]["approved_profile_version"] == 1
    assert len(evidence["character_profiles"][0]["versions"]) == 2
    assert evidence["character_profiles"][0]["runs"][0]["prompt_lineage"] == lineage
    assert not evidence["lineage_errors"]
    assert evidence["execution_kind"] == "MOCK_OR_RECORDED"
    assert evidence["chapters"][0]["versions"][0]["content"] == version["content"]
    assert blind["samples"] == [
        {"blind_label": "Sample 1", "prose": "[人物]问[人物]：[人物]还能合作吗？"}
    ]
    assert evidence["blind_reading_mapping"]["Sample 1"]["chapter_version_id"] == "draft-v1"
    assert "林遥" not in json.dumps(blind, ensure_ascii=False)
    assert not evidence["completed_at"] and evidence["ai_behavior_acceptance"] != "PASS"


def test_future_chapter_change_invalidates_complete_baseline_and_legacy_is_readonly(
    tmp_path, monkeypatch
):
    paths = [runner.FIXTURES / "scenario.json"] + [
        runner.FIXTURES / f"chapter-{n:02d}.json" for n in range(1, 6)
    ]
    for path in paths:
        (tmp_path / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(runner, "FIXTURES", tmp_path)
    complete_hash = runner.fixture_hash()
    legacy_hash = hashlib.sha256((tmp_path / "scenario.json").read_bytes()).hexdigest()
    state = {
        **runner.metadata("E2E-001R", "run", "project"),
        "scenario_id": "E2E-001",
        "fixture_hash": complete_hash,
        "chapters": {},
    }
    changed = runner.load(tmp_path / "chapter-02.json")
    changed["raw_requirement"] += "\nchanged future chapter"
    runner.save(tmp_path / "chapter-02.json", changed)
    assert runner.fixture_hash() != complete_hash
    calls = []

    def transport(request):
        calls.append(request.method)
        return httpx.Response(
            200,
            json={
                "metadata": {
                    "e2e_run_id": "run",
                    "e2e_scenario": "E2E-001",
                    "e2e_fixture_hash": legacy_hash,
                }
            },
        )

    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        with pytest.raises(ValueError, match="changed fixture"):
            runner.owned_project(client, state)
        legacy = {**state, "fixture_hash": legacy_hash}
        with pytest.raises(ValueError, match="partial.*BLOCKED"):
            runner.owned_project(client, legacy)
        assert not calls
        runner.owned_project(client, legacy, read_only=True)
    assert calls == ["GET"]


def prerequisite_responses(state, chapters, entries):
    base = "/projects/project"
    responses = {
        base: {
            "metadata": {
                "e2e_run_id": state["run_id"],
                "e2e_scenario": state["scenario_id"],
                "e2e_fixture_hash": state["fixture_hash"],
            }
        },
        base + "/writing-profile/approved": {
            "id": "writing",
            "version": 1,
            "profile_hash": "writing-hash",
            "target_audience": "same",
        },
        base + "/chapters": chapters,
        base + "/memory": entries,
    }
    for chapter in chapters:
        source_entries = [entry for entry in entries if entry["chapter_id"] == chapter["id"]]
        responses[base + f"/chapters/{chapter['id']}/workflows"] = [
            {"id": "flow-" + chapter["id"], "status": "COMPLETED"}
        ]
        responses[f"/workflows/flow-{chapter['id']}/memory"] = [
            {
                "status": "COMMITTED",
                "request": {"draft_version": 1},
                "batch": {
                    "id": "batch-" + chapter["id"],
                    "status": "COMMITTED",
                    "confirmed_by": "human",
                    "chapter_version_id": "draft-" + chapter["id"],
                },
                "entries": source_entries,
            }
        ]
    return responses


@pytest.mark.parametrize("committed_count", [2, 3])
def test_repetition_binder_reads_real_commits_and_start_uses_next_actual_sequence(
    tmp_path, monkeypatch, committed_count
):
    state = {
        **runner.metadata("013R", "run"),
        "scenario_id": "013R",
        "fixture_hash": runner.fixture_hash("013R"),
        "case_id": "recent-mechanism-repetition",
        "chapters": {},
        "status": "BLOCKED",
        "selected_input": {"title": "repetition", "raw_requirement": "Author's requirement only"},
        "workflow_path": "/workflows/chapter-exploration",
    }
    chapters = [{"id": f"chapter-{n}", "sequence": n, "approved_version": 1} for n in range(1, 4)]
    entries = [
        {
            "id": f"summary-{n}",
            "version": 1,
            "project_id": "project",
            "chapter_id": f"chapter-{n}",
            "chapter_version_id": f"draft-chapter-{n}",
            "batch_id": f"batch-chapter-{n}",
            "memory_type": "DERIVED_CHAPTER_SUMMARY",
        }
        for n in range(1, committed_count + 1)
    ]
    responses = prerequisite_responses(state, chapters, entries)
    calls = []

    def transport(request):
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        if request.method == "POST" and request.url.path.endswith("/chapters"):
            return httpx.Response(201, json={"id": "selected-chapter"})
        if request.method == "POST" and request.url.path == "/workflows/chapter-exploration":
            return httpx.Response(
                201, json={"workflow": {"id": "selected-flow", "state_version": 1}}
            )
        return httpx.Response(200, json=responses.get(request.url.path, []))

    args = SimpleNamespace(
        state=tmp_path / "state.json",
        project_id="project",
        chapter=1,
        allow_real_provider=True,
        worker_stopped=True,
    )
    monkeypatch.setattr(runner, "ensure_idle_queue", lambda *args: [])
    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.check_prerequisites(client, args, state)
        assert all(method == "GET" for method, _, _ in calls)
        assert state["chapter_sequence_base"] == 3
        assert state["status"] == ("PENDING" if committed_count == 3 else "BLOCKED")
        if committed_count == 3:
            runner.start_chapter(client, args, state)
            posted = next(
                body
                for method, path, body in calls
                if method == "POST" and path.endswith("/chapters")
            )
            assert posted["sequence"] == 4
            assert set(state["chapters"]) == {"1"}
        else:
            with pytest.raises(ValueError, match="BLOCKED"):
                runner.start_chapter(client, args, state)


@pytest.mark.parametrize(
    "condition", ["valid", "unconfirmed", "wrong-owner", "suspects", "unapproved-draft"]
)
def test_knowledge_binder_requires_owner_epistemic_and_committed_approved_source(
    tmp_path, condition
):
    state = {
        **runner.metadata("014R", "run", "project"),
        "scenario_id": "014R",
        "fixture_hash": runner.fixture_hash("014R"),
        "case_id": "CDV-04-knowledge-boundary",
        "chapters": {},
        "status": "BLOCKED",
        "character_id_mapping": {"e3339fa1-b1bb-5b32-9d5d-5d56fa3902a1": "pov"},
        "required_profiles": {},
    }
    chapters = [{"id": "prior", "sequence": 2, "approved_version": 1}]
    common = {
        "project_id": "project",
        "chapter_id": "prior",
        "batch_id": "batch-prior",
        "chapter_version_id": "draft-prior",
        "version": 1,
    }
    entries = [
        {
            **common,
            "id": "visible",
            "memory_type": "CHARACTER_KNOWLEDGE",
            "subject_id": "pov",
            "epistemic_status": "KNOWS",
            "body": {"known_fact_id": "visible-fact"},
        },
        {
            **common,
            "id": "private",
            "memory_type": "CHARACTER_KNOWLEDGE",
            "subject_id": "other",
            "epistemic_status": "KNOWS",
            "body": {"known_fact_id": "private-fact"},
        },
        {
            **common,
            "id": "private-fact",
            "memory_type": "CANON_FACT",
            "subject_id": None,
            "epistemic_status": None,
            "body": {},
        },
    ]
    if condition == "wrong-owner":
        entries[0]["subject_id"] = "other"
    if condition == "suspects":
        entries[0]["epistemic_status"] = "SUSPECTS"
    responses = prerequisite_responses(state, chapters, entries)
    if condition == "unconfirmed":
        responses["/workflows/flow-prior/memory"][0]["batch"]["confirmed_by"] = ""
    if condition == "unapproved-draft":
        chapters[0]["approved_version"] = 2
    methods = []

    def transport(request):
        methods.append(request.method)
        return httpx.Response(200, json=responses.get(request.url.path, []))

    args = SimpleNamespace(state=tmp_path / "state.json", project_id=None)
    with httpx.Client(
        base_url="http://fixture", transport=httpx.MockTransport(transport)
    ) as client:
        runner.check_prerequisites(client, args, state)
    assert set(methods) == {"GET"}
    assert state["status"] == ("PENDING" if condition == "valid" else "BLOCKED")
    assert state["chapter_sequence_base"] == 2


@pytest.mark.parametrize("matching_profile", [True, False])
def test_case03_binder_verifies_historical_profile_body_without_loading_eval_answers(
    tmp_path, matching_profile
):
    historical = runner.load(runner.ROOT / "evals/creative-exploration/case-03.json")
    baseline, pins = historical["A"], historical["comparable_inputs"]
    state = {
        **runner.metadata("013R", "run"),
        "scenario_id": "013R",
        "fixture_hash": runner.fixture_hash("013R"),
        "case_id": "case-03-historical-small-setback",
        "chapters": {},
        "status": "BLOCKED",
    }
    responses = prerequisite_responses(state, [], [])
    original = {
        "id": "original",
        "version": pins["writing_profile_version"],
        "profile_hash": pins["writing_profile_hash"],
        "target_audience": "same",
    }
    responses[f"/projects/{baseline['project_id']}/writing-profile/versions"] = [original]
    responses[f"/projects/{baseline['project_id']}/chapters/{baseline['chapter_id']}/plans"] = [
        {"id": baseline["plan_id"]}
    ]
    responses[f"/context-packages/{baseline['context_package_id']}"] = {
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
    }
    if not matching_profile:
        responses["/projects/project/writing-profile/approved"]["narrative_perspective"] = (
            "THIRD_PERSON"
        )
    with httpx.Client(
        base_url="http://fixture",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=responses.get(request.url.path, []))
        ),
    ) as client:
        runner.check_prerequisites(
            client, SimpleNamespace(state=tmp_path / "state.json", project_id="project"), state
        )
    assert state["status"] == ("PENDING" if matching_profile else "BLOCKED")
    assert "historical_baseline" in state["prerequisite_evidence"]


@pytest.mark.parametrize("marker", ["e2e_run_id", "e2e_scenario", "e2e_fixture_hash"])
def test_prerequisite_binding_rejects_unowned_project_before_any_mutation(tmp_path, marker):
    state = {
        **runner.metadata("013R", "run"),
        "scenario_id": "013R",
        "fixture_hash": runner.fixture_hash("013R"),
        "case_id": "recent-mechanism-repetition",
        "chapters": {},
    }
    responses = prerequisite_responses(state, [], [])
    responses["/projects/project"]["metadata"][marker] = "another-run"
    with (
        httpx.Client(
            base_url="http://fixture",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=responses[request.url.path])
            ),
        ) as client,
        pytest.raises(ValueError, match="ownership"),
    ):
        runner.check_prerequisites(
            client, SimpleNamespace(state=tmp_path / "state.json", project_id="project"), state
        )
    assert state["project_id"] is None and not (tmp_path / "state.json").exists()
