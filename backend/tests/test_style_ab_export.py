"""Offline evidence export contract: MockTransport permits GET only; no provider calls."""

import copy
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/case01_style_ab.py"
spec = importlib.util.spec_from_file_location("style_ab", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


@pytest.fixture
def evidence():
    baseline = exporter.verify_baseline()
    lineage = json.loads((exporter.CASE / "baseline/prompt-lineage.json").read_text())
    binding = {
        "writing_profile_id": baseline["project_id"],
        "writing_profile_version": 1,
        "writing_profile_hash": "profile-content-hash",
    }
    item = {
        "source_type": "PROJECT_WRITING_PROFILE",
        "source_version": 1,
        "status": "APPROVED",
        "authority_level": "A5_USER_PREFERENCE",
        "payload_json": json.dumps(binding),
    }
    tasks = [
        {"task_id": f"task-{i}", "task_type": kind}
        for i, kind in enumerate(["PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN", "WRITE_CHAPTER"])
    ]
    root = "/api/v1/workflows/b"
    paths = {
        root: {"project_id": baseline["project_id"], "chapter_id": baseline["chapter_id"]},
        root + "/creative-brief": {
            "raw_requirement": (exporter.CASE / "baseline/requirement.txt").read_text()
        },
        root + "/planning/plan": {"version": 3},
        root + "/agent-tasks": tasks,
        root + "/human-gates": [{"status": "APPROVED"}],
        root + "/writing/history": [
            {"chapter_version_id": "draft-b", "content_hash": exporter.sha(b"B")}
        ],
        f"/api/v1/projects/{baseline['project_id']}/chapters/{baseline['chapter_id']}/versions": [
            {"id": "draft-a", "version": 1, "content": "A"},
            {"id": "draft-b", "version": 2, "content": "B"},
        ],
    }
    for i in range(3):
        paths[f"/api/v1/agent-tasks/task-{i}/runs"] = [{"run_id": f"run-{i}"}]
        paths[f"/api/v1/agent-runs/run-{i}/prompt-lineage"] = copy.deepcopy(lineage)
        paths[f"/api/v1/agent-runs/run-{i}/context"] = {"package": {"items": [copy.deepcopy(item)]}}
    return paths


def client_for(paths):
    def handler(request):
        assert request.method == "GET"
        assert request.url.host == "127.0.0.1"
        assert request.url.path in paths, request.url
        return httpx.Response(200, json=paths[request.url.path])

    return httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1", transport=httpx.MockTransport(handler)
    )


def test_export_exact_three_stage_binding_and_draft_without_mutation(evidence, tmp_path):
    output = tmp_path / "B"
    with client_for(evidence) as client:
        assert exporter.export(client, "b", output) == (3, 1)
        with pytest.raises(ValueError, match="already exists"):
            exporter.export(client, "b", output)
    bundle = json.loads((output / "evidence.json").read_text())
    assert {row["task_type"] for row in bundle["writing_profile_bindings"]} == {
        "PLAN_CHAPTER",
        "REVIEW_CHAPTER_PLAN",
        "WRITE_CHAPTER",
    }
    assert bundle["winner"] is None and bundle["human_evaluation"] == "PENDING"
    assert (output / "draft-v2.txt").read_text() == "B"
    assert not (output / "draft-v1.txt").exists()


@pytest.mark.parametrize(
    "change, message",
    [
        ("missing_review", "lacks exact approved"),
        ("changed_profile", "one consistent Profile"),
        ("draft_profile", "approved A5"),
        ("wrong_authority", "approved A5"),
        ("changed_raw", "raw Requirement changed"),
        ("changed_model", "Model changed"),
        ("changed_draft", "content hash"),
        ("empty_writing", "no generated Draft"),
    ],
)
def test_export_refuses_misleading_ab_evidence(evidence, tmp_path, change, message):
    item = evidence["/api/v1/agent-runs/run-1/context"]["package"]["items"][0]
    if change == "missing_review":
        evidence["/api/v1/agent-runs/run-1/context"]["package"]["items"] = []
    elif change == "changed_profile":
        payload = json.loads(item["payload_json"])
        payload["writing_profile_hash"] = "different"
        item["payload_json"] = json.dumps(payload)
    elif change == "draft_profile":
        item["status"] = "DRAFT"
    elif change == "wrong_authority":
        item["authority_level"] = "A2_USER_APPROVED"
    elif change == "changed_raw":
        evidence["/api/v1/workflows/b/creative-brief"]["raw_requirement"] += "changed"
    elif change == "changed_model":
        evidence["/api/v1/agent-runs/run-0/prompt-lineage"]["model_profile"]["model"] = "other"
    elif change == "changed_draft":
        evidence["/api/v1/workflows/b/writing/history"][0]["content_hash"] = "wrong"
    elif change == "empty_writing":
        evidence["/api/v1/workflows/b/writing/history"] = []
    with client_for(evidence) as client, pytest.raises(ValueError, match=message):
        exporter.export(client, "b", tmp_path / "B")
    assert not (tmp_path / "B").exists()


def test_planning_export_is_explicit_and_cannot_claim_complete_writing(evidence, tmp_path):
    evidence["/api/v1/workflows/b/agent-tasks"].pop()
    evidence["/api/v1/workflows/b/writing/history"] = []
    with client_for(evidence) as client:
        with pytest.raises(ValueError, match="missing required"):
            exporter.export(client, "b", tmp_path / "incomplete")
        assert exporter.export(client, "b", tmp_path / "planning", planning_only=True) == (2, 0)
    bundle = json.loads((tmp_path / "planning/evidence.json").read_text())
    assert bundle["evidence_phase"] == "PLANNING" and bundle["human_evaluation"] == "PENDING"
    assert bundle["drafts"] == []
