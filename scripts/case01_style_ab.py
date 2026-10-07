"""Read-only A/B evidence export. Never starts a Worker or invokes a ModelProvider.

Run from backend: uv run python ../scripts/case01_style_ab.py --help
Manual, opt-in execution steps: evals/writing/v0.1/case-01/case01_style_ab.md
"""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID

import httpx

CASE = Path(__file__).resolve().parents[1] / "evals/writing/v0.1/case-01"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def verify_baseline():
    manifest = json.loads((CASE / "baseline/manifest.json").read_text())
    for name, expected in manifest["files"].items():
        if sha((CASE / "baseline" / name).read_bytes()) != expected:
            raise ValueError(f"Baseline changed: {name}")
    for key, name in (
        ("requirement_sha256", "requirement.txt"),
        ("draft_sha256", "draft.txt"),
    ):
        if manifest[key] != manifest["files"][name]:
            raise ValueError(f"Baseline manifest hash mismatch: {name}")
    return manifest


def export(client, workflow_id, output, *, planning_only=False):
    if output.exists():
        raise ValueError("Evidence directory already exists; choose a new path")
    baseline = verify_baseline()
    baseline_lineage = json.loads((CASE / "baseline/prompt-lineage.json").read_text())
    flow = f"/workflows/{workflow_id}"

    def get(path):
        response = client.get(path)
        response.raise_for_status()
        return response.json()

    def pages(path):
        rows = []
        for offset in range(0, 20000, 200):
            batch = get(f"{path}?limit=200&offset={offset}")
            rows.extend(batch)
            if len(batch) < 200:
                return rows
        raise ValueError("Unexpectedly large acceptance run; stop and inspect")

    workflow = get(flow)
    if str(workflow_id) == baseline["workflow_id"]:
        raise ValueError("B must be a new Workflow; baseline A cannot be reused as B")
    if (workflow["project_id"], workflow["chapter_id"]) != (
        baseline["project_id"],
        baseline["chapter_id"],
    ):
        raise ValueError(
            "Use the original Project/Chapter to avoid scope and previous-chapter confounds"
        )
    brief = get(flow + "/creative-brief")
    if sha(brief["raw_requirement"].encode()) != baseline["requirement_sha256"]:
        raise ValueError("Case 01 raw Requirement changed")
    plan = get(flow + "/planning/plan")
    writing = pages(flow + "/writing/history")
    tasks = pages(flow + "/agent-tasks")
    records = []
    profile_bindings = []
    for task in tasks:
        for run in pages(f"/agent-tasks/{task['task_id']}/runs"):
            lineage_response = client.get(f"/agent-runs/{run['run_id']}/prompt-lineage")
            if lineage_response.status_code == 404:
                records.append({"task": task, "run": run, "lineage": None, "context": None})
                continue
            lineage_response.raise_for_status()
            lineage = lineage_response.json()
            model = lineage["model_profile"]
            if (model["provider"], model["model"]) != (
                baseline["provider"],
                baseline["model"],
            ):
                raise ValueError(
                    "A/B Model changed; do not present this as a controlled comparison"
                )
            if model != baseline_lineage["model_profile"]:
                raise ValueError(
                    "A/B model parameters changed; resolve or document a separate experiment"
                )
            context = get(f"/agent-runs/{run['run_id']}/context")
            selected = [
                item
                for item in context["package"]["items"]
                if item["source_type"] == "PROJECT_WRITING_PROFILE"
            ]
            if task["task_type"] in {
                "PLAN_CHAPTER",
                "REVIEW_CHAPTER_PLAN",
                "WRITE_CHAPTER",
            }:
                if len(selected) != 1:
                    raise ValueError(
                        "B Planning/Review/Writing lacks exact approved profile evidence"
                    )
                item = selected[0]
                if item["status"] != "APPROVED" or item["authority_level"] != "A5_USER_PREFERENCE":
                    raise ValueError("B profile must be approved A5 user preference")
                payload = json.loads(item["payload_json"])
                binding = {
                    key: payload[key]
                    for key in (
                        "writing_profile_id",
                        "writing_profile_version",
                        "writing_profile_hash",
                    )
                }
                if binding["writing_profile_version"] != item["source_version"]:
                    raise ValueError("Profile binding version differs from context source")
                profile_bindings.append(
                    {
                        "task_id": task["task_id"],
                        "run_id": run["run_id"],
                        "task_type": task["task_type"],
                        **binding,
                    }
                )
            records.append({"task": task, "run": run, "lineage": lineage, "context": context})
    required_stages = {"PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}
    if not planning_only:
        required_stages.add("WRITE_CHAPTER")
    if not required_stages <= {p["task_type"] for p in profile_bindings}:
        raise ValueError("B evidence is missing required Planning/Review/Writing stages")
    if (
        not profile_bindings
        or len(
            {
                (
                    p["writing_profile_id"],
                    p["writing_profile_version"],
                    p["writing_profile_hash"],
                )
                for p in profile_bindings
            }
        )
        != 1
    ):
        raise ValueError("B must use one consistent Profile version across Planning/Review/Writing")
    chapter_path = f"/projects/{workflow['project_id']}/chapters/{workflow['chapter_id']}"
    draft_ids = {row["chapter_version_id"] for row in writing if row["chapter_version_id"]}
    if not draft_ids and not planning_only:
        raise ValueError("B has no generated Draft yet")
    drafts = [row for row in pages(chapter_path + "/versions") if row["id"] in draft_ids]
    if {row["id"] for row in drafts} != draft_ids:
        raise ValueError("WritingResult refers to a missing Draft")
    for row in writing:
        draft = next((d for d in drafts if d["id"] == row["chapter_version_id"]), None)
        if draft and sha(draft["content"].encode()) != row["content_hash"]:
            raise ValueError("Draft body does not match WritingResult content hash")
    bundle = {
        "workflow": workflow,
        "requirement": brief,
        "plan": plan,
        "writing_results": writing,
        "drafts": drafts,
        "runs": records,
        "writing_profile_bindings": profile_bindings,
        "human_gates": pages(flow + "/human-gates"),
        "baseline": baseline,
        "winner": None,
        "human_evaluation": "PENDING",
        "evidence_phase": "PLANNING" if planning_only else "WRITING",
        "confounds": [
            "B uses STYLE-001 Prompt and Context versions; not a profile-only ablation.",
            "Same raw requirement may produce different model interpretations/plans.",
            "Hard constraints and major direction require human comparison before approval.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "evidence.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
    for draft in drafts:
        (output / f"draft-v{draft['version']}.txt").write_text(draft["content"])
    return len(records), len(drafts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflow-id", type=UUID, help="Read/export B; omitted: verify saved A only"
    )
    parser.add_argument("--output", type=Path, help="New evidence directory (never overwrite)")
    parser.add_argument(
        "--planning-only",
        action="store_true",
        help="Export C06 evidence before human Plan Approval",
    )
    args = parser.parse_args()
    if args.workflow_id is None:
        verify_baseline()
        print("Case 01 baseline integrity PASS. No model call or database mutation.")
        return
    if args.output is None:
        parser.error("--output is required with --workflow-id")
    with httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1", trust_env=False, timeout=20
    ) as client:
        runs, drafts = export(
            client, args.workflow_id, args.output, planning_only=args.planning_only
        )
    print(f"Exported {runs} run records and {drafts} drafts. Human comparison remains pending.")


if __name__ == "__main__":
    main()
