"""Explicit Phase 2 acceptance using existing APIs/Worker, stopping at human gates."""

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx

FIXTURES = Path(__file__).resolve().parent
ROOT = FIXTURES.parents[2]
BACKEND = ROOT / "backend"
ACTIVE_TASKS = {"PENDING", "CLAIMED", "RUNNING"}
MANIFEST = FIXTURES / "acceptance-manifest.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def show(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def fixture_hash(test_id="E2E-001R"):
    paths = {
        "E2E-001R": [FIXTURES / "scenario.json"]
        + [FIXTURES / f"chapter-{sequence:02d}.json" for sequence in range(1, 6)],
        "013R": [
            ROOT / "evals/creative-exploration" / name
            for name in ("case-03.json", "repetition-context.json")
        ],
        "014R": [
            ROOT / "evals/character-depth" / name for name in ("cases.json", "characters.json")
        ],
    }
    if test_id not in paths:
        raise ValueError("Unknown acceptance test ID")
    return hashlib.sha256(b"".join(path.read_bytes() for path in paths[test_id])).hexdigest()


def legacy_baseline(state):
    return (
        state.get("test_id", "E2E-001R") == "E2E-001R"
        and state["fixture_hash"]
        == hashlib.sha256((FIXTURES / "scenario.json").read_bytes()).hexdigest()
    )


def metadata(test_id, run_id, project_id=None):
    return {
        "test_id": test_id,
        "run_id": run_id,
        "project_id": project_id,
        "provider": None,
        "model_profile": None,
        "started_at": None,
        "completed_at": None,
        "human_gates": [],
        "status": "PENDING",
        "result": "PENDING",
    }


def request(client, method, path, body=None, *, optional=False):
    response = client.request(method, path, json=body)
    if optional and response.status_code == 404:
        return None
    if response.is_error:
        # Print the public error code only, never a raw transport/configuration dump.
        try:
            error = response.json().get("error", {})
            code = error.get("code", "HTTP_ERROR") if isinstance(error, dict) else "HTTP_ERROR"
        except ValueError:
            code = "HTTP_ERROR"
        raise ValueError(f"{method} {path}: HTTP {response.status_code} {code}")
    return response.json()


def get(client, path, *, optional=False):
    return request(client, "GET", path, optional=optional)


def pages(client, path):
    rows = []
    separator = "&" if "?" in path else "?"
    for offset in range(0, 20000, 200):
        batch = get(client, f"{path}{separator}limit=200&offset={offset}")
        rows.extend(batch)
        if len(batch) < 200:
            return rows
    raise ValueError("Evidence exceeds 20,000 rows; inspect before continuing")


def planning_history(client, path):
    history = {"briefs": [], "plans": [], "reviews": []}
    for offset in range(0, 20000, 200):
        batch = get(client, f"{path}?limit=200&offset={offset}")
        for key, rows in batch.items():
            history.setdefault(key, []).extend(rows)
        if all(len(rows) < 200 for rows in batch.values()):
            return history
    raise ValueError("Planning history exceeds export limit")


def owned_project(client, state, *, read_only=False):
    test_id = state.get("test_id", "E2E-001R")
    scenario_id = "E2E-001" if test_id == "E2E-001R" else test_id
    legacy = legacy_baseline(state)
    if legacy and not read_only:
        raise ValueError(
            "Legacy input baseline is partial; paid continuation is BLOCKED. "
            "Inspect/export and manually verify inputs before preparing a fresh run"
        )
    if state["scenario_id"] != scenario_id or (
        not legacy and state["fixture_hash"] != fixture_hash(test_id)
    ):
        raise ValueError("State belongs to another scenario or a changed fixture")
    if not state.get("project_id"):
        raise ValueError("Preparation is BLOCKED; inspect the recorded prerequisites")
    project = get(client, f"/projects/{state['project_id']}")
    if any(
        project["metadata"].get(key) != value
        for key, value in {
            "e2e_run_id": state["run_id"],
            "e2e_scenario": scenario_id,
            "e2e_fixture_hash": state["fixture_hash"],
        }.items()
    ):
        raise ValueError("Project ownership marker does not match this dedicated E2E run")
    return project


def workflow(client, state, sequence):
    chapter = state["chapters"].get(str(sequence))
    if chapter is None:
        raise ValueError("Chapter has not been started in this E2E run")
    flow = get(client, f"/workflows/{chapter['workflow_id']}")
    if (flow["project_id"], flow["chapter_id"]) != (state["project_id"], chapter["chapter_id"]):
        raise ValueError("Workflow scope differs from the dedicated E2E Project/Chapter")
    return flow


def command_body(flow, reason):
    return {
        "event_id": str(uuid4()),
        "expected_state_version": flow["state_version"],
        "reason": reason,
    }


def require_manual_execution(args):
    if not args.allow_real_provider or not args.worker_stopped:
        raise ValueError("Explicit --allow-real-provider --worker-stopped are required")


def ensure_idle_queue(client, allowed_workflow_id=None):
    """The existing Worker is global; fail closed before its one permitted claim."""
    permitted = []
    for project in pages(client, "/projects"):
        project_path = f"/projects/{project['id']}"
        for chapter in pages(client, project_path + "/chapters"):
            for flow in pages(client, project_path + f"/chapters/{chapter['id']}/workflows"):
                for task in pages(client, f"/workflows/{flow['id']}/agent-tasks"):
                    if task["status"] not in ACTIVE_TASKS:
                        continue
                    if task["status"] != "PENDING" or flow["id"] != allowed_workflow_id:
                        raise ValueError(
                            "Another pending/leased task exists. Pause/cancel it through the "
                            "Workspace before an isolated manual model step"
                        )
                    if (
                        task["workflow_state"] != flow["current_state"]
                        or task["workflow_state_version"] != flow["state_version"]
                    ):
                        raise ValueError("A stale pending task exists; inspect Workflow Debug")
                    permitted.append(task)
    return permitted


