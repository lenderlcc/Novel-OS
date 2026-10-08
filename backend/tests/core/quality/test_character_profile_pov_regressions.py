"""Offline POV identity regressions using the isolated test database."""

from dataclasses import replace
from uuid import UUID

import pytest

from novel_os.context.policies import ContextFilter
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import ExclusionReason, KnowledgeScope, SourceType
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.character_profile_context import PROFILE_SELECTOR
from novel_os.services.context import ContextService
from tests.context.test_character_profile_context import character, profile_version
from tests.context.test_context import item, selector
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_human_feedback import submit
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider

POV_TASKS = {
    "REVIEW_CHAPTER_PLAN",
    "WRITE_CHAPTER",
    "REVIEW_CHAPTER_COMPLIANCE",
    "REVIEW_CHAPTER_NARRATIVE",
    "INTERPRET_CHAPTER_FEEDBACK",
    "PLAN_CHAPTER_REVISION",
    "REVISE_CHAPTER",
    "VALIDATE_REVISION_FIDELITY",
}


@pytest.fixture
def anonymous_plan(core_client, core_database, project_api, chapter_api):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    pov = character(core_database, project_id, "Mira")
    profile_version(core_database, project_id, pov.id, communication_style="Short direct answers")
    unrelated = character(core_database, project_id, "Atlas")
    profile_version(core_database, project_id, unrelated.id, communication_style="UNRELATED")
    draft(core_client, project_api, narrative_perspective="FIRST_PERSON")
    approve(core_client, project_api)

    def anonymous_output(request, body):
        if request.output_kind == "creative_brief":
            body["result"]["must"] = []
        elif request.task_type == "PLAN_CHAPTER":
            body["result"]["pov_character_id"] = str(pov.id)
            body["result"]["objective"] = "我在雨夜找到信件，决定沿河寻找线索。"
            body["result"]["required_outcome"] = "我收好信件，决定继续寻找。"
            body["result"]["ending_state"] = "我收好信件，决定继续寻找。"
        elif request.task_type == "WRITE_CHAPTER":
            body["result"]["content"] = (
                "我推开窗，雨水从屋檐落下。\n\n我收好信件，走向河边。\n\n我决定等到天亮。"
            )

    provider = RecordedProvider(anonymous_output)
    d = QualityDriver(
        core_client, chapter_api, raw_requirement="Mira 在雨夜找到信件，以她的第一人称叙述。"
    )
    run_one(core_database, d, provider=provider)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C05_PLAN_REVIEW", d.workflow
    return d, pov, unrelated, provider


@pytest.mark.integration
def test_anonymous_pov_survives_review_feedback_and_revision(anonymous_plan, core_database):
    d, pov, unrelated, provider = anonymous_plan
    run_one(core_database, d, provider=provider)
    assert d.decide().status_code == 200
    for _ in range(3):
        run_one(core_database, d, provider=provider)
    assert d.workflow["status"] == "WAITING_HUMAN", d.workflow
    response, _ = submit(d)
    assert response.status_code == 200, response.text
    d.refresh()
    for _ in range(6):
        run_one(core_database, d, provider=provider)
    assert d.workflow["draft_version"] == 2 and d.workflow["status"] == "WAITING_HUMAN"

    seen = set()
    missing = []
    for request in provider.requests:
        if request.task_type not in POV_TASKS:
            continue
        seen.add(request.task_type)
        identities = {
            value.structured_payload["character_id"]
            for value in request.context_package.items
            if value.selector_id == PROFILE_SELECTOR
        }
        if identities != {str(pov.id)}:
            missing.append((request.task_type, identities))
        assert str(unrelated.id) not in identities
    assert seen == POV_TASKS
    assert not missing, missing


@pytest.mark.integration
def test_queued_anonymous_pov_review_detects_approval_drift(anonymous_plan, core_database):
    d, pov, _, provider = anonymous_plan
    run_one(core_database, d, provider=provider)
    assert d.decide().status_code == 200
    run_one(core_database, d, provider=provider)
    queued = next(t for t in d.read("/agent-tasks") if t["status"] == "PENDING")
    assert queued["task_type"] == "REVIEW_CHAPTER_COMPLIANCE"
    profile_version(
        core_database,
        UUID(d.workflow["project_id"]),
        pov.id,
        1,
        communication_style="Long deliberate answers",
    )
    before_calls = len(provider.requests)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == before_calls
    failed = next(t for t in d.read("/agent-tasks") if t["task_id"] == queued["task_id"])
    assert failed["last_error_code"] == "CONTEXT_STALE"
    assert d.workflow["current_state"] == "C90_BLOCKED"


@pytest.mark.integration
def test_plan_review_pov_uses_exact_generation_without_required_plan_selector(
    anonymous_plan, core_database
):
    d, pov, _, _ = anonymous_plan
    queued = next(t for t in d.read("/agent-tasks") if t["status"] == "PENDING")
    response = d.client.post(
        d.chapter_api + "/plans",
        json={
            "expected_version": 1,
            "objective": "Atlas searches the road alone",
            "required_outcome": "Atlas decides to leave",
        },
    )
    assert response.status_code == 201, response.text
    assert d.client.get(d.chapter_api).json()["current_plan_version"] == 2
    d.refresh()
    assert d.workflow["plan_version"] == 1
    with core_database.session() as session:
        service = ContextService(session)
        task = AgentTaskRepository(session).get(UUID(queued["task_id"]))
        workflow = WorkflowRepository(session).get(UUID(d.workflow["id"]))
        profile = service.registry.for_task(task.task_type)
        profile = profile.model_copy(
            update={
                "selectors": tuple(
                    s for s in profile.selectors if s.source_type != SourceType.CHAPTER_PLAN
                )
            }
        )
        request = service.request_for_task(task, workflow, profile)
        assert request.character_id == pov.id
        assert request.approved_plan_version is None
        assert request.knowledge_scope == KnowledgeScope.GLOBAL_ONLY
        # A missing exact version must never fall back to a current or approved Plan.
        missing = service.request_for_task(task, replace(workflow, plan_version=None), profile)
        assert missing.character_id is None
        assert "workflow.plan_version" in missing.missing_bindings

        for task_type in POV_TASKS - {"WRITE_CHAPTER"}:
            bound_request = replace(request, task_type=task_type)
            private = item(
                bound_request,
                selector_id="committed-memory",
                knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
                character_id=pov.id,
                provenance=("committed_memory",),
            )
            assert (
                ContextFilter().reason(
                    private, selector(), bound_request, ContextProfileRegistry().for_task(task_type)
                )
                == ExclusionReason.CHARACTER_KNOWLEDGE
            )
            future = item(bound_request, chapter_sequence=request.chapter_sequence + 10)
            assert (
                ContextFilter().reason(
                    future, selector(), bound_request, ContextProfileRegistry().for_task(task_type)
                )
                == ExclusionReason.FUTURE_KNOWLEDGE
            )
