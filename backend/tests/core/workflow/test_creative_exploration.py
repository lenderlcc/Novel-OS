"""Offline A03 integration evidence; fixtures do not measure creative quality."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from novel_os.agents.planning_mock import source_ref
from novel_os.agents.runtime import AgentRuntime
from novel_os.db.base import Base
from novel_os.domain.planning import CreativeExploration
from novel_os.models.memory import MemoryEntryModel, MemorySubjectModel
from novel_os.models.planning import CreativeExplorationModel
from novel_os.providers.base import ModelResponse
from novel_os.repositories.planning import PlanningRepository
from novel_os.services.agent_queue import AgentQueue
from novel_os.services.agent_results import AgentResultHandler
from novel_os.worker import AgentWorker
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_context_engine import chapter, plan, post
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider

RAW = "让人物自主解决一次小挫折，不改变已经确定的重要方向。"
REJECTED_SENTINEL = "REJECTED_CONCEPT_PRIVATE_SENTINEL"


class ExplorationDriver(PlanningDriver):
    def __init__(self, client, chapter_api, raw=RAW):
        self.client = client
        self.chapter_api = chapter_api
        parts = chapter_api.split("/")
        self.creation = {
            "project_id": parts[4],
            "chapter_id": parts[6],
            "event_id": str(uuid4()),
            "raw_requirement": raw,
        }
        response = client.post("/api/v1/workflows/chapter-exploration", json=self.creation)
        assert response.status_code == 201, response.text
        self.workflow = response.json()["workflow"]
        self.url = "/api/v1/workflows/" + self.workflow["id"]
        assert self.event("USER_SUBMITTED").status_code == 200


def candidate(identifier, mechanism, *, blocked=False):
    return {
        "id": identifier,
        "concept_summary": mechanism,
        "core_event": "A local obstacle shaped by " + mechanism,
        "conflict_engine": mechanism,
        "character_pressure": "A habitual reaction is challenged by " + mechanism,
        "story_progression": "Resolve this bounded setback without changing direction",
        "reader_interest": "A character choice has an immediate, limited consequence",
        "continuity_fit": "Preserve all supplied facts and knowledge owners",
        "requirement_fit": "One unexpected local setback with no major direction change",
        "creative_freedom_fit": "Use only granted local detail and local conflict",
        "audience_fit": "Use supplied preferences; do not invent a default audience",
        "execution_feasibility": "Can be expanded into a short, bounded ChapterPlan",
        "required_new_elements": ["An unauthorized world rule"] if blocked else [],
        "major_change_risk": "HIGH" if blocked else "LOW",
        "major_change_reason": "Requires a major rule" if blocked else "No major new facts",
        "similarity_risk": "HIGH" if identifier == "C1" else "LOW",
        "similarity_reason": "A repeated mechanism" if identifier == "C1" else "Different pressure",
        "authority_fit": "REQUIRES_MAJOR_CHANGE" if blocked else "WITHIN_BOUNDS",
        "authority_reason": "Needs user direction" if blocked else "Preserves locks and Canon",
        "strengths": ["A bounded character choice"],
        "risks": [],
    }


class ExplorationProvider(RecordedProvider):
    def __init__(self, *, level="HIGH", all_unsafe=False, review_failures=0, transform=None):
        self.level = level
        self.all_unsafe = all_unsafe
        self.review_failures = review_failures
        self.extra_transform = transform
        super().__init__(self.adjust)

    def adjust(self, request, body):
        if request.output_kind == "creative_brief":
            body["result"]["creative_freedom"].update(
                level=self.level,
                allowed_operations=["LOCAL_DETAIL", "LOCAL_CONFLICT"],
            )
        if request.output_kind == "chapter_plan":
            body["result"]["source_refs"].extend(
                source_ref(item)
                for item in request.context_package.items
                if item.selector_id == "selected-creative-concept"
            )
        if request.output_kind == "plan_review" and self.review_failures:
            self.review_failures -= 1
            body["result"]["verdict"] = "FAIL"
            body["result"]["hard_gate_issues"] = [
                {"code": "OUTCOME_UNACHIEVABLE", "description": "Repair the local outcome"}
            ]
        if self.extra_transform:
            self.extra_transform(request, body)

    def generate(self, request):
        if request.output_kind != "creative_exploration":
            return super().generate(request)
        self.requests.append(request)
        items = request.context_package.items
        brief = next(item for item in items if item.source_type == "CREATIVE_BRIEF")
        mechanisms = [
            "A personal judgment error",
            "Two compatible goals collide under changed circumstances",
            REJECTED_SENTINEL,
        ][: 3 if self.level == "HIGH" else 2]
        rows = [
            candidate(f"C{index}", mechanism, blocked=self.all_unsafe)
            for index, mechanism in enumerate(mechanisms, 1)
        ]
        selected = None if self.all_unsafe else "C2"
        body = {
            "task_id": str(request.task_id),
            "status": "BLOCKED" if self.all_unsafe else "SUCCESS",
            "result": {
                "kind": "creative_exploration",
                "brief_id": str(brief.source_id),
                "mode": "DIVERGENT",
                "focused_reason": None,
                "candidates": rows,
                "selected_candidate_id": selected,
                "selection_reason": "Best bounded fit for character pressure and continuity",
                "rejected_reasons": [
                    {
                        "candidate_id": row["id"],
                        "code": "REQUIRES_MAJOR_CHANGE" if self.all_unsafe else "NOT_SELECTED",
                        "reason": "Unsafe major change" if self.all_unsafe else "Weaker local fit",
                    }
                    for row in rows
                    if row["id"] != selected
                ],
                "source_refs": [source_ref(item) for item in items],
                "blocked_reason": "No safe concept within supplied direction"
                if self.all_unsafe
                else None,
            },
            "confidence": 0.9,
            "assumptions": [],
            "issues": [],
            "proposed_changes": [],
            "memory_proposals": [],
            "escalation": None,
        }
        if self.extra_transform:
            self.extra_transform(request, body)
        return ModelResponse(json.dumps(body))


@pytest.fixture
def exploration_driver(core_client, chapter_api):
    return ExplorationDriver(core_client, chapter_api)


def explore(database, driver, provider=None):
    provider = provider or ExplorationProvider()
    run_one(database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    stage = driver.workflow["state_version"]
    run_one(database, driver, provider=provider)
    return provider, stage


def test_a03_internal_exploration_selected_only_then_original_human_gate(
    exploration_driver, core_database
):
    d = exploration_driver
    provider, stage = explore(core_database, d)
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING", d.read("/agent-tasks")
    assert d.workflow["state_version"] == stage
    assert d.workflow["planning_iteration_count"] == 1
    artifact = d.read("/planning/exploration")
    assert artifact["status"] == "READY" and artifact["freshness"] == "READY"
    assert artifact["authority_level"] == "A7_AI_INFERENCE"
    assert artifact["body"]["selected_candidate_id"] == "C2"
    assert len(artifact["body"]["candidates"]) == 3
    assert d.read("/human-gates") == []
    assert d.read("/planning/history")["plans"] == []
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "PLAN_CHAPTER")
    assert task["task_type"] == "PLAN_CHAPTER"
    assert task["agent_id"] == "A03_PLANNING"
    run_one(core_database, d, provider=provider)
    package = provider.requests[-1].context_package
    serialized = json.dumps([item.structured_payload for item in package.items])
    assert REJECTED_SENTINEL not in serialized
    assert "Two compatible goals collide" in serialized
    assert not any("candidates" in item.structured_payload for item in package.items)
    plan_view = d.read("/planning/plan")
    generation = plan_view["generation"]
    assert generation["creative_exploration_id"] == artifact["id"]
    assert generation["selected_candidate_id"] == "C2"
    assert "creative_exploration_id" not in generation["body"]
    assert plan_view["plan"]["status"] == "PROPOSED"
    assert plan_view["plan"]["authority_level"] == "A7_AI_INFERENCE"
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert d.read("/planning/review")["verdict"] == "PASS"
    assert len(d.read("/human-gates")) == 1
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] is None
    assert d.decide().status_code == 200
    assert d.client.get(d.chapter_api).json()["approved_plan_version"] == 1
    assert d.read("/planning/exploration") == artifact
    assert d.read("/planning/explorations/" + artifact["id"]) == artifact
    assert d.read("/planning/history")["explorations"] == [artifact]
    run_one(core_database, d, provider=provider)
    writing_package = provider.requests[-1].context_package
    assert provider.requests[-1].output_kind == "writing_result"
    assert REJECTED_SENTINEL not in json.dumps(
        [item.structured_payload for item in writing_package.items]
    )
    assert not any(
        item.selector_id == "selected-creative-concept" for item in writing_package.items
    )
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(MemoryEntryModel)) == 0
        assert session.scalar(select(func.count()).select_from(MemorySubjectModel)) == 0
    assert artifact["context_package_id"] and artifact["prompt_lineage_id"]
    assert artifact["agent_run_id"] and artifact["source_versions"]


@pytest.mark.parametrize("level,expected_calls", [("LOW", 0), ("MEDIUM", 1), ("HIGH", 1)])
def test_simple_trigger_uses_one_call_not_one_per_candidate(
    exploration_driver, core_database, level, expected_calls
):
    d = exploration_driver
    provider = ExplorationProvider(level=level)
    run_one(core_database, d, provider=provider)
    tasks = d.read("/agent-tasks")
    assert tasks[-1]["task_type"] == (
        "EXPLORE_CHAPTER_CONCEPTS" if expected_calls else "PLAN_CHAPTER"
    )
    if expected_calls:
        run_one(core_database, d, provider=provider)
    run_one(core_database, d, provider=provider)
    assert sum(r.output_kind == "creative_exploration" for r in provider.requests) == expected_calls
    assert d.workflow["planning_iteration_count"] == 1


def test_plan_review_repair_reuses_exploration_and_keeps_two_plan_budget(
    exploration_driver, core_database
):
    d = exploration_driver
    provider, _ = explore(core_database, d, ExplorationProvider(review_failures=2))
    artifact = d.read("/planning/exploration")
    for _ in range(4):
        run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED", d.workflow
    assert d.workflow["block_reason"] == "PLANNING_ITERATION_LIMIT"
    history = d.read("/planning/history")
    assert len(history["explorations"]) == 1
    assert len(history["plans"]) == 2 and len(history["reviews"]) == 2
    assert all(p["creative_exploration_id"] == artifact["id"] for p in history["plans"])
    assert history["explorations"] == [artifact]
    assert sum(r.output_kind == "creative_exploration" for r in provider.requests) == 1


@pytest.mark.parametrize("decision", ["REJECT", "MODIFY", "REQUEST_ALTERNATIVE"])
def test_explicit_human_directive_reexplores_and_marks_old_selection_stale(
    exploration_driver, core_database, decision
):
    d = exploration_driver
    provider, _ = explore(core_database, d)
    for _ in range(2):
        run_one(core_database, d, provider=provider)
    old = d.read("/planning/exploration")
    assert d.decide(decision, reason="保留原方向，换一个局部冲突机制").status_code == 200
    stale = {**old, "freshness": "STALE"}
    assert d.read("/planning/exploration") == stale
    assert d.read("/planning/explorations/" + old["id"]) == stale
    assert d.read("/planning/history")["explorations"] == [stale]
    current = next(t for t in d.read("/agent-tasks") if t["status"] == "PENDING")
    assert current["task_type"] == "EXPLORE_CHAPTER_CONCEPTS"
    run_one(core_database, d, provider=provider)
    request = provider.requests[-1]
    assert request.output_kind == "creative_exploration"
    task_input = next(
        item for item in request.context_package.items if item.source_type == "TASK_INPUT"
    )
    directives = [json.loads(value) for value in task_input.structured_payload["requirements"]]
    assert any(value.get("decision") == decision for value in directives)
    artifact = d.read("/planning/exploration")
    assert artifact["id"] != old["id"] and artifact["brief_id"] == old["brief_id"]
    assert artifact["freshness"] == "READY"
    assert d.read("/planning/explorations/" + old["id"]) == stale
    assert d.read("/planning/history")["explorations"] == [stale, artifact]
    run_one(core_database, d, provider=provider)
    assert d.read("/planning/plan")["generation"]["creative_exploration_id"] == artifact["id"]
    run_one(core_database, d, provider=provider)
    assert d.decide().status_code == 200
    assert d.read("/planning/exploration") == artifact
    assert d.read("/planning/explorations/" + artifact["id"]) == artifact
    assert d.read("/planning/explorations/" + old["id"]) == stale
    assert d.read("/planning/history")["explorations"] == [stale, artifact]
    assert sum(r.output_kind == "creative_exploration" for r in provider.requests) == 2


def test_all_major_change_candidates_block_without_forcing_selection_or_loop(
    exploration_driver, core_database
):
    d = exploration_driver
    provider, _ = explore(core_database, d, ExplorationProvider(all_unsafe=True))
    assert d.workflow["current_state"] == "C90_BLOCKED"
    artifact = d.read("/planning/exploration")
    assert artifact["status"] == "BLOCKED"
    assert artifact["body"]["selected_candidate_id"] is None
    assert all(r["code"] == "REQUIRES_MAJOR_CHANGE" for r in artifact["body"]["rejected_reasons"])
    assert d.read("/planning/history")["plans"] == []
    before = len(provider.requests)
    response = d.event("RESUME")
    assert response.status_code == 409 or d.workflow["current_state"] == "C90_BLOCKED"
    assert AgentWorker(core_database, AgentRuntime(provider)).run_once() is False
    assert len(provider.requests) == before
    assert d.read("/human-gates") == []


@pytest.mark.parametrize("change", ["profile", "new_lock"])
@pytest.mark.parametrize("timing", ["queued", "during_model"])
def test_profile_and_lock_drift_rejects_old_selected_concept(
    exploration_driver, core_database, change, timing
):
    d = exploration_driver
    url = d.chapter_api.split("/chapters/")[0]
    draft(d.client, url, target_audience="Original audience")
    approve(d.client, url)
    explore(core_database, d)

    def mutate(*_):
        if change == "profile":
            draft(d.client, url, 1, target_audience="New audience")
            approve(d.client, url, 2)
        else:
            decision = post(
                d.client,
                url + "/decisions",
                {"question": "Direction", "decision": "Keep direction"},
            )
            post(
                d.client,
                url + "/locks",
                {
                    "target_type": "DECISION",
                    "target_id": decision["logical_id"],
                    "expected_version": 1,
                },
            )

    if timing == "queued":
        mutate()
    provider = ExplorationProvider(transform=mutate if timing == "during_model" else None)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C90_BLOCKED", d.workflow
    assert d.read("/planning/history")["plans"] == []
    assert d.read("/planning/exploration")["freshness"] == "STALE"
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "PLAN_CHAPTER")
    assert task["last_error_code"] == "CONTEXT_STALE"
    assert len(provider.requests) == int(timing == "during_model")


def test_first_profile_approval_invalidates_queued_exploration_before_model(
    exploration_driver, core_database
):
    d = exploration_driver
    run_one(core_database, d, provider=ExplorationProvider())
    project = d.chapter_api.split("/chapters/")[0]
    draft(d.client, project, target_audience="First approved audience")
    approve(d.client, project)
    provider = ExplorationProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["explorations"] == []
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "EXPLORE_CHAPTER_CONCEPTS")
    assert task["last_error_code"] == "CONTEXT_STALE"


def test_explicit_resume_after_profile_drift_reexplores_against_approved_version(
    exploration_driver, core_database
):
    d = exploration_driver
    project = d.chapter_api.split("/chapters/")[0]
    draft(d.client, project, target_audience="Old audience")
    approve(d.client, project)
    explore(core_database, d)
    old = d.read("/planning/exploration")
    draft(d.client, project, 1, target_audience="New approved audience")
    approve(d.client, project, 2)
    run_one(core_database, d, provider=ExplorationProvider())
    assert d.workflow["current_state"] == "C90_BLOCKED"
    response = d.event("RESUME")
    assert response.status_code == 200, response.text
    task = next(t for t in d.read("/agent-tasks") if t["status"] == "PENDING")
    assert task["task_type"] == "EXPLORE_CHAPTER_CONCEPTS"
    provider = ExplorationProvider()
    run_one(core_database, d, provider=provider)
    profile = next(
        item
        for item in provider.requests[-1].context_package.items
        if item.source_type == "PROJECT_WRITING_PROFILE"
    )
    assert profile.source_version == 2
    assert profile.structured_payload["target_audience"] == "New approved audience"
    artifact = d.read("/planning/exploration")
    assert artifact["id"] != old["id"] and artifact["brief_id"] == old["brief_id"]
    assert artifact["freshness"] == "READY"
    run_one(core_database, d, provider=provider)
    assert d.read("/planning/plan")["generation"]["creative_exploration_id"] == artifact["id"]


@pytest.mark.parametrize("source_changed", [False, True])
def test_paused_planning_resume_rebinds_manual_plan_without_ignoring_stale_sources(
    exploration_driver, core_database, source_changed
):
    d = exploration_driver
    provider, _ = explore(core_database, d)
    artifact = d.read("/planning/exploration")
    assert d.event("PAUSE").status_code == 200
    manual = plan(d.client, d.chapter_api, objective="A manually proposed current Plan")
    if source_changed:
        project = d.chapter_api.split("/chapters/")[0]
        decision = post(
            d.client,
            project + "/decisions",
            {"question": "Direction", "decision": "Preserve the approved direction"},
        )
        post(
            d.client,
            project + "/locks",
            {
                "target_type": "DECISION",
                "target_id": decision["logical_id"],
                "expected_version": 1,
            },
        )
    resumed = d.event("RESUME")
    assert resumed.status_code == 200, resumed.text
    if source_changed:
        assert d.workflow["current_state"] == "C90_BLOCKED"
        assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
        assert d.read("/planning/history")["plans"] == []
        return
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert d.workflow["status"] == "WAITING_AGENT"
    assert d.workflow["plan_version"] == manual["version"]
    pending = next(task for task in d.read("/agent-tasks") if task["status"] == "PENDING")
    assert pending["task_type"] == "PLAN_CHAPTER"
    run_one(core_database, d, provider=provider)
    generated = d.read("/planning/plan")
    assert generated["plan"]["version"] == manual["version"] + 1
    assert generated["generation"]["creative_exploration_id"] == artifact["id"]


def test_resume_after_new_lock_reinterprets_same_raw_before_fresh_exploration(
    exploration_driver, core_database
):
    d = exploration_driver
    explore(core_database, d)
    old = d.read("/planning/exploration")
    project = d.chapter_api.split("/chapters/")[0]
    decision = post(
        d.client,
        project + "/decisions",
        {"question": "Major direction", "decision": "Keep the established direction"},
    )
    post(
        d.client,
        project + "/locks",
        {
            "target_type": "DECISION",
            "target_id": decision["logical_id"],
            "expected_version": 1,
        },
    )
    run_one(core_database, d, provider=ExplorationProvider())
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["resume_state"] == "C01_REQUIREMENT_INTAKE"
    assert d.event("RESUME").status_code == 200
    assert d.workflow["current_state"] == "C01_REQUIREMENT_INTAKE"
    provider = ExplorationProvider()
    run_one(core_database, d, provider=provider)
    brief = d.read("/creative-brief")
    assert brief["raw_requirement"] == RAW
    assert brief["id"] != old["brief_id"]
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    run_one(core_database, d, provider=provider)
    artifact = d.read("/planning/exploration")
    assert artifact["id"] != old["id"] and artifact["brief_id"] == brief["id"]
    assert artifact["freshness"] == "READY"
    assert d.read("/planning/explorations/" + old["id"])["freshness"] == "STALE"
    run_one(core_database, d, provider=provider)
    assert d.read("/planning/plan")["generation"]["creative_exploration_id"] == artifact["id"]


def test_brief_correction_retains_old_artifact_but_never_reuses_it(
    exploration_driver, core_database
):
    d = exploration_driver
    explore(core_database, d)
    old = d.read("/planning/exploration")
    assert (
        d.post(
            "/requirement",
            d.command(expected_brief_version=1, raw_requirement="改变局部呈现，继续保持重要方向。"),
        ).status_code
        == 200
    )
    provider = ExplorationProvider()
    explore(core_database, d, provider)
    current = d.read("/planning/exploration")
    assert current["id"] != old["id"] and current["brief_id"] != old["brief_id"]
    original = d.read("/planning/explorations/" + old["id"])
    assert original["body"] == old["body"] and original["freshness"] == "STALE"
    assert len(d.read("/planning/history")["explorations"]) == 2


@pytest.mark.parametrize("event", ["PAUSE", "CANCEL"])
def test_inflight_exploration_pause_cancel_fences_the_result(
    exploration_driver, core_database, event
):
    d = exploration_driver
    run_one(core_database, d, provider=ExplorationProvider())

    def interrupt(request, body):
        assert request.output_kind == "creative_exploration"
        assert d.event(event).status_code == 200

    provider = ExplorationProvider(transform=interrupt)
    run_one(core_database, d, provider=provider)
    assert d.workflow["status"] == ("PAUSED" if event == "PAUSE" else "CANCELLED")
    assert d.read("/planning/history")["explorations"] == []
    assert d.read("/agent-tasks")[-1]["result_metadata"]["disposition"] == "STALE_IGNORED"


def test_duplicate_deliveries_persist_one_exploration_and_one_plan_task(
    exploration_driver, core_database
):
    d = exploration_driver
    runtime = AgentRuntime(ExplorationProvider())
    run_one(core_database, d, provider=ExplorationProvider())
    with core_database.session() as session:
        lease = AgentQueue(session).claim(
            "exploration-delivery", profile_for_task=runtime.profile_for_task
        )
    with core_database.session() as session:
        task = AgentQueue(session).start(lease)
    execution = AgentWorker(core_database, runtime).prepare_and_execute(task, lease)
    assert execution.error_code is None
    barrier = Barrier(2)

    def deliver(_):
        barrier.wait(timeout=5)
        with core_database.session() as session:
            return AgentResultHandler(session).complete(lease, execution)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(deliver, range(2))) == ["APPLIED", "DUPLICATE"]
    assert len(d.read("/planning/history")["explorations"]) == 1
    assert sum(t["task_type"] == "PLAN_CHAPTER" for t in d.read("/agent-tasks")) == 1
    assert d.refresh()["planning_iteration_count"] == 1


def test_artifact_and_planner_scheduling_rollback_together(
    exploration_driver, core_database, monkeypatch
):
    d = exploration_driver
    run_one(core_database, d, provider=ExplorationProvider())
    before = d.refresh()
    original = PlanningRepository.add

    def fail_after_insert(self, entity):
        result = original(self, entity)
        if isinstance(entity, CreativeExploration):
            raise RuntimeError("Injected artifact failure")
        return result

    monkeypatch.setattr(PlanningRepository, "add", fail_after_insert)
    with pytest.raises(RuntimeError, match="Injected artifact"):
        run_one(core_database, d, provider=ExplorationProvider())
    assert d.refresh() == before
    assert d.read("/planning/history")["explorations"] == []
    assert not any(t["task_type"] == "PLAN_CHAPTER" for t in d.read("/agent-tasks"))
    assert d.read("/agent-tasks")[-1]["status"] == "RUNNING"


def test_exploration_database_content_is_immutable(exploration_driver, core_database):
    d = exploration_driver
    explore(core_database, d)
    identifier = UUID(d.read("/planning/exploration")["id"])
    for statement in (
        "UPDATE creative_explorations SET body='{}' WHERE id=:id",
        "DELETE FROM creative_explorations WHERE id=:id",
    ):
        with core_database.session() as session, pytest.raises(IntegrityError), session.begin():
            session.execute(text(statement), {"id": identifier})
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(CreativeExplorationModel)) == 1


@pytest.mark.parametrize("scope", ["planning-only", "chapter-writing", "chapter-quality"])
def test_planning_execution_scopes_include_internal_a03_task(scope, settings):
    configured = settings.model_copy(update={"agent_execution_scope": scope})
    assert "EXPLORE_CHAPTER_CONCEPTS" in configured.agent_task_types


def test_recent_approved_plan_projection_excludes_newer_draft_and_future(
    core_client, chapter_api, core_database
):
    url = chapter_api.split("/chapters/")[0]
    plan(core_client, chapter_api, 1, objective="APPROVED_MECHANISM")
    post(core_client, chapter_api + "/plans/approve", {"expected_version": 1})
    plan(core_client, chapter_api, 2, objective="CURRENT_DRAFT_SECRET")
    target = chapter(core_client, url, 2)
    future = chapter(core_client, url, 3)
    plan(core_client, future, 1, objective="FUTURE_PLAN_SECRET")
    post(core_client, future + "/plans/approve", {"expected_version": 1})
    d = ExplorationDriver(core_client, target)
    provider, _ = explore(core_database, d)
    package = provider.requests[-1].context_package
    payload = json.dumps([i.structured_payload for i in package.items])
    assert "APPROVED_MECHANISM" in payload
    assert "CURRENT_DRAFT_SECRET" not in payload and "FUTURE_PLAN_SECRET" not in payload
    assert not any(i.source_type == "CHAPTER_VERSION" for i in package.items)
    assert package.future_knowledge_policy == "REQUIRED_ONLY"


def test_0018_roundtrip_preserves_existing_core_and_planning_data(
    core_client, chapter_api, core_database, migration_config
):
    plan(core_client, chapter_api, 1, objective="Historical manual Plan")

    def snapshot(connection):
        return {
            name: connection.execute(
                select(
                    *[
                        column
                        for column in table.c
                        if column.name
                        not in {
                            "creative_exploration_id",
                            "selected_candidate_id",
                            "report_character_id",
                        }
                        and not (
                            name == "memory_subjects"
                            and column.name in {"created_at", "created_by"}
                        )
                    ]
                ).order_by(*table.primary_key)
            )
            .mappings()
            .all()
            for name, table in Base.metadata.tables.items()
            if name not in {"creative_explorations", "character_behavior_profiles"}
        }

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0021_writing_output_contract"
        )
        command.downgrade(migration_config, "0018_creative_exploration")
        before = snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0017_memory_state_transitions"
        )
        assert connection.scalar(text("SELECT to_regclass('creative_explorations')")) is None
        assert snapshot(connection) == before
        command.upgrade(migration_config, "head")
        assert connection.scalar(text("SELECT to_regclass('creative_explorations')")) is not None
        assert snapshot(connection) == before
        command.check(migration_config)


def test_two_character_contexts_supply_distinct_committed_states_to_exploration(
    core_client, chapter_api, core_database
):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.quality.test_memory_commit import confirm, prepare
    from tests.core.quality.test_memory_context_isolation import LATER, candidates, commit_initial

    first = QualityDriver(core_client, chapter_api).approve_plan(core_database)
    entries = commit_initial(first, core_database)
    project = chapter_api.split("/chapters/")[0]
    second = QualityDriver(
        core_client, chapter(core_client, project, 2), "Mira meets Jun."
    ).approve_plan(core_database)
    knowledge = candidates(
        [
            (
                "a_knows",
                "CHARACTER_KNOWLEDGE",
                "Mira",
                "CHARACTER",
                "knowledge_x",
                "RED",
                2,
                "Mira learned Vault Cipher has code RED, without Jun present.",
                {"known_fact_id": entries["x"]["id"]},
            ),
            (
                "b_knows",
                "CHARACTER_KNOWLEDGE",
                "Jun",
                "CHARACTER",
                "knowledge_y",
                "BLUE",
                3,
                "Jun learned River Password has code BLUE, without Mira present.",
                {"known_fact_id": entries["y"]["id"]},
            ),
        ]
    )
    prepare(second, core_database, knowledge, LATER)
    response = confirm(second, ["a_knows", "b_knows"])
    assert response.status_code == 200, response.text
    for sequence, name, expected, excluded in (
        (3, "Mira", "a_state", "b_state"),
        (4, "Jun", "b_state", "a_state"),
    ):
        d = ExplorationDriver(
            core_client,
            chapter(core_client, project, sequence),
            name + " experiences a bounded setback and retains the established direction.",
        )
        provider, _ = explore(core_database, d)
        items = provider.requests[-1].context_package.items
        memory_ids = {str(i.source_id) for i in items if i.selector_id == "committed-memory"}
        assert entries[expected]["id"] in memory_ids
        assert entries[excluded]["id"] not in memory_ids
        knowledge_items = [
            item
            for item in items
            if item.selector_id == "committed-memory"
            and item.structured_payload["memory_type"] == "CHARACTER_KNOWLEDGE"
        ]
        assert len(knowledge_items) == 1
        owner = knowledge_items[0]
        assert owner.knowledge_scope == "CHARACTER_KNOWLEDGE"
        assert str(owner.character_id) == entries[expected]["subject_id"]
        assert owner.structured_payload["epistemic_status"] == "KNOWS"
        identities = [i for i in items if i.selector_id == "memory-subjects"]
        assert any(i.structured_payload["subject"]["name"] == name for i in identities)
        assert d.event("CANCEL").status_code == 200


def test_changed_selected_canon_blocks_pending_plan_from_old_exploration(
    core_client, chapter_api, core_database
):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.quality.test_memory_commit import confirm, prepare
    from tests.core.quality.test_memory_context_isolation import (
        LATER,
        candidates,
        commit_initial,
    )

    first = QualityDriver(core_client, chapter_api).approve_plan(core_database)
    commit_initial(first, core_database)
    project = chapter_api.split("/chapters/")[0]
    second = QualityDriver(
        core_client, chapter(core_client, project, 2), "Mira meets Jun."
    ).approve_plan(core_database)
    update = candidates(
        [
            (
                "a_state",
                "CHARACTER_STATE",
                "Mira",
                "CHARACTER",
                "location",
                "Hill",
                1,
                "Mira moved from Harbor to Hill.",
                {"state_before": "Harbor"},
            )
        ]
    )
    prepare(second, core_database, update, LATER)
    d = ExplorationDriver(
        core_client,
        chapter(core_client, project, 3),
        "Mira faces a local setback while continuing the established direction.",
    )
    explore(core_database, d)
    before = d.read("/planning/exploration")
    response = confirm(second, ["a_state"])
    assert response.status_code == 200, response.text
    provider = ExplorationProvider()
    run_one(core_database, d, provider=provider)
    assert provider.requests == []
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/planning/history")["plans"] == []
    artifact = d.read("/planning/exploration")
    assert artifact["id"] == before["id"] and artifact["freshness"] == "STALE"