def initialize(client, args):
    if args.state.exists():
        raise ValueError("State file already exists; use it or choose a new file")
    scenario = load(FIXTURES / "scenario.json")
    run_id = str(uuid4())
    data = dict(scenario["project"])
    data["metadata"] = {
        **data.get("metadata", {}),
        "e2e_scenario": "E2E-001",
        "e2e_run_id": run_id,
        "e2e_fixture_hash": fixture_hash(),
    }
    project = request(client, "POST", "/projects", data)
    state = {
        **metadata("E2E-001R", run_id, project["id"]),
        "scenario_id": "E2E-001",
        "fixture_hash": fixture_hash(),
        "run_id": run_id,
        "project_id": project["id"],
        "chapters": {},
    }
    # Retain the owned Project ID if profile creation fails; never delete story data.
    save(args.state, state)
    profile = request(
        client,
        "POST",
        f"/projects/{project['id']}/writing-profile/drafts",
        {"expected_version": 0, "preferences": scenario["writing_profile"]},
    )
    show({"project_id": project["id"], "profile": profile})
    print("Profile remains DRAFT. Inspect it before approve-profile. No model call.")


def prepare_case(client, args):
    """Only selected authored inputs cross the API; evaluator expectations never do."""
    if args.test_id == "E2E-001R":
        return initialize(client, args)
    if args.state.exists():
        raise ValueError("State file already exists; use it or choose a new file")
    manifest = load(MANIFEST)["tests"][args.test_id]
    if args.case not in manifest["cases"]:
        raise ValueError("Select a declared --case from acceptance-manifest.json")
    state = {
        **metadata(args.test_id, str(uuid4())),
        "scenario_id": args.test_id,
        "fixture_hash": fixture_hash(args.test_id),
        "case_id": args.case,
        "chapters": {},
        "workflow_path": "/workflows/chapter-exploration",
    }
    if args.test_id == "013R":
        name = (
            "case-03.json"
            if args.case == "case-03-historical-small-setback"
            else "repetition-context.json"
        )
        state["selected_input"] = {
            "title": args.case,
            "raw_requirement": load(ROOT / "evals/creative-exploration" / name)["raw_requirement"],
        }
        state.update(status="BLOCKED", result="BLOCKED", blocked_reasons=manifest["prerequisites"])
        save(args.state, state)
        show(state)
        print(
            "BLOCKED: use the existing APIs to establish comparable approved history. "
            "No project/model was created; synthetic history will not be seeded."
        )
        return
    cases = load(ROOT / "evals/character-depth/cases.json")["cases"]
    selected = next(case for case in cases if case["id"] == args.case)["input"]
    if "variants" in selected:
        selected = next(
            (variant for variant in selected["variants"] if variant["label"] == args.variant), None
        )
        if selected is None:
            raise ValueError("Select this case's explicit --variant label")
    elif args.variant is not None:
        raise ValueError("This case has no variants")
    # Do not serialize the case, its evaluator_only fields or synthetic knowledge as input.
    state["selected_input"] = {"title": args.case, "raw_requirement": selected["raw_requirement"]}
    state["variant"] = args.variant
    project = request(
        client,
        "POST",
        "/projects",
        {
            "name": f"014R {args.case}",
            "description": "Isolated human character acceptance",
            "metadata": {
                "e2e_scenario": "014R",
                "e2e_run_id": state["run_id"],
                "e2e_fixture_hash": state["fixture_hash"],
            },
        },
    )
    state.update(project_id=project["id"], character_id_mapping={}, required_profiles={})
    save(args.state, state)
    base = f"/projects/{project['id']}"
    request(
        client,
        "POST",
        base + "/writing-profile/drafts",
        {
            "expected_version": 0,
            "preferences": {
                "target_audience": "人物表现人工验收",
                "narrative_perspective": "THIRD_PERSON",
            },
        },
    )
    characters = load(ROOT / "evals/character-depth/characters.json")["characters"]
    for character in characters:
        identity = request(
            client,
            "POST",
            base + "/characters",
            {
                "name": character["name"],
                "aliases": character["static_identity"]["aliases"],
            },
        )
        state["character_id_mapping"][character["id"]] = identity["id"]
        save(args.state, state)
    for character in characters:
        if character["id"] not in selected["approved_profile_ids"]:
            continue
        body = copy.deepcopy(character["behavior_profile"]["body"])
        for modifier in body.get("relationship_modifiers", []):
            modifier["other_character_id"] = state["character_id_mapping"][
                modifier["other_character_id"]
            ]
        character_id = state["character_id_mapping"][character["id"]]
        draft = request(
            client,
            "POST",
            base + f"/characters/{character_id}/behavior-profile/drafts",
            {
                "expected_version": 0,
                "profile": body,
            },
        )
        state["required_profiles"][character_id] = {
            "version": draft["version"],
            "profile_hash": draft["profile_hash"],
        }
        save(args.state, state)
    if args.case == "CDV-04-knowledge-boundary":
        state.update(
            status="BLOCKED",
            result="BLOCKED",
            blocked_reasons=[
                "Full knowledge-boundary acceptance requires legitimate approved/committed "
                "knowledge "
                "sources. Use chapter completion and human Memory confirmation APIs; do not seed "
                "evaluator Secret X or synthetic knowledge into Canon."
            ],
        )
        save(args.state, state)
    show(state)
    print(
        "Writing/Character profiles remain DRAFT. Approve exact versions explicitly in "
        "Workspace/API before start; no model call."
    )


