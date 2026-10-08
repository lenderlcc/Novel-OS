"""Offline evidence for relevant tendencies, exact lineage and approval freshness."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from novel_os.context.engine import ContextEngine, FreshnessValidator
from novel_os.context.policies import ContextFilter
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import (
    ContextRequest,
    ExclusionReason,
    KnowledgeScope,
    SourceRef,
    SourceType,
)
from novel_os.domain.core import CommandContext, now
from novel_os.domain.enums import Authority
from novel_os.domain.memory import MemorySubject
from novel_os.repositories.memory import MemoryRepository
from novel_os.services.canon_context import CanonContextReader
from novel_os.services.character_profile_context import PROFILE_SELECTOR
from novel_os.services.character_profiles import CharacterProfileService
from novel_os.services.memory_query import MemoryQueryService
from tests.context.test_context import item
from tests.core.conftest import chapter_api as chapter_api
from tests.core.conftest import core_client as core_client
from tests.core.conftest import core_database as core_database
from tests.core.conftest import core_settings as core_settings
from tests.core.conftest import migration_config as migration_config
from tests.core.conftest import project_api as project_api
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_revision import finish_review, request_revision
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider


def actor():
    return CommandContext(actor_id="character-test-user", request_id=str(uuid4()))


def character(database, project_id, name):
    with database.session() as session:
        return CharacterProfileService(session).create_character(
            project_id, name, [], actor(), "Define a character for this test"
        )


def profile_version(database, project_id, character_id, version=0, *, approved=True, **body):
    with database.session() as session:
        record = CharacterProfileService(session).create_draft(
            project_id, character_id, body, version, actor(), "Define tendencies"
        )
    if approved:
        with database.session() as session:
            record = CharacterProfileService(session).approve(
                project_id, character_id, record.version, actor(), "Approve tendencies"
            )
    return record


def query(database, request, task_type):
    profile = ContextProfileRegistry().for_task(task_type)
    profile = profile.model_copy(
        update={
            "selectors": tuple(s for s in profile.selectors if s.selector_id == PROFILE_SELECTOR)
        }
    )
    with database.session() as session:
        batch = MemoryQueryService(session).query(request, profile, now(), now())
    return profile, batch


@pytest.mark.integration
@pytest.mark.parametrize(
    "task_type",
    [
        "EXPLORE_CHAPTER_CONCEPTS",
        "PLAN_CHAPTER",
        "WRITE_CHAPTER",
        "REVIEW_CHAPTER_NARRATIVE",
        "REVISE_CHAPTER",
        "INTERPRET_CHAPTER_FEEDBACK",
    ],
)
def test_approved_profiles_and_relevant_pairs_use_one_immutable_source(
    core_database, project_api, chapter_api, task_type
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    b = character(core_database, project_id, "Jun")
    unrelated = character(core_database, project_id, "Atlas")
    approved = profile_version(
        core_database,
        project_id,
        a.id,
        attention_bias="Notices exits first; this grants no hidden information",
        relationship_modifiers=[
            {"other_character_id": str(b.id), "interaction_tendency": "Explains more to Jun"},
            {
                "other_character_id": str(unrelated.id),
                "interaction_tendency": "UNRELATED_MODIFIER_MUST_STAY_OUT",
            },
        ],
    )
    profile_version(
        core_database, project_id, unrelated.id, communication_style="UNRELATED_PROFILE"
    )
    profile_version(
        core_database, project_id, b.id, approved=False, communication_style="DRAFT_ONLY"
    )
    request = ContextRequest(
        project_id=project_id,
        task_id=uuid4(),
        chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
        task_type=task_type,
        objective="Mira meets Jun under time pressure",
        character_id=a.id if task_type == "WRITE_CHAPTER" else None,
        workflow_state_version=1,
    )
    selected_profile, batch = query(core_database, request, task_type)
    result = ContextEngine().build(request, selected_profile, batch)
    assert result.status == "READY"
    assert len(result.package.items) == 1
    selected = result.package.items[0]
    assert selected.source_type == SourceType.EXTENSION
    assert selected.selector_id == PROFILE_SELECTOR
    assert selected.structured_payload["kind"] == "CHARACTER_BEHAVIOR_PROFILE"
    assert selected.ref.logical_id == approved.logical_id != a.id
    assert selected.source_id == approved.id
    assert selected.structured_payload["character_profile_id"] == str(approved.logical_id)
    assert selected.ref.version == selected.structured_payload["relationship_modifier_version"] == 1
    assert selected.structured_payload["character_profile_hash"] == approved.profile_hash
    assert selected.status == "APPROVED" and selected.authority_level == Authority.A3_CANON
    assert selected.priority == "P0" and not selected.locked and not selected.is_plan
    assert selected.knowledge_scope == KnowledgeScope.GLOBAL_ONLY
    modifiers = selected.structured_payload["profile"]["relationship_modifiers"]
    assert [modifier["other_character_id"] for modifier in modifiers] == [str(b.id)]
    assert "UNRELATED" not in selected.payload_json and "DRAFT_ONLY" not in selected.payload_json
    # Model projection is a copy; filtering did not mutate the immutable profile body.
    assert len(approved.body["relationship_modifiers"]) == 2


@pytest.mark.integration
def test_identity_and_profile_extension_sources_have_distinct_logical_namespaces(
    core_database, project_api, chapter_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    subject = character(core_database, project_id, "Mira")
    approved = profile_version(core_database, project_id, subject.id, communication_style="Brief")
    request = ContextRequest(
        project_id=project_id,
        chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
        task_id=uuid4(),
        task_type="PLAN_CHAPTER",
        objective="Mira must choose quickly",
    )
    profile = ContextProfileRegistry().for_task(request.task_type)
    profile = profile.model_copy(
        update={
            "selectors": tuple(
                s
                for s in profile.selectors
                if s.selector_id in {"memory-subjects", PROFILE_SELECTOR}
            )
        }
    )
    with core_database.session() as session:
        batch = MemoryQueryService(session).query(request, profile, now(), now())
    result = ContextEngine().build(request, profile, batch)
    assert result.status == "READY"
    selected = {item.selector_id: item for item in result.package.items}
    assert set(selected) == {"memory-subjects", PROFILE_SELECTOR}
    identity, behavior = selected["memory-subjects"], selected[PROFILE_SELECTOR]
    assert identity.source_type == behavior.source_type == SourceType.EXTENSION
    assert identity.logical_id == subject.id
    assert behavior.ref.logical_id == approved.logical_id != identity.ref.logical_id
    assert behavior.source_id == approved.id
    assert behavior.structured_payload["character_id"] == str(subject.id)
    assert behavior.structured_payload["kind"] == "CHARACTER_BEHAVIOR_PROFILE"
    assert len({item.ref for item in result.package.items}) == 2


@pytest.mark.integration
def test_approval_freshness_includes_empty_sets_and_preserves_the_prior_snapshot(
    core_database, project_api, chapter_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    request = ContextRequest(
        project_id=project_id,
        chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
        task_id=uuid4(),
        task_type="PLAN_CHAPTER",
        objective="Mira must choose quickly",
        workflow_state_version=1,
    )
    selected_profile, empty = query(core_database, request, request.task_type)
    package = ContextEngine().build(request, selected_profile, empty).package
    assert package.build_status == "READY" and package.items == ()
    draft = profile_version(
        core_database, project_id, a.id, approved=False, communication_style="Brief"
    )
    assert query(core_database, request, request.task_type)[1].snapshots == empty.snapshots
    with core_database.session() as session:
        CharacterProfileService(session).approve(
            project_id, a.id, draft.version, actor(), "Approve"
        )
    approved_profile, approved = query(core_database, request, request.task_type)
    assert (
        FreshnessValidator()
        .validate(
            package,
            source_snapshots=approved.snapshots,
            workflow_state_version=1,
            profile_hash=approved_profile.profile_hash,
        )
        .status
        == "STALE"
    )
    original = ContextEngine().build(request, approved_profile, approved).package
    profile_version(core_database, project_id, a.id, 1, communication_style="Detailed")
    changed = query(core_database, request, request.task_type)[1]
    assert changed.snapshots != approved.snapshots
    assert original.items[0].source_version == 1
    assert original.items[0].structured_payload["profile"]["communication_style"] == "Brief"


def test_tendencies_do_not_authorize_another_characters_knowledge():
    request = ContextRequest(
        project_id=uuid4(),
        chapter_id=uuid4(),
        task_id=uuid4(),
        task_type="WRITE_CHAPTER",
        character_id=uuid4(),
    )
    profile = ContextProfileRegistry().for_task(request.task_type)
    selector = next(s for s in profile.selectors if s.selector_id == "committed-memory")
    knowledge = item(
        request,
        selector_id=selector.selector_id,
        status="ACTIVE",
        authority_level=Authority.A3_CANON,
        knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
        character_id=uuid4(),
        provenance=("committed_memory",),
    )
    assert ContextFilter().reason(knowledge, selector, request, profile) == (
        ExclusionReason.CHARACTER_KNOWLEDGE
    )
    assert (
        ContextFilter().reason(
            replace(knowledge, character_id=request.character_id), selector, request, profile
        )
        is None
    )


@pytest.mark.parametrize("manual", [False, True])
def test_identity_payload_retains_historical_shape_and_truthful_provenance(manual):
    request = ContextRequest(
        project_id=uuid4(), chapter_id=uuid4(), task_id=uuid4(), task_type="PLAN_CHAPTER"
    )
    subject = MemorySubject(
        id=uuid4(),
        project_id=request.project_id,
        name="Mira",
        normalized_name="mira",
        kind="CHARACTER",
        aliases=[],
        batch_id=None if manual else uuid4(),
        created_by="profile-user",
    )
    reader = CanonContextReader(None)
    reader.repo = SimpleNamespace(subjects_in_text=lambda *_, **__: [subject])
    selector = next(
        s
        for s in ContextProfileRegistry().for_task(request.task_type).selectors
        if s.selector_id == "memory-subjects"
    )
    selected = reader.query(request, selector)[0][0]
    assert selected.source_created_at == subject.created_at
    assert set(selected.structured_payload["subject"]) == {
        "id",
        "project_id",
        "name",
        "normalized_name",
        "kind",
        "aliases",
        "batch_id",
    }
    assert selected.provenance == (
        ("manual_character_identity", "profile-user")
        if manual
        else ("memory_subject", str(subject.batch_id))
    )
    assert ("prior-chapter" in selected.selected_reason) is not manual


@pytest.mark.integration
@pytest.mark.parametrize("scope", ["approved_plan", "brief_and_concept"])
def test_short_names_in_metadata_are_absent_and_do_not_invalidate_relevant_context(
    core_client, core_database, project_api, chapter_api, monkeypatch, scope
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    chapter_id = UUID(chapter_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    character(core_database, project_id, "Jun")
    unrelated = [character(core_database, project_id, name) for name in ("C", "B", "AB")]
    profile_version(core_database, project_id, a.id, communication_style="Brief")
    workflow_id, concept_id = uuid4(), uuid4()
    changes = {}
    if scope == "approved_plan":
        response = core_client.post(
            chapter_api + "/plans",
            json={
                "expected_version": 0,
                "objective": "Mira meets Jun",
                "required_outcome": "Mira meets Jun",
                "scene_plans": [
                    {"id": "C", "purpose": "Mira meets Jun", "character_id": str(unrelated[0].id)}
                ],
            },
        )
        assert response.status_code == 201, response.text
        response = core_client.post(chapter_api + "/plans/approve", json={"expected_version": 1})
        assert response.status_code == 200, response.text
        changes["approved_plan_version"] = 1
    else:
        from novel_os.repositories import planning

        artifact = SimpleNamespace(
            project_id=project_id,
            chapter_id=chapter_id,
            workflow_id=workflow_id,
            body={
                "selected_candidate_id": "C",
                "candidates": [
                    {
                        "id": "C",
                        "core_event": "Mira meets Jun",
                        "major_change_risk": "LOW",
                        "similarity_risk": "MEDIUM",
                        "authority_fit": "WITHIN_BOUNDS",
                        "source_refs": [{"logical_id": str(unrelated[0].id)}],
                    }
                ],
            },
        )
        monkeypatch.setattr(
            planning,
            "PlanningRepository",
            lambda _: SimpleNamespace(
                brief=lambda _: SimpleNamespace(
                    status="READY", body={"character_focus": ["Mira", "Jun"]}
                ),
                exploration_by_id=lambda _: artifact,
            ),
        )
        changes.update(
            workflow_id=workflow_id,
            explicit_refs=(
                SourceRef(source_type=SourceType.EXTENSION, logical_id=concept_id, version=1),
            ),
            requirements=(
                '{"type":"USER_PLANNING_DIRECTIVE","reason":"Mira meets Jun","plan_id":"C"}',
            ),
        )
    request = ContextRequest(
        project_id=project_id,
        chapter_id=chapter_id,
        task_id=uuid4(),
        task_type="PLAN_CHAPTER",
        objective="Mira meets Jun",
        **changes,
    )
    _, before = query(core_database, request, request.task_type)
    assert {item.character_id for item in before.items} == {a.id}
    for subject in unrelated:
        profile_version(core_database, project_id, subject.id, communication_style="UNRELATED")
    _, after = query(core_database, request, request.task_type)
    assert {item.character_id for item in after.items} == {a.id}
    assert before.snapshots == after.snapshots
    with core_database.session() as session:
        assert MemoryRepository(session).subjects_in_text(project_id, "A\nB") == [unrelated[1]]


@pytest.mark.integration
@pytest.mark.parametrize(
    "story_field, story_value",
    [
        ("required_outcome", "Jun leaves with a promise to meet again"),
        ("plot_progression", {"outcome": "Jun leaves with a promise to meet again"}),
        ("information_release", ["Jun learns when to return"]),
        ("ending_state", {"outcome": "Jun leaves with a promise to meet again"}),
        ("constraints", ["Jun must not learn the secret"]),
        ("risks", ["Jun may refuse the invitation"]),
    ],
)
def test_approved_plan_story_fields_select_profiles_and_pairs_without_latest_draft_leakage(
    core_client, core_database, project_api, chapter_api, story_field, story_value
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    b = character(core_database, project_id, "Jun")
    unrelated = character(core_database, project_id, "Atlas")
    profile_version(
        core_database,
        project_id,
        a.id,
        communication_style="Brief",
        relationship_modifiers=[
            {"other_character_id": str(b.id), "interaction_tendency": "Explains more to Jun"},
            {
                "other_character_id": str(unrelated.id),
                "interaction_tendency": "UNRELATED_MODIFIER",
            },
        ],
    )
    profile_version(core_database, project_id, b.id, communication_style="Patient")
    profile_version(core_database, project_id, unrelated.id, communication_style="UNRELATED")
    profile_version(core_database, project_id, b.id, 1, approved=False, communication_style="DRAFT")
    response = core_client.post(
        chapter_api + "/plans",
        json={
            "expected_version": 0,
            "objective": "Mira waits for a visitor",
            "required_outcome": "Mira agrees to meet again",
            "scene_plans": [{"purpose": "Mira offers a seat", "character_id": str(unrelated.id)}],
            story_field: story_value,
        },
    )
    assert response.status_code == 201, response.text
    response = core_client.post(chapter_api + "/plans/approve", json={"expected_version": 1})
    assert response.status_code == 200, response.text
    response = core_client.post(
        chapter_api + "/plans",
        json={
            "expected_version": 1,
            "objective": "Atlas waits for Mira",
            "required_outcome": "Atlas meets Mira",
        },
    )
    assert response.status_code == 201, response.text
    chapter = core_client.get(chapter_api).json()
    assert (chapter["current_plan_version"], chapter["approved_plan_version"]) == (2, 1)
    request = ContextRequest(
        project_id=project_id,
        chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
        task_id=uuid4(),
        task_type="WRITE_CHAPTER",
        character_id=a.id,
        approved_plan_version=1,
    )
    _, batch = query(core_database, request, request.task_type)
    selected = {item.character_id: item for item in batch.items}
    assert set(selected) == {a.id, b.id}
    assert selected[b.id].source_version == 1
    assert selected[b.id].structured_payload["profile"]["communication_style"] == "Patient"
    modifiers = selected[a.id].structured_payload["profile"]["relationship_modifiers"]
    assert [modifier["other_character_id"] for modifier in modifiers] == [str(b.id)]
    assert "UNRELATED" not in selected[a.id].payload_json


@pytest.mark.integration
@pytest.mark.parametrize("phase", ["planning", "writing"])
@pytest.mark.parametrize("timing", ["queued", "inflight"])
def test_approved_profile_updates_stale_actual_tasks_before_persistence(
    core_client, core_database, project_api, chapter_api, phase, timing
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    profile_version(core_database, project_id, a.id, communication_style="Brief")
    driver = (
        PlanningDriver(core_client, chapter_api, "Mira must choose quickly")
        if phase == "planning"
        else QualityDriver(core_client, chapter_api, "Mira must choose quickly")
    )
    run_one(core_database, driver)
    if phase == "writing":
        run_one(core_database, driver)
        run_one(core_database, driver)
        assert driver.decide().status_code == 200

    def change():
        profile_version(core_database, project_id, a.id, 1, communication_style="Detailed")

    if timing == "queued":
        change()
    provider = RecordedProvider(lambda *_: change() if timing == "inflight" else None)
    run_one(core_database, driver, provider=provider)
    assert len(provider.requests) == (1 if timing == "inflight" else 0)
    assert driver.workflow["current_state"] == "C90_BLOCKED", driver.workflow
    assert driver.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"
    chapter = core_client.get(chapter_api).json()
    assert chapter["current_version"] is None
    if phase == "planning":
        assert chapter["current_plan_version"] is None
    if provider.requests:
        selected = [
            item
            for item in provider.requests[0].context_package.items
            if item.selector_id == PROFILE_SELECTOR
        ]
        assert selected[0].source_version == 1


@pytest.mark.integration
@pytest.mark.parametrize("phase", ["revision", "feedback"])
@pytest.mark.parametrize("timing", ["queued", "inflight"])
def test_approved_changes_stale_revision_and_feedback_without_mutating_source_draft(
    core_client, core_database, project_api, chapter_api, phase, timing
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    profile_version(core_database, project_id, a.id, communication_style="Brief")
    draft(core_client, project_api, narrative_perspective="THIRD_PERSON")
    approve(core_client, project_api)
    driver = QualityDriver(core_client, chapter_api, "Mira must choose quickly")
    driver.approve_plan(core_database)
    review = finish_review(driver, core_database)
    source = core_client.get(chapter_api + "/versions/1").json()
    if phase == "revision":
        request_revision(driver, review)
    else:
        response, _ = submit(driver, "Mira should speak more briefly in this scene")
        assert response.status_code == 200, response.text
        driver.refresh()

    def change():
        profile_version(core_database, project_id, a.id, 1, communication_style="Detailed")

    if timing == "queued":
        change()
    provider = RecordedProvider(lambda *_: change() if timing == "inflight" else None)
    run_one(core_database, driver, provider=provider)
    assert len(provider.requests) == (1 if timing == "inflight" else 0)
    assert driver.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"
    assert driver.workflow["current_state"] == "C90_BLOCKED", driver.workflow
    assert core_client.get(chapter_api + "/versions/1").json() == source
    assert core_client.get(chapter_api).json()["current_version"] == 1
    if phase == "revision":
        assert driver.read("/revisions")[0]["plan"] is None
    else:
        assert driver.read("/feedback")[0]["interpretation"] is None
    if provider.requests:
        selected = [
            item
            for item in provider.requests[0].context_package.items
            if item.selector_id == PROFILE_SELECTOR
        ]
        assert selected[0].source_version == 1
