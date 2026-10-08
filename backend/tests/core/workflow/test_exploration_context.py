"""Exploration reuses exact, bounded Context selection without exposing rejected ideas."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from novel_os.context.policies import ContextFilter
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import (
    ContextRequest,
    ExclusionReason,
    KnowledgeScope,
    SourceRef,
    SourceType,
)
from novel_os.domain.core import now
from novel_os.domain.enums import Authority
from novel_os.domain.memory import CommittedMemory, MemoryType
from novel_os.services.exploration_context import ExplorationContextReader
from novel_os.services.memory_query import MemoryQueryService
from tests.core.conftest import chapter_api as chapter_api
from tests.core.conftest import core_client as core_client
from tests.core.conftest import core_database as core_database
from tests.core.conftest import core_settings as core_settings
from tests.core.conftest import migration_config as migration_config
from tests.core.conftest import project_api as project_api
from tests.core.workflow.test_context_engine import chapter, plan, post


def request(**changes):
    return ContextRequest(
        project_id=uuid4(),
        task_id=uuid4(),
        workflow_id=uuid4(),
        task_type="EXPLORE_CHAPTER_CONCEPTS",
        chapter_id=uuid4(),
        chapter_sequence=5,
        **changes,
    )


def selected_reader(value):
    brief = SimpleNamespace(id=uuid4())
    artifact = SimpleNamespace(
        id=uuid4(),
        project_id=value.project_id,
        chapter_id=value.chapter_id,
        workflow_id=value.workflow_id,
        brief_id=brief.id,
        status="READY",
        agent_run_id=uuid4(),
        created_at=now(),
        body={
            "candidates": [
                {"id": "chosen", "core_event": "A character reassesses a failed judgment"},
                {"id": "rejected", "core_event": "REJECTED_SECRET_NEVER_BECOMES_CANON"},
            ],
            "selected_candidate_id": "chosen",
            "selection_reason": "Fits this character within the existing direction",
            "rejected_reasons": [{"candidate_id": "rejected", "reason": "Major change"}],
        },
    )
    reader = ExplorationContextReader(None)
    reader.planning = SimpleNamespace(
        brief=lambda _: brief,
        exploration=lambda *_: artifact,
        exploration_by_id=lambda _: artifact,
    )
    return reader, artifact


def test_profiles_keep_history_and_selected_concepts_bounded():
    profiles = ContextProfileRegistry()
    exploration = profiles.for_task("EXPLORE_CHAPTER_CONCEPTS")
    assert (exploration.profile_id, exploration.version) == ("CP-004E", 2)
    assert exploration.future_knowledge_policy == "REQUIRED_ONLY"
    assert not any(s.source_type == "CHAPTER_VERSION" for s in exploration.selectors)
    selectors = {s.selector_id: s for s in exploration.selectors}
    assert selectors["committed-memory"].priority == "P0"
    assert selectors["approved-project-writing-profile"].priority == "P0"
    assert selectors["recent-approved-plans"].max_items == 3
    assert selectors["recent-final-summaries"].priority == "P1"
    assert selectors["recent-final-summaries"].max_items == 3
    assert "selected-creative-concept" not in selectors
    planning = profiles.resolve("CP-004", 7)
    assert planning.future_knowledge_policy == "REQUIRED_ONLY"
    selected = next(s for s in planning.selectors if s.selector_id == "selected-creative-concept")
    assert (selected.scope, selected.version_policy, selected.max_items) == ("EXPLICIT", "EXACT", 1)
    assert profiles.resolve("CP-004", 6).future_knowledge_policy == "LIMITED"


def test_selected_only_projection_requires_exact_reference_and_keeps_a7():
    value = replace(request(), task_type="PLAN_CHAPTER")
    reader, artifact = selected_reader(value)
    artifact.body["selection_reason"] = (
        "Select chosen because REJECTED_SECRET_NEVER_BECOMES_CANON needs a major new fact."
    )
    profile = ContextProfileRegistry().resolve("CP-004", 7)
    selector = next(s for s in profile.selectors if s.selector_id == "selected-creative-concept")
    assert reader.query(value, selector)[0] == ()
    reference = SourceRef(source_type=SourceType.EXTENSION, logical_id=artifact.id, version=1)
    selected, _ = reader.query(replace(value, explicit_refs=(reference,)), selector)
    assert len(selected) == 1
    item = selected[0]
    assert item.authority_level == Authority.A7_AI_INFERENCE
    assert item.ref == reference and not item.is_plan and not item.locked
    assert item.structured_payload["selected_candidate"]["id"] == "chosen"
    assert "rejected" not in item.payload_json.lower()
    assert "REJECTED_SECRET_NEVER_BECOMES_CANON" not in item.payload_json
    assert "selection_reason" not in item.structured_payload
    assert "REJECTED_SECRET_NEVER_BECOMES_CANON" in artifact.body["selection_reason"]
    # The projection cannot mutate the immutable persisted artifact through its returned copy.
    item.structured_payload["selected_candidate"]["id"] = "changed"
    assert artifact.body["selected_candidate_id"] == "chosen"
    assert (
        reader.query(
            replace(value, task_type="WRITE_CHAPTER", explicit_refs=(reference,)), selector
        )[0]
        == ()
    )


@pytest.mark.parametrize("changed", ["chapter_id", "project_id", "workflow_id", "brief_id"])
def test_selected_projection_rejects_cross_binding(changed):
    value = replace(request(), task_type="PLAN_CHAPTER")
    reader, artifact = selected_reader(value)
    reference = SourceRef(source_type=SourceType.EXTENSION, logical_id=artifact.id, version=1)
    setattr(artifact, changed, uuid4())
    selector = next(
        s
        for s in ContextProfileRegistry().resolve("CP-004", 7).selectors
        if s.selector_id == "selected-creative-concept"
    )
    assert reader.query(replace(value, explicit_refs=(reference,)), selector)[0] == ()


def test_same_a03_knowledge_owner_policy_and_required_future_firewall():
    from tests.context.test_context import item

    value = request()
    profile = ContextProfileRegistry().resolve("CP-004E", 1)
    selector = next(s for s in profile.selectors if s.selector_id == "committed-memory")
    owner = uuid4()
    knowledge = item(
        value,
        selector_id="committed-memory",
        authority_level=Authority.A3_CANON,
        status="ACTIVE",
        knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
        character_id=owner,
        provenance=("committed_memory",),
    )
    assert ContextFilter().reason(knowledge, selector, value, profile) is None
    assert (
        ContextFilter().reason(
            knowledge,
            selector,
            replace(
                value, knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE, character_id=uuid4()
            ),
            profile,
        )
        == ExclusionReason.CHARACTER_KNOWLEDGE
    )
    future = replace(knowledge, future_knowledge=True, chapter_sequence=6)
    assert (
        ContextFilter().reason(future, selector, value, profile) == ExclusionReason.FUTURE_KNOWLEDGE
    )
    assert (
        ContextFilter().reason(
            future, selector, replace(value, required_future_refs=(future.ref,)), profile
        )
        is None
    )


def test_recent_summaries_reuse_only_committed_derived_records(monkeypatch):
    from novel_os.services import exploration_context

    value = request()
    chapter_id, batch_id = uuid4(), uuid4()
    entry = CommittedMemory(
        project_id=value.project_id,
        chapter_id=chapter_id,
        chapter_version_id=uuid4(),
        batch_id=batch_id,
        candidate_id="derived-summary",
        logical_id=uuid4(),
        version=1,
        supersedes_id=None,
        subject_id=None,
        memory_type=MemoryType.DERIVED_CHAPTER_SUMMARY,
        slot="chapter_summary",
        value="A prior local misjudgment changed their cooperation",
        statement="A prior local misjudgment changed their cooperation",
        epistemic_status=None,
        authority_level=Authority.A6_DERIVED_MEMORY,
        body={"unrelated_prose": "FULL_CHAPTER_BODY_MUST_NOT_BE_LOADED"},
    )
    calls = []

    def entries(project_id, **kwargs):
        calls.append((project_id, kwargs))
        return [entry]

    monkeypatch.setattr(
        exploration_context,
        "MemoryRepository",
        lambda _: SimpleNamespace(batch=lambda _: SimpleNamespace(id=batch_id), entries=entries),
    )
    reader = ExplorationContextReader(None)
    reader.sources = SimpleNamespace(
        recent_approved=lambda project_id, sequence, limit: [
            SimpleNamespace(id=chapter_id, sequence=4)
        ]
    )
    selector = next(
        s
        for s in ContextProfileRegistry().resolve("CP-004E", 1).selectors
        if s.selector_id == "recent-final-summaries"
    )
    items, _ = reader.query(value, selector)
    assert len(items) == 1 and items[0].authority_level == Authority.A6_DERIVED_MEMORY
    assert items[0].chapter_sequence == 4
    assert items[0].structured_payload == {
        "memory_type": "DERIVED_CHAPTER_SUMMARY",
        "subject_id": None,
        "statement": entry.statement,
        "slot": entry.slot,
        "value": entry.value,
        "state_after": None,
        "epistemic_status": None,
        "role": "DERIVED_HINT",
        "source_chapter_version_id": str(entry.chapter_version_id),
        "known_fact_id": None,
    }
    assert "FULL_CHAPTER_BODY" not in items[0].payload_json
    assert calls == [
        (
            value.project_id,
            {
                "types": [MemoryType.DERIVED_CHAPTER_SUMMARY],
                "before_sequence": 5,
                "batch_id": batch_id,
                "limit": 1,
            },
        )
    ]


@pytest.mark.integration
def test_recent_plans_use_three_approved_pointers_without_body_dump(
    core_client, chapter_api, core_database
):
    project_url = chapter_api.split("/chapters/")[0]
    urls = {1: chapter_api}
    urls.update({i: chapter(core_client, project_url, i) for i in range(2, 7)})
    for sequence in (1, 2, 3, 4, 6):
        plan(
            core_client,
            urls[sequence],
            objective=f"Approved event {sequence}",
            scene_plans=[{"body": "FULL_SCENE_PROSE_MUST_BE_OMITTED" * 1000}],
        )
        post(core_client, urls[sequence] + "/plans/approve", {"expected_version": 1})
        plan(core_client, urls[sequence], 2, objective="UNAPPROVED_CURRENT_PLAN_SECRET")
    profile = ContextProfileRegistry().resolve("CP-004E", 1)
    selector = next(s for s in profile.selectors if s.selector_id == "recent-approved-plans")
    profile = profile.model_copy(update={"selectors": (selector,)})
    value = replace(
        request(),
        project_id=UUID(project_url.rsplit("/", 1)[1]),
        chapter_id=UUID(urls[5].rsplit("/", 1)[1]),
    )

    def query():
        with core_database.session() as session:
            return MemoryQueryService(session).query(value, profile, now(), now())

    before = query()
    assert len(before.items) == 3
    assert {item.chapter_sequence for item in before.items} == {2, 3, 4}
    assert {item.source_version for item in before.items} == {1}
    for context_item in before.items:
        assert "scene_plans" not in context_item.structured_payload
        assert "FULL_SCENE_PROSE" not in context_item.payload_json
        assert "UNAPPROVED_CURRENT_PLAN_SECRET" not in context_item.payload_json
        assert context_item.structured_payload["role"] == "APPROVED_PLAN_NOT_FACT"
        assert context_item.is_plan
    plan(core_client, urls[4], 3, objective="Another unapproved proposal")
    assert query().snapshots == before.snapshots
    post(core_client, urls[4] + "/plans/approve", {"expected_version": 3})
    assert query().snapshots != before.snapshots


@pytest.mark.integration
def test_two_committed_summaries_deduplicate_in_actual_v7_planning_context(
    core_client, chapter_api, core_database
):
    from tests.core.quality.conftest import QualityDriver
    from tests.core.quality.test_memory_commit import confirm, prepare
    from tests.core.test_writing_profiles import approve, draft
    from tests.core.workflow.test_creative_exploration import (
        ExplorationDriver,
        ExplorationProvider,
        explore,
    )
    from tests.core.workflow.test_planning_vertical_slice import run_one

    project_url = chapter_api.split("/chapters/")[0]
    draft(core_client, project_url, narrative_perspective="THIRD_PERSON")
    approve(core_client, project_url)
    expected_entries, expected_versions = set(), set()

    def summary_only(_, body):
        body["result"]["candidates"] = [
            c
            for c in body["result"]["candidates"]
            if c["candidate_type"] == "DERIVED_CHAPTER_SUMMARY"
        ]

    for sequence in (1, 2):
        url = chapter_api if sequence == 1 else chapter(core_client, project_url, sequence)
        prior = QualityDriver(core_client, url).approve_plan(core_database)
        accepted = prepare(prior, core_database, summary_only)
        response = confirm(prior, ["summary"])
        assert response.status_code == 200, response.text
        prior.refresh()
        assert prior.workflow["current_state"] == "C16_COMPLETED"
        entries = prior.read("/memory")[0]["entries"]
        assert len(entries) == 1 and entries[0]["memory_type"] == "DERIVED_CHAPTER_SUMMARY"
        expected_entries.add(entries[0]["id"])
        expected_versions.add(accepted["id"])

    driver = ExplorationDriver(core_client, chapter(core_client, project_url, 3))
    provider, _ = explore(core_database, driver, ExplorationProvider())
    run_one(core_database, driver, provider=provider)
    assert driver.workflow["current_state"] == "C05_PLAN_REVIEW", driver.workflow
    package = provider.requests[-1].context_package
    assert (package.profile_id, package.profile_version) == ("CP-004", 9)
    assert package.authority_conflicts == ()
    summaries = [
        item
        for item in package.items
        if item.structured_payload.get("memory_type") == "DERIVED_CHAPTER_SUMMARY"
    ]
    assert {str(item.source_id) for item in summaries} == expected_entries
    assert len(summaries) == 2
    assert {
        item.structured_payload["source_chapter_version_id"] for item in summaries
    } == expected_versions
    for item in summaries:
        assert item.authority_level == "A6_DERIVED_MEMORY"
        assert item.knowledge_scope == "GLOBAL_ONLY" and item.character_id is None
        assert item.structured_payload["subject_id"] is None
        assert item.structured_payload["epistemic_status"] is None
        assert item.structured_payload["known_fact_id"] is None
        assert item.structured_payload["role"] == "DERIVED_HINT"
    duplicates = {
        str(item.source_id) for item in package.excluded_items if item.reason == "DUPLICATE"
    }
    assert expected_entries <= duplicates