def confirmed_sources(client, project_id, chapters):
    """Verify current entries against actual completed workflows and human commit batches."""
    current = {entry["id"] for entry in pages(client, f"/projects/{project_id}/memory")}
    sources = []
    for chapter in chapters:
        path = f"/projects/{project_id}/chapters/{chapter['id']}"
        for flow in pages(client, path + "/workflows"):
            if flow["status"] != "COMPLETED":
                continue
            for history in pages(client, f"/workflows/{flow['id']}/memory"):
                batch = history["batch"]
                if (
                    history["status"] != "COMMITTED"
                    or not batch
                    or not batch["confirmed_by"]
                    or batch["status"] != "COMMITTED"
                ):
                    continue
                if history["request"]["draft_version"] != chapter["approved_version"]:
                    continue
                for entry in history["entries"]:
                    if entry["id"] in current and (
                        entry["project_id"],
                        entry["chapter_id"],
                        entry["batch_id"],
                        entry["chapter_version_id"],
                    ) == (project_id, chapter["id"], batch["id"], batch["chapter_version_id"]):
                        sources.append({**entry, "source_sequence": chapter["sequence"]})
    return sources


def check_prerequisites(client, args, state):
    """GET-only recovery: owned real prerequisites, no approval/model/Canon fabrication."""
    if state.get("test_id") not in {"013R", "014R"} or state["chapters"]:
        raise ValueError("Check prerequisites before starting a selected 013/014 case")
    project_id = (
        str(args.project_id) if getattr(args, "project_id", None) else state.get("project_id")
    )
    if state.get("project_id") and state["project_id"] != project_id:
        raise ValueError("Cannot replace this run's prepared Project")
    owned_project(client, {**state, "project_id": project_id})
    base = f"/projects/{project_id}"
    profile = get(client, base + "/writing-profile/approved")
    chapters = pages(client, base + "/chapters")
    reasons, evidence = [], {}
    if profile is None:
        reasons.append("Explicit human approval of Writing Profile is required")
    else:
        evidence["writing_profile"] = {
            key: profile[key] for key in ("id", "version", "profile_hash")
        }
    for character_id, expected in state.get("required_profiles", {}).items():
        approved = get(client, base + f"/characters/{character_id}/behavior-profile/approved")
        if approved is None or any(approved[key] != value for key, value in expected.items()):
            reasons.append(
                "Explicit human approval of the selected exact Character Profile is required"
            )
    if state["test_id"] == "013R" and state["case_id"] == "case-03-historical-small-setback":
        from novel_os.api.writing_profile_schemas import WritingPreferencesInput

        historical = load(ROOT / "evals/creative-exploration/case-03.json")
        baseline, pins = historical["A"], historical["comparable_inputs"]
        package = get(client, f"/context-packages/{baseline['context_package_id']}")["package"]
        versions = pages(client, f"/projects/{baseline['project_id']}/writing-profile/versions")
        original = next(
            (
                row
                for row in versions
                if row["version"] == pins["writing_profile_version"]
                and row["profile_hash"] == pins["writing_profile_hash"]
            ),
            None,
        )
        plans = pages(
            client, f"/projects/{baseline['project_id']}/chapters/{baseline['chapter_id']}/plans"
        )
        items = package["items"]
        exact = any(
            item["source_type"] == "PROJECT_WRITING_PROFILE"
            and json.loads(item["payload_json"]).get("writing_profile_hash")
            == pins["writing_profile_hash"]
            and item["source_version"] == pins["writing_profile_version"]
            for item in items
        )
        fields = set(WritingPreferencesInput.model_fields)
        if (
            not original
            or not exact
            or package["project_id"] != baseline["project_id"]
            or not any(plan["id"] == baseline["plan_id"] for plan in plans)
        ):
            reasons.append("Historical A Plan/Context/exact Writing Profile could not be verified")
        elif profile is None or {key: original.get(key) for key in fields} != {
            key: profile.get(key) for key in fields
        }:
            reasons.append(
                "Writing preferences differ from historical A; do not upgrade POV silently"
            )
        allowed_sources = {
            "TASK_INPUT",
            "PROJECT",
            "CHAPTER",
            "CREATIVE_BRIEF",
            "PLAN_REVIEW_REPORT",
            "PROJECT_WRITING_PROFILE",
        }
        if (
            any(item["source_type"] not in allowed_sources for item in items)
            or any(
                row["status"] in {"APPROVED", "LOCKED"}
                for kind in ("requirements", "decisions")
                for row in pages(client, base + f"/{kind}")
            )
            or pages(client, base + "/memory")
            or any(row["active"] for row in pages(client, base + "/locks"))
        ):
            reasons.append(
                "Historical Authority comparability needs human verification; "
                "cannot copy or ignore Canon/Locks"
            )
        evidence["historical_baseline"] = {
            **baseline,
            "writing_profile_hash": pins["writing_profile_hash"],
            "comparison": "Profile body compared; Project/record IDs differ",
        }
    if state["test_id"] == "013R" and state["case_id"] == "recent-mechanism-repetition":
        recent = sorted(chapters, key=lambda chapter: chapter["sequence"], reverse=True)[:3]
        sources = confirmed_sources(client, project_id, recent)
        summaries = [
            entry for entry in sources if entry["memory_type"] == "DERIVED_CHAPTER_SUMMARY"
        ]
        if len({entry["chapter_id"] for entry in summaries}) != 3:
            reasons.append(
                "Three recent approved final chapters with committed summaries are required"
            )
        evidence["recent_history"] = summaries
    if state["case_id"] == "CDV-04-knowledge-boundary":
        sources = confirmed_sources(client, project_id, chapters)
        cases = load(ROOT / "evals/character-depth/cases.json")["cases"]
        selected = next(case for case in cases if case["id"] == state["case_id"])["input"]
        owner = state["character_id_mapping"][selected["pov_character_id"]]
        knows = [
            entry
            for entry in sources
            if entry["memory_type"] == "CHARACTER_KNOWLEDGE"
            and entry["epistemic_status"] == "KNOWS"
        ]
        owned = [entry for entry in knows if entry["subject_id"] == owner]
        known_ids = {entry["body"].get("known_fact_id") for entry in owned}
        other = [
            entry
            for entry in knows
            if entry["subject_id"] != owner
            and entry["body"].get("known_fact_id") not in known_ids
            and any(
                fact["memory_type"] == "CANON_FACT"
                and fact["id"] == entry["body"].get("known_fact_id")
                for fact in sources
            )
        ]
        if not owned or not other:
            reasons.append(
                "Committed POV KNOWS and another owner's distinct known Canon fact are required"
            )
        evidence["knowledge_sources"] = owned + other
    state.update(
        project_id=project_id,
        chapter_sequence_base=max((chapter["sequence"] for chapter in chapters), default=0),
        prerequisite_evidence=evidence,
        status="BLOCKED" if reasons else "PENDING",
        result="BLOCKED" if reasons else "PENDING",
        blocked_reasons=reasons,
    )
    save(args.state, state)
    show(
        {
            "status": state["status"],
            "blocked_reasons": reasons,
            "prerequisite_evidence": evidence,
            "next_sequence": state["chapter_sequence_base"] + 1,
        }
    )


def require_writing_profile(client, state):
    profile = get(client, f"/projects/{state['project_id']}/writing-profile/approved")
    if profile is None:
        raise ValueError("Approve the Project Writing Profile before starting Chapter 01")
    expected = state.get("prerequisite_evidence", {}).get("writing_profile")
    if expected is not None and any(
        profile[key] != expected[key] for key in ("id", "version", "profile_hash")
    ):
        raise ValueError(
            "Approved Writing Profile changed; revalidate prerequisites in an unstarted run"
        )


def start_chapter(client, args, state):
    require_manual_execution(args)
    if state.get("blocked_reasons"):
        raise ValueError("Case prerequisites are BLOCKED; inspect status and manifest")
    ensure_idle_queue(client)
    if str(args.chapter) in state["chapters"]:
        raise ValueError("This chapter already exists; inspect/reuse its Workflow")
    if len(state["chapters"]) != args.chapter - 1:
        raise ValueError("Start chapters in order, one at a time")
    if args.chapter > 1 and workflow(client, state, args.chapter - 1)["status"] != "COMPLETED":
        raise ValueError("Previous Chapter must complete human Memory Confirmation first")
    require_writing_profile(client, state)
    if state.get("test_id", "E2E-001R") != "E2E-001R" and args.chapter != 1:
        raise ValueError("A selected comparison variant uses one isolated Chapter")
    for character_id, expected in state.get("required_profiles", {}).items():
        approved = get(
            client,
            f"/projects/{state['project_id']}/characters/{character_id}/behavior-profile/approved",
        )
        if approved is None or any(approved[key] != value for key, value in expected.items()):
            raise ValueError("Human approval of the exact selected Character Profile is required")
    fixture = state.get("selected_input") or load(FIXTURES / f"chapter-{args.chapter:02d}.json")
    chapter = request(
        client,
        "POST",
        f"/projects/{state['project_id']}/chapters",
        {
            "sequence": args.chapter + state.get("chapter_sequence_base", 0),
            "title": fixture["title"],
        },
    )
    created = request(
        client,
        "POST",
        state.get("workflow_path", "/workflows/chapter-quality"),
        {
            "project_id": state["project_id"],
            "chapter_id": chapter["id"],
            "event_id": str(uuid4()),
            "raw_requirement": fixture["raw_requirement"],
        },
    )["workflow"]
    state["chapters"][str(args.chapter)] = {
        "chapter_id": chapter["id"],
        "workflow_id": created["id"],
        "raw_requirement_sha256": hashlib.sha256(fixture["raw_requirement"].encode()).hexdigest(),
    }
    state["completed_at"] = None
    save(args.state, state)
    request(
        client,
        "POST",
        f"/workflows/{created['id']}/events",
        {**command_body(created, "Start one manual E2E chapter"), "event_type": "USER_SUBMITTED"},
    )
    print("Requirement task queued. Run exactly one model step explicitly; no Worker was started.")


def one_task(client, args, state, flow):
    require_manual_execution(args)
    if flow["current_state"] != args.stage or flow["status"] != "WAITING_AGENT":
        raise ValueError("Requested stage is not the current waiting-agent stage")
    if state.get("prerequisite_evidence", {}).get("writing_profile") is not None:
        require_writing_profile(client, state)
    pending = ensure_idle_queue(client, flow["id"])
    if not pending:
        raise ValueError("No pending task; do not launch an unscoped Worker")
    # Import the existing file-backed Settings. Never print credentials or alter configuration.
    from novel_os.core.config import Settings

    settings = Settings.from_file(args.config.resolve())
    policy = get(client, "/agent-execution/config")
    if (
        settings.agent_execution_scope != "chapter-quality"
        or settings.agent_max_attempts != 1
        or settings.agent_model_profile != policy["model_profile"]
        or settings.agent_model_profile == "mock-default"
    ):
        raise ValueError(
            "Use the API's real model profile, chapter-quality scope and max_attempts=1"
        )
    verify_worker_database(settings, state, flow, pending)
    state.update(
        provider=policy["provider"],
        model_profile=policy["model_profile"],
        started_at=state.get("started_at") or datetime.now(UTC).isoformat(),
        status="RUNNING",
        result="PENDING_HUMAN_REVIEW",
    )
    if hasattr(args, "state"):
        save(args.state, state)
    before = {task["task_id"]: task["attempt_count"] for task in pending}
    # Bind the standard Worker's claim to the audited IDs, even if the queue changes afterward.
    completed = subprocess.run(
        [sys.executable, "-m", "novel_os.worker", "--once", "--config", str(args.config.resolve())]
        + [argument for task in pending for argument in ("--task-id", task["task_id"])],
        cwd=BACKEND,
        check=False,
    )
    after = pages(client, f"/workflows/{flow['id']}/agent-tasks")
    consumed = [
        task
        for task in after
        if task["task_id"] in before and task["attempt_count"] > before[task["task_id"]]
    ]
    if len(consumed) != 1:
        raise ValueError("One-attempt evidence is incomplete; stop and inspect Debug")
    show({"worker_exit_code": completed.returncode, "attempt": consumed[0]})
    print("Stopped after one attempt. Inspect status/export before any further model step.")
    return consumed[0]


def verify_worker_database(settings, state, flow, pending):
    """Read-only identity check: an API audit cannot authorize a different Worker database."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    from novel_os.db.session import Database
    from novel_os.domain.errors import DomainError
    from novel_os.models.agents import AgentTaskModel
    from novel_os.services.agent_queries import AgentQueries
    from novel_os.services.projects import ProjectService
    from novel_os.workflow.runtime import WorkflowRuntime

    database = Database(settings)
    try:
        with database.session() as session:
            config = Config(str(BACKEND / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND / "alembic"))
            head = ScriptDirectory.from_config(config).get_current_head()
            if MigrationContext.configure(session.connection()).get_current_heads() != (head,):
                raise ValueError(
                    "Worker migration differs from repository head; no model attempt allowed"
                )
            project = ProjectService(session).get(UUID(state["project_id"]))
            actual = WorkflowRuntime(session).get(UUID(flow["id"]))
            if (
                project.metadata.get("e2e_run_id") != state["run_id"]
                or str(actual.project_id) != flow["project_id"]
                or str(actual.chapter_id) != flow["chapter_id"]
                or actual.current_state != flow["current_state"]
                or actual.state_version != flow["state_version"]
                or actual.status != "WAITING_AGENT"
            ):
                raise ValueError("Worker configuration does not match the API's owned E2E scope")
            queries = AgentQueries(session)
            active_ids = set(
                session.scalars(
                    select(AgentTaskModel.task_id).where(
                        AgentTaskModel.workflow_instance_id.is_not(None),
                        AgentTaskModel.status.in_(ACTIVE_TASKS),
                    )
                )
            )
            if active_ids != {UUID(task["task_id"]) for task in pending}:
                raise ValueError(
                    "Worker database has another pending/leased task outside the audited API scope"
                )
            for expected in pending:
                task = queries.get(UUID(expected["task_id"]))
                for key in (
                    "project_id",
                    "workflow_instance_id",
                    "target_ref",
                    "task_type",
                    "status",
                    "workflow_state",
                    "workflow_state_version",
                    "attempt_count",
                    "version",
                    "objective",
                    "requirements",
                    "constraints",
                    "expected_output_schema",
                ):
                    value = getattr(task, key)
                    if (str(value) if isinstance(value, UUID) else value) != expected[key]:
                        raise ValueError("Worker database task differs from the audited API task")
    except DomainError:
        raise ValueError(
            "Worker database is missing the API's owned E2E Project/Workflow/task"
        ) from None
    except SQLAlchemyError:
        raise ValueError(
            "Worker database preflight unavailable; no model attempt allowed"
        ) from None
    finally:
        database.dispose()


def mutate_workflow(client, args, flow):
    base = f"/workflows/{flow['id']}"
    body = command_body(flow, "Explicit manual E2E human action")
    if args.action == "approve-plan":
        require_manual_execution(args)
        gates = [
            gate
            for gate in pages(client, base + "/human-gates")
            if gate["status"] == "WAITING" and gate["gate_type"] == "PLAN_APPROVAL"
        ]
        if len(gates) != 1 or flow["current_state"] != "C06_PLAN_APPROVAL":
            raise ValueError("There is no exact pending Plan Approval gate")
        gate = gates[0]
        if gate["artifact_version"] != args.expected_version:
            raise ValueError("Expected Plan version is stale")
        path = f"/human-gates/{gate['id']}/decision"
        body.update(expected_artifact_version=args.expected_version, decision="APPROVE")
    elif args.action == "finalize":
        require_manual_execution(args)
        versions = pages(
            client, f"/projects/{flow['project_id']}/chapters/{flow['chapter_id']}/versions"
        )
        current = next((row for row in versions if row["version"] == flow["draft_version"]), None)
        if current is None or current["id"] != str(args.version_id):
            raise ValueError("Accept the exact current Draft ID shown in the trace")
        path = base + "/completion"
        body["chapter_version_id"] = str(args.version_id)
    elif args.action == "confirm-memory":
        history = pages(client, base + "/memory")
        active = next(
            (
                row
                for row in history
                if row["proposal"] and row["proposal"]["id"] == str(args.proposal_id)
            ),
            None,
        )
        if active is None or active["status"] != "PROPOSED":
            raise ValueError("Proposal is not current PROPOSED memory")
        selected = args.candidate or []
        if not selected and not args.confirm_empty:
            raise ValueError("List selected --candidate IDs, or explicitly --confirm-empty")
        known = {row["id"] for row in active["proposal"]["candidates"]}
        if not set(selected) <= known:
            raise ValueError("Unknown selected candidate ID")
        path = base + "/memory/confirm"
        body.update(proposal_id=str(args.proposal_id), selected_candidate_ids=selected)
    elif args.action == "feedback":
        require_manual_execution(args)
        path = base + "/feedback"
        body.update(
            source_chapter_version_id=str(args.version_id),
            raw_feedback=args.text.read_text(encoding="utf-8"),
        )
    else:
        require_manual_execution(args)
        path = base + "/revision"
        body.update(
            source_review_id=str(args.review_id), expected_draft_version=args.expected_version
        )
    if args.action != "confirm-memory":
        ensure_idle_queue(client)
    show(request(client, "POST", path, body))
    print("Human command recorded. No model Worker started; no further gate was approved.")


def run_to_gate(client, args, state, *, continuing=False):
    """Bound existing one-task execution; never approve, accept, retry or advance a chapter."""
    require_manual_execution(args)
    if not 1 <= args.max_tasks <= 12:
        raise ValueError("Use a bounded --max-tasks between 1 and 12")
    flow = workflow(client, state, args.chapter)
    stop = state.get("stop")
    if (
        stop
        and stop["workflow_id"] == flow["id"]
        and stop["kind"] in {"HUMAN_GATE", "DRAFT_REVIEW"}
    ):
        if not continuing:
            raise ValueError("Use continue-after-human after an actual human transition")
        history = pages(client, f"/workflows/{flow['id']}/history")
        audits = {row["id"]: row for row in pages(client, f"/projects/{state['project_id']}/audit")}
        allowed = {
            "USER_APPROVED",
            "USER_REJECTED",
            "USER_MODIFIED",
            "REQUEST_REVISION",
            "REQUEST_FEEDBACK",
            "REQUEST_COMPLETION",
            "CONFIRM_MEMORY",
            "DISCARD_MEMORY",
            "DISCARD_FEEDBACK",
        }
        human = next(
            (
                row
                for row in history
                if row["from_version"] >= stop["state_version"]
                and row["to_version"] <= flow["state_version"]
                and (audit := audits.get(row["audit_record_id"]))
                and audit["actor_type"] == "USER"
                and audit["after"].get("workflow_id") == flow["id"]
                and audit["after"].get("event_type") in allowed
            ),
            None,
        )
        if human is None:
            raise ValueError("No recorded human gate transition; no model will run")
        state.setdefault("human_gates", []).append(
            {"stop": stop, "transition": human, "audit_record_id": human["audit_record_id"]}
        )
        state.pop("stop")
        save(args.state, state)
    elif continuing:
        raise ValueError("No recorded human stop to continue")

    executed = 0
    while True:
        flow = workflow(client, state, args.chapter)
        status, stage = flow["status"], flow["current_state"]
        if status in {"BLOCKED", "FAILED", "CANCELLED", "PAUSED"}:
            kind = status
        elif status == "COMPLETED":
            kind = "COMPLETED"
        elif (
            stage in {"C10_REVISION", "C11_INTERNAL_PASS", "C12_USER_REVIEW"}
            and status != "WAITING_AGENT"
        ):
            kind = "DRAFT_REVIEW"
        elif status == "WAITING_HUMAN":
            kind = "HUMAN_GATE"
        elif status != "WAITING_AGENT":
            kind = "NO_WAITING_TASK"
        elif executed >= args.max_tasks:
            kind = "TASK_BUDGET"
        else:
            args.stage = stage
            attempt = one_task(client, args, state, flow)
            executed += 1
            if attempt["status"] == "SUCCEEDED":
                continue
            # No technical retry, escalation or ordinary quality retry is hidden here.
            kind = "OUTPUT_BLOCKED" if attempt["status"] == "BLOCKED" else "ATTEMPT_FAILED"
            flow = workflow(client, state, args.chapter)
        state["stop"] = {
            "workflow_id": flow["id"],
            "state_version": flow["state_version"],
            "state": flow["current_state"],
            "kind": kind,
        }
        state["status"] = kind
        state["result"] = (
            "PENDING_HUMAN_REVIEW"
            if kind in {"HUMAN_GATE", "DRAFT_REVIEW", "COMPLETED", "TASK_BUDGET"}
            else "BLOCKED"
        )
        if kind == "COMPLETED" and (
            state.get("test_id", "E2E-001R") != "E2E-001R" or args.chapter == 5
        ):
            state["completed_at"] = datetime.now(UTC).isoformat()
        save(args.state, state)
        show({"stop": state["stop"], "executed_tasks": executed, "result": state["result"]})
        return


def run_evidence(client, tasks, errors):
    records = []
    for task in tasks:
        for run in pages(client, f"/agent-tasks/{task['task_id']}/runs"):
            lineage = get(client, f"/agent-runs/{run['run_id']}/prompt-lineage", optional=True)
            context = get(client, f"/agent-runs/{run['run_id']}/context", optional=True)
            if run["status"] == "SUCCEEDED" and (lineage is None or context is None):
                errors.append({"run_id": run["run_id"], "error": "MISSING_SUCCESS_LINEAGE"})
            if lineage is not None and (
                lineage["agent_run_id"] != run["run_id"]
                or lineage["task_id"] != task["task_id"]
                or f"{lineage['output_schema_id']}.v{lineage['output_schema_version']}"
                != task["expected_output_schema"]
            ):
                errors.append(
                    {"run_id": run["run_id"], "error": "RUN_TASK_SCHEMA_BINDING_MISMATCH"}
                )
            records.append(
                {"task": task, "run": run, "prompt_lineage": lineage, "context": context}
            )
    return records


def export(client, state, output, blind_output=None):
    if output.exists():
        raise ValueError("Evidence file already exists; choose a fresh output path")
    if blind_output is not None and (blind_output == output or blind_output.exists()):
        raise ValueError("Choose a separate fresh blind-reading output path")
    if not state.get("project_id"):
        save(
            output,
            {
                **state,
                "exported_at": datetime.now(UTC).isoformat(),
                "ai_behavior_acceptance": "NOT_RUN",
                "human_prose_evaluation": "NOT_EVALUATED",
            },
        )
        print("Blocked preparation evidence exported; no API/model/state mutation.")
        return
    project_path = f"/projects/{state['project_id']}"
    bundle = {
        **metadata(state.get("test_id", "E2E-001R"), state["run_id"], state["project_id"]),
        **{
            key: state[key]
            for key in (
                "provider",
                "model_profile",
                "started_at",
                "completed_at",
                "human_gates",
                "status",
                "result",
                "case_id",
                "variant",
                "character_id_mapping",
                "blocked_reasons",
                "prerequisite_evidence",
                "chapter_sequence_base",
            )
            if key in state
        },
        "scenario_id": state["scenario_id"],
        "exported_at": datetime.now(UTC).isoformat(),
        "fixture_hash": state["fixture_hash"],
        "input_baseline": "INPUT_BASELINE_PARTIAL" if legacy_baseline(state) else "COMPLETE",
        "project": get(client, project_path),
        "execution_policy": get(client, "/agent-execution/config"),
        "writing_profile": get(client, project_path + "/writing-profile"),
        "writing_profile_versions": pages(client, project_path + "/writing-profile/versions"),
        "current_memory": pages(client, project_path + "/memory"),
        "historical_memory": pages(client, project_path + "/memory?historical=true"),
        "audit": pages(client, project_path + "/audit"),
        "chapters": [],
        "character_profiles": [],
        "lineage_errors": [],
        "ai_behavior_acceptance": "PENDING_HUMAN_REVIEW",
        "human_prose_evaluation": "PENDING",
    }
    if legacy_baseline(state):
        bundle["legacy_started_input_checks"] = {
            sequence: {
                "recorded_raw_requirement_sha256": chapter.get("raw_requirement_sha256"),
                "matches_current_fixture": chapter.get("raw_requirement_sha256")
                == hashlib.sha256(
                    load(FIXTURES / f"chapter-{int(sequence):02d}.json")["raw_requirement"].encode()
                ).hexdigest(),
            }
            for sequence, chapter in state["chapters"].items()
        }
    for character in pages(client, project_path + "/characters"):
        base = project_path + f"/characters/{character['id']}/behavior-profile"
        tasks = pages(client, base + "/interpretations")
        bundle["character_profiles"].append(
            {
                "character": character,
                "state": get(client, base),
                "approved": get(client, base + "/approved"),
                "versions": pages(client, base + "/versions"),
                "interpretation_tasks": tasks,
                "runs": run_evidence(client, tasks, bundle["lineage_errors"]),
            }
        )
    for sequence in sorted(state["chapters"], key=int):
        flow = workflow(client, state, int(sequence))
        base = f"/workflows/{flow['id']}"
        chapter_path = project_path + f"/chapters/{flow['chapter_id']}"
        memory = pages(client, base + "/memory")
        evidence = {
            "sequence": int(sequence),
            "workflow": flow,
            "chapter": get(client, chapter_path),
            "input": get(client, base + "/creative-brief", optional=True),
            "planning": planning_history(client, base + "/planning/history"),
            "plan_versions": pages(client, chapter_path + "/plans"),
            "versions": pages(client, chapter_path + "/versions"),
            "writing_results": pages(client, base + "/writing/history"),
            "reviews": pages(client, chapter_path + "/quality-reviews"),
            "revisions": pages(client, base + "/revisions"),
            "human_feedback": pages(client, base + "/feedback"),
            "memory": memory,
            "human_gates": pages(client, base + "/human-gates"),
            "transitions": pages(client, base + "/history"),
            "runs": [],
            "memory_density": [],
        }
        for row in memory:
            proposal, batch = row["proposal"], row["batch"]
            candidates = proposal["candidates"] if proposal else []
            evidence["memory_density"].append(
                {
                    "request_id": row["request"]["id"],
                    "source_chapter_version_id": row["request"]["chapter_version_id"],
                    "candidate_count": len(candidates),
                    "committed_count": len(row["entries"]),
                    "excluded_count": len(candidates) - len(batch["selected_candidate_ids"])
                    if batch
                    else None,
                    "duplicate_count": sum(
                        candidate["conflict_status"] == "DUPLICATE" for candidate in candidates
                    ),
                    "conflict_count": sum(
                        candidate["conflict_status"]
                        in {"CONTRADICTION", "AUTHORITY_CONFLICT", "AMBIGUOUS"}
                        for candidate in candidates
                    ),
                }
            )
        evidence["tasks"] = pages(client, base + "/agent-tasks")
        evidence["runs"] = run_evidence(client, evidence["tasks"], bundle["lineage_errors"])
        bundle["chapters"].append(evidence)
    providers = sorted(
        {
            record["run"]["provider"]
            for source in bundle["chapters"] + bundle["character_profiles"]
            for record in source["runs"]
        }
    )
    records = [
        record
        for source in bundle["chapters"] + bundle["character_profiles"]
        for record in source["runs"]
    ]
    profiles = sorted(
        {
            record["prompt_lineage"]["model_profile_id"]
            for record in records
            if record["prompt_lineage"] is not None
        }
    )
    bundle["model_profiles_observed"] = profiles
    bundle["providers_observed"] = providers
    bundle["execution_kind"] = (
        "NO_MODEL_ATTEMPT"
        if not providers
        else "MOCK_OR_RECORDED"
        if providers == ["mock"]
        else "REAL_PROVIDER_ATTEMPTS"
    )
    if providers:
        bundle["provider"] = providers[0] if len(providers) == 1 else providers
    if profiles:
        bundle["model_profile"] = profiles[0] if len(profiles) == 1 else profiles
    else:
        bundle["model_profile"] = (
            bundle["model_profile"] or bundle["execution_policy"]["model_profile"]
        )
    starts = [record["run"]["started_at"] for record in records if record["run"].get("started_at")]
    bundle["started_at"] = min(starts) if starts else bundle["started_at"]
    bundle["human_actions"] = bundle["human_gates"]
    bundle["human_gates"] = [
        gate for chapter in bundle["chapters"] for gate in chapter["human_gates"]
    ]
    expected_chapters = 5 if state.get("test_id", "E2E-001R") == "E2E-001R" else 1
    if len(bundle["chapters"]) == expected_chapters and all(
        chapter["workflow"]["status"] == "COMPLETED" for chapter in bundle["chapters"]
    ):
        bundle["completed_at"] = max(
            chapter["workflow"]["updated_at"] for chapter in bundle["chapters"]
        )
    if blind_output is not None:
        names = {
            name
            for row in bundle["character_profiles"]
            for name in [row["character"]["name"], *row["character"].get("aliases", [])]
        }
        samples, mapping = [], {}
        for chapter in bundle["chapters"]:
            for version in chapter["versions"]:
                text = version["content"]
                for name in sorted(names, key=len, reverse=True):
                    pattern = rf"\b{re.escape(name)}\b" if name.isascii() else re.escape(name)
                    text = re.sub(pattern, "[人物]", text)
                label = f"Sample {len(samples) + 1}"
                samples.append({"blind_label": label, "prose": text})
                mapping[label] = {
                    "chapter_version_id": version["id"],
                    "original_names": sorted(names),
                }
        bundle["blind_reading_mapping"] = mapping
        save(
            blind_output,
            {
                "purpose": "Human reading aid only; no automatic score or PASS rule",
                "samples": samples,
            },
        )
    save(output, bundle)
    print(f"Read-only trace exported: {output}. No model call; human acceptance remains pending.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument(
        "--state", type=Path, required=True, help="Dedicated ignored local E2E state file"
    )
    parser.add_argument(
        "--allow-real-provider",
        action="store_true",
        help="Explicit opt-in to enqueue/execute one manual stage",
    )
    parser.add_argument(
        "--worker-stopped",
        action="store_true",
        help="Operator confirms all polling Workers are stopped",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    prepare = sub.add_parser(
        "prepare", help="Prepare selected legitimate inputs; never approve or call a model"
    )
    prepare.add_argument("--test-id", choices=("E2E-001R", "013R", "014R"), required=True)
    prepare.add_argument("--case")
    prepare.add_argument("--variant", help="Exact variant label from the selected fixture")
    prerequisites = sub.add_parser(
        "check-prerequisites", help="GET-only verification of legitimate owned source history"
    )
    prerequisites.add_argument(
        "--project-id",
        type=UUID,
        help="Explicit prepared Project carrying this run's ownership markers",
    )
    profile = sub.add_parser("approve-profile")
    profile.add_argument("--expected-version", required=True, type=int)
    character = sub.add_parser("approve-character-profile")
    character.add_argument("--character-id", required=True, type=UUID)
    character.add_argument("--expected-version", required=True, type=int)
    start = sub.add_parser("start")
    start.add_argument("--chapter", required=True, type=int, choices=range(1, 6))
    sub.add_parser("status")
    trace = sub.add_parser("export")
    trace.add_argument("--output", type=Path, required=True)
    trace.add_argument(
        "--blind-reading-output",
        type=Path,
        help="Optional names-hidden human reading aid; mapping stays in full evidence",
    )
    step = sub.add_parser("one-task")
    step.add_argument("--chapter", required=True, type=int, choices=range(1, 6))
    step.add_argument("--stage", required=True, help="Exact current Workflow state from status")
    step.add_argument("--config", type=Path, default=BACKEND / "config.toml")
    for action in ("run-to-next-gate", "continue-after-human"):
        command = sub.add_parser(action)
        command.add_argument("--chapter", required=True, type=int, choices=range(1, 6))
        command.add_argument("--max-tasks", type=int, default=6)
        command.add_argument("--config", type=Path, default=BACKEND / "config.toml")
    for action in ("approve-plan", "finalize", "confirm-memory", "feedback", "revise"):
        command = sub.add_parser(action)
        command.add_argument("--chapter", required=True, type=int, choices=range(1, 6))
        if action in {"approve-plan", "revise"}:
            command.add_argument("--expected-version", required=True, type=int)
        if action in {"finalize", "feedback"}:
            command.add_argument("--version-id", required=True, type=UUID)
        if action == "revise":
            command.add_argument("--review-id", required=True, type=UUID)
        if action == "feedback":
            command.add_argument("--text", required=True, type=Path)
        if action == "confirm-memory":
            command.add_argument("--proposal-id", required=True, type=UUID)
            command.add_argument("--candidate", action="append")
            command.add_argument("--confirm-empty", action="store_true")
    args = parser.parse_args()
    try:
        with httpx.Client(base_url=args.api, trust_env=False, timeout=30) as client:
            if args.action == "init":
                initialize(client, args)
                return
            if args.action == "prepare":
                prepare_case(client, args)
                return
            state = load(args.state)
            if args.action == "check-prerequisites":
                check_prerequisites(client, args, state)
                return
            if not state.get("project_id") and state.get("status") == "BLOCKED":
                if state["fixture_hash"] != fixture_hash(state["test_id"]):
                    raise ValueError("Blocked preparation fixture changed; prepare a fresh run")
                if args.action == "status":
                    show(state)
                elif args.action == "export":
                    export(client, state, args.output, args.blind_reading_output)
                else:
                    raise ValueError("Preparation is BLOCKED; inspect the manifest prerequisites")
                return
            owned_project(client, state, read_only=args.action in {"export", "status"})
            if args.action == "approve-profile":
                show(
                    request(
                        client,
                        "POST",
                        f"/projects/{state['project_id']}/writing-profile/approve",
                        {"expected_version": args.expected_version},
                    )
                )
            elif args.action == "approve-character-profile":
                if str(args.character_id) not in state.get("required_profiles", {}):
                    raise ValueError("Approve only a Character Profile prepared in this run")
                show(
                    request(
                        client,
                        "POST",
                        f"/projects/{state['project_id']}/characters/{args.character_id}/behavior-profile/approve",
                        {
                            "expected_version": args.expected_version,
                        },
                    )
                )
            elif args.action == "start":
                start_chapter(client, args, state)
            elif args.action == "export":
                export(client, state, args.output, args.blind_reading_output)
            elif args.action == "status":
                show(
                    {
                        "run_metadata": {
                            key: state.get(key)
                            for key in metadata(state.get("test_id", "E2E-001R"), state["run_id"])
                        },
                        "stop": state.get("stop"),
                        "blocked_reasons": state.get("blocked_reasons", []),
                        "input_baseline": "INPUT_BASELINE_PARTIAL"
                        if legacy_baseline(state)
                        else "COMPLETE",
                        "execution_policy": get(client, "/agent-execution/config"),
                        "workflows": [
                            workflow(client, state, int(sequence)) for sequence in state["chapters"]
                        ],
                    }
                )
            else:
                flow = workflow(client, state, args.chapter)
                if args.action == "one-task":
                    one_task(client, args, state, flow)
                elif args.action in {"run-to-next-gate", "continue-after-human"}:
                    run_to_gate(
                        client, args, state, continuing=args.action == "continue-after-human"
                    )
                else:
                    mutate_workflow(client, args, flow)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        parser.exit(1, f"Stopped: {exc}\n")


if __name__ == "__main__":
    main()
