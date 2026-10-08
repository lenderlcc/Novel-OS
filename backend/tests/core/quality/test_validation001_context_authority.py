"""Local VALIDATION-001 evidence. Recorded inputs verify wiring, never AI quality."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from novel_os.context.engine import ContextEngine
from novel_os.context.policies import TokenBudgetService
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import ContextRequest, SourceType
from novel_os.domain.enums import Authority
from novel_os.memory.policy import normalized
from novel_os.repositories.memory import MemoryRepository
from novel_os.services.character_profiles import CharacterProfileService
from tests.context.test_character_profile_context import actor, character, profile_version, query
from tests.context.test_context import build, item
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_checkpoint_phase2 import Phase2Driver, recorded_slice
from tests.core.quality.test_memory_commit import confirm, prepare
from tests.core.quality.test_memory_context_isolation import (
    LATER,
    candidates,
    commit_initial,
    committed_items,
)
from tests.core.workflow.test_creative_exploration import (
    REJECTED_SENTINEL,
    ExplorationDriver,
    ExplorationProvider,
)
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.writing_support import chapter


@pytest.mark.integration
@pytest.mark.parametrize("as_alias", [False, True], ids=["display", "alias"])
@pytest.mark.parametrize(
    "name, unrelated",
    [
        ("É", "café"),
        ("Émile", "ÉmileExtra"),
        ("François", "Françoise"),
        ("E\u0301mile", "ÉmileExtra"),
        ("Ｆｒａｎçｏｉｓ", "Françoise"),
        ("R2D2", "R2D2X"),
        ("A1", "A10"),
    ],
    ids=[
        "accent-in-word",
        "accent-prefix",
        "accent-suffix",
        "decomposed",
        "fullwidth",
        "latin-digit",
        "digit-suffix",
    ],
)
def test_latin_accent_name_and_alias_context_boundaries(
    core_database, project_api, chapter_api, name, unrelated, as_alias
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    with core_database.session() as session:
        subject = CharacterProfileService(session).create_character(
            project_id,
            "AliasTarget" if as_alias else name,
            [name] if as_alias else [],
            actor(),
            "Define existing normalized Latin identities for relevance regression",
        )
    assert (subject.aliases[0] if as_alias else subject.normalized_name) == normalized(name)
    approved = profile_version(core_database, project_id, subject.id, communication_style="Brief")
    for story, expected in ((f"{name} arrives", {subject.id}), (unrelated, set())):
        with core_database.session() as session:
            selected = MemoryRepository(session).subjects_in_text(project_id, story)
        assert {value.id for value in selected} == expected, story
        request = ContextRequest(
            project_id=project_id,
            chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
            task_id=uuid4(),
            task_type="PLAN_CHAPTER",
            objective=story,
        )
        profile, batch = query(core_database, request, request.task_type)
        package = ContextEngine().build(request, profile, batch).package
        assert {value.character_id for value in package.items} == expected, story
        if expected:
            chosen = package.items[0]
            assert (chosen.source_id, chosen.logical_id, chosen.source_version) == (
                approved.id,
                approved.logical_id,
                1,
            )
            assert chosen.authority_level == Authority.A3_CANON and chosen.selected_reason


@pytest.mark.integration
@pytest.mark.parametrize("as_alias", [False, True], ids=["display", "alias"])
def test_normalized_multiword_latin_identity_boundaries(core_database, project_api, as_alias):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    with core_database.session() as session:
        subject = CharacterProfileService(session).create_character(
            project_id,
            "AliasTarget" if as_alias else "Red Fox",
            ["Red Fox"] if as_alias else [],
            actor(),
            "Preserve historical normalized identity forms within complete boundaries",
        )
    assert (subject.aliases[0] if as_alias else subject.normalized_name) == "redfox"
    positives = ("Red Fox", "Red-Fox", "Red.Fox", "Red_Fox", "RedFox")
    negatives = ("bredfoxes", "RedFoxes", "Red-Foxes", "Red\nFox", "Red\n\nFox")
    for story, expected in (
        *((value, {subject.id}) for value in positives),
        *((value, set()) for value in negatives),
    ):
        with core_database.session() as session:
            found = MemoryRepository(session).subjects_in_text(project_id, story)
        assert {value.id for value in found} == expected, story


@pytest.mark.integration
def test_latin_names_match_story_words_without_injecting_unrelated_profiles(
    core_database, core_client, project_api, chapter_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    subjects = {name: character(core_database, project_id, name) for name in "ABCDE"}
    exact = profile_version(
        core_database,
        project_id,
        subjects["A"].id,
        relationship_modifiers=[
            dict(other_character_id=str(subjects["B"].id), interaction_tendency="AB_ONLY"),
            dict(other_character_id=str(subjects["E"].id), interaction_tendency="AE_UNRELATED"),
        ],
    )
    for name in "BCDE":
        profile_version(core_database, project_id, subjects[name].id, communication_style=name)
    response = core_client.post(
        chapter_api + "/plans",
        json={
            "expected_version": 0,
            "objective": "A meets B",
            "required_outcome": "A leaves with B",
        },
    )
    assert response.status_code == 201
    assert (
        core_client.post(chapter_api + "/plans/approve", json={"expected_version": 1}).status_code
        == 200
    )
    request = ContextRequest(
        project_id=project_id,
        chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
        task_id=uuid4(),
        task_type="WRITE_CHAPTER",
        character_id=subjects["A"].id,
        approved_plan_version=1,
    )
    selected_profile, batch = query(core_database, request, request.task_type)
    package = ContextEngine().build(request, selected_profile, batch).package
    assert {value.character_id for value in package.items} == {subjects["A"].id, subjects["B"].id}
    selected = next(value for value in package.items if value.character_id == subjects["A"].id)
    assert (
        selected.source_id,
        selected.logical_id,
        selected.source_version,
        selected.authority_level,
    ) == (exact.id, exact.logical_id, 1, Authority.A3_CANON)
    assert selected.selected_reason
    assert selected.structured_payload["character_profile_hash"] == exact.profile_hash
    assert [
        value["interaction_tendency"]
        for value in selected.structured_payload["profile"]["relationship_modifiers"]
    ] == ["AB_ONLY"]
    assert len(exact.body["relationship_modifiers"]) == 2


@pytest.mark.integration
def test_name_and_alias_word_boundaries_preserve_cjk_and_multiword_lookup(
    core_database, project_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    names = ("A", "E", "Ann", "Mira", "Jun", "张三", "Ann Marie")
    subjects = {name: character(core_database, project_id, name) for name in names}
    with core_database.session() as session:
        alias = CharacterProfileService(session).create_character(
            project_id,
            "Atlas",
            ["AB", "Scout"],
            actor(),
            "Define exact aliases for boundary regression",
        )
    cases = (
        ("A meets B", {"A"}),
        ("A B", {"A", "Atlas"}),
        ("A.B", {"A", "Atlas"}),
        ("A\nB", {"A"}),
        ("AB", {"Atlas"}),
        ("Scout arrives", {"Atlas"}),
        ("scouting locations", set()),
        ("An annex and miracles", set()),
        ("Ann meets Mira", {"Ann", "Mira"}),
        ("mIrA, then Jun.", {"Mira", "Jun"}),
        ("张三与Jun交谈", {"张三", "Jun"}),
        ("Ann Marie joins 张三", {"Ann", "Ann Marie", "张三"}),
        ("Café and A1", set()),
        ("a_b", {"Atlas"}),
    )
    for story, expected in cases:
        with core_database.session() as session:
            found = MemoryRepository(session).subjects_in_text(project_id, story)
        assert {subject.name for subject in found} == expected, story
    with core_database.session() as session:
        explicit = MemoryRepository(session).subjects_in_text(
            project_id, "A miracle happens", explicit_ids=(subjects["E"].id,)
        )
        outside = MemoryRepository(session).subjects_in_text(
            uuid4(), "Mira meets AB", explicit_ids=(alias.id,)
        )
    assert {subject.name for subject in explicit} == {"A", "E"}
    assert outside == []


def sample(request):
    package = request.context_package
    profile = ContextProfileRegistry().resolve(package.profile_id, package.profile_version)
    assert package.estimated_tokens == TokenBudgetService().cost(
        package.request, profile, package.items
    )
    return dict(
        task=request.task_type,
        context_profile=f"{package.profile_id}.v{package.profile_version}",
        item_count=len(package.items),
        estimated_tokens=package.estimated_tokens,
        estimator="Utf8TokenEstimator (conservative UTF-8 bytes; not billing tokens)",
        package_hash=package.package_hash,
        sources=[
            dict(
                source_type=value.source_type,
                source_id=str(value.source_id),
                logical_id=str(value.logical_id),
                version=value.source_version,
                authority=value.authority_level,
                selected_reason=value.selected_reason,
                selector_id=value.selector_id,
            )
            for value in package.items
        ],
    )


@pytest.mark.integration
def test_five_character_overload_and_positive_negative_knowledge(
    revision_quality_driver, core_database
):
    first = revision_quality_driver
    initial = commit_initial(first, core_database)
    project = first.chapter_api.split("/chapters/")[0]
    project_id = UUID(project.rsplit("/", 1)[1])
    a_id, b_id = (UUID(initial[key]["subject_id"]) for key in ("a_state", "b_state"))
    second = QualityDriver(first.client, chapter(first.client, project, 2), "Mira meets Jun.")
    second.approve_plan(core_database)
    rows = [
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
        ),
        (
            "a_knows",
            "CHARACTER_KNOWLEDGE",
            "Mira",
            "CHARACTER",
            "knowledge_x",
            "RED",
            2,
            "Mira learned Vault Cipher has code RED, without Jun present.",
            {"known_fact_id": initial["x"]["id"]},
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
            {"known_fact_id": initial["y"]["id"]},
        ),
    ]
    prepare(second, core_database, candidates(rows), LATER)
    assert confirm(second, ["a_state", "a_knows", "b_knows"]).status_code == 200
    updated = {row["candidate_id"]: row for row in second.read("/memory")[0]["entries"]}
    extras = [character(core_database, project_id, name) for name in ("Noa", "Lia", "Rhea")]
    profiles = {}
    profiles[a_id] = profile_version(
        core_database,
        project_id,
        a_id,
        attention_bias="Very observant and actively investigates; grants no unknown facts",
        relationship_modifiers=[
            dict(other_character_id=str(b_id), interaction_tendency="AB_ONLY"),
            *[
                dict(other_character_id=str(other.id), interaction_tendency="UNRELATED_PAIR")
                for other in extras
            ],
        ],
    )
    profiles[b_id] = profile_version(
        core_database,
        project_id,
        b_id,
        attention_bias="Very observant and actively investigates; grants no unknown facts",
    )
    for other in extras:
        profile_version(
            core_database, project_id, other.id, communication_style="UNRELATED_PROFILE"
        )
    for identity in (a_id, b_id):
        profile_version(
            core_database,
            project_id,
            identity,
            1,
            approved=False,
            communication_style="UNAPPROVED_V2",
        )

    samples = []
    for sequence, owner, forbidden in ((3, "a", "b"), (4, "b", "a")):
        owner_id = a_id if owner == "a" else b_id

        def recorded(request, body, owner_id=owner_id):
            recorded_slice(request, body)
            if request.output_kind == "chapter_plan":
                body["result"]["pov_character_id"] = str(owner_id)

        provider = ExplorationProvider(transform=recorded)
        driver = Phase2Driver(first.client, chapter(first.client, project, sequence), True)
        for _ in range(4):
            run_one(core_database, driver, provider=provider)
        assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL"
        assert driver.decide().status_code == 200
        run_one(core_database, driver, provider=provider)
        writer = provider.requests[-1]
        assert writer.task_type == "WRITE_CHAPTER"
        package = writer.context_package
        assert package.request.character_id == owner_id
        selected = [
            value
            for value in package.items
            if value.selector_id == "approved-character-behavior-profiles"
        ]
        assert {value.character_id for value in selected} == {a_id, b_id}
        for value in selected:
            exact = profiles[value.character_id]
            assert (
                value.source_type,
                value.source_id,
                value.logical_id,
                value.source_version,
                value.authority_level,
            ) == (SourceType.EXTENSION, exact.id, exact.logical_id, 1, Authority.A3_CANON)
            assert value.selected_reason
            assert value.structured_payload["character_profile_hash"] == exact.profile_hash
        a_profile = next(value for value in selected if value.character_id == a_id)
        assert [
            value["interaction_tendency"]
            for value in a_profile.structured_payload["profile"]["relationship_modifiers"]
        ] == ["AB_ONLY"]
        rendered = json.dumps([value.structured_payload for value in package.items])
        assert all(
            marker not in rendered
            for marker in (
                "UNRELATED_PROFILE",
                "UNRELATED_PAIR",
                "UNAPPROVED_V2",
                REJECTED_SENTINEL,
            )
        )
        assert not any(value.source_type == SourceType.CHAPTER_VERSION for value in package.items)
        assert not any(value.selector_id == "selected-creative-concept" for value in package.items)
        included = {str(value.source_id) for value in committed_items(package)}
        expected = {
            updated[owner + "_knows"]["id"],
            (updated if owner == "a" else initial)[owner + "_state"]["id"],
            initial["x" if owner == "a" else "y"]["id"],
        }
        assert included == expected
        assert updated[forbidden + "_knows"]["id"] not in included
        assert initial["y" if owner == "a" else "x"]["id"] not in included
        assert initial["a_state"]["id"] not in included
        for request in provider.requests:
            samples.append(sample(request))
            memory = committed_items(request.context_package)
            if request.task_type in {"EXPLORE_CHAPTER_CONCEPTS", "PLAN_CHAPTER"}:
                known_x = next(
                    value for value in memory if str(value.source_id) == updated["a_knows"]["id"]
                )
                assert known_x.character_id == a_id
                assert known_x.structured_payload["epistemic_status"] == "KNOWS"
                assert not any(
                    value.character_id == b_id
                    and value.structured_payload.get("known_fact_id") == initial["x"]["id"]
                    for value in memory
                )
        assert driver.event("CANCEL").status_code == 200
    root = Path(".runtime/validation001")
    root.mkdir(parents=True, exist_ok=True)
    (root / "context-overload-samples.json").write_text(
        json.dumps(dict(result="PASS", mock_only=True, characters=5, samples=samples), indent=2)
    )


@pytest.mark.integration
def test_profile_v2_approval_stales_pending_explore_and_new_tasks_use_exact_v2(
    core_client, core_database, project_api, chapter_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a = character(core_database, project_id, "Mira")
    v1 = profile_version(core_database, project_id, a.id, communication_style="Brief")
    driver = ExplorationDriver(core_client, chapter_api, raw="Mira solves a bounded setback")
    run_one(core_database, driver, provider=ExplorationProvider())
    pending = next(value for value in driver.read("/agent-tasks") if value["status"] == "PENDING")
    assert pending["task_type"] == "EXPLORE_CHAPTER_CONCEPTS"
    v2 = profile_version(core_database, project_id, a.id, 1, communication_style="Detailed")
    provider = ExplorationProvider()
    run_one(core_database, driver, provider=provider)
    assert provider.requests == []
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    failed = next(
        value for value in driver.read("/agent-tasks") if value["task_id"] == pending["task_id"]
    )
    assert failed["last_error_code"] == "CONTEXT_STALE"
    assert driver.event("CANCEL").status_code == 200
    fresh = ExplorationDriver(
        core_client, chapter(core_client, project_api, 2), raw="Mira solves a bounded setback"
    )
    for _ in range(3):
        run_one(core_database, fresh, provider=provider)
    for request in provider.requests:
        if request.task_type not in {"EXPLORE_CHAPTER_CONCEPTS", "PLAN_CHAPTER"}:
            continue
        chosen = next(
            value
            for value in request.context_package.items
            if value.selector_id == "approved-character-behavior-profiles"
        )
        assert (chosen.source_id, chosen.logical_id, chosen.source_version) == (
            v2.id,
            v2.logical_id,
            2,
        )
        assert chosen.source_id != v1.id and chosen.selected_reason
        assert chosen.authority_level == Authority.A3_CANON
        assert chosen.structured_payload["profile"]["communication_style"] == "Detailed"


@pytest.mark.integration
def test_same_character_pair_inputs_change_without_dumping_other_modifiers(
    core_database, project_api, chapter_api
):
    project_id = UUID(project_api.rsplit("/", 1)[1])
    a, b, c = [character(core_database, project_id, name) for name in ("Mira", "Jun", "Noa")]
    profile_version(
        core_database,
        project_id,
        a.id,
        relationship_modifiers=[
            dict(other_character_id=str(b.id), interaction_tendency="AB"),
            dict(other_character_id=str(c.id), interaction_tendency="AC"),
        ],
    )
    packages = []
    for other, expected in ((b, "AB"), (c, "AC")):
        request = ContextRequest(
            project_id=project_id,
            task_id=uuid4(),
            chapter_id=UUID(chapter_api.rsplit("/", 1)[1]),
            task_type="PLAN_CHAPTER",
            objective=f"Mira meets {other.name}",
        )
        profile, batch = query(core_database, request, request.task_type)
        package = ContextEngine().build(request, profile, batch).package
        assert package.build_status == "READY"
        modifiers = package.items[0].structured_payload["profile"]["relationship_modifiers"]
        assert [value["interaction_tendency"] for value in modifiers] == [expected]
        packages.append(package)
    assert packages[0].items[0].payload_json != packages[1].items[0].payload_json


@pytest.mark.parametrize("higher", list(Authority)[1:7])
def test_a7_cannot_override_each_higher_authority(higher):
    request = ContextRequest(
        project_id=uuid4(), task_id=uuid4(), chapter_id=uuid4(), task_type="TEST_CONTEXT"
    )
    authoritative = item(request, authority_level=higher)
    from dataclasses import replace

    lower = replace(
        authoritative,
        source_id=uuid4(),
        context_item_id=uuid4(),
        authority_level=Authority.A7_AI_INFERENCE,
        payload_json='{"fact":"A7"}',
    )
    result = build(request, [lower, authoritative])
    assert result.status == "READY"
    assert result.package.items == (authoritative,)
    assert result.package.excluded_items[0].reason == "AUTHORITY_SUPERSEDED"
    if higher == Authority.A3_CANON:
        derived = replace(lower, authority_level=Authority.A6_DERIVED_MEMORY)
        canon = build(request, [derived, authoritative])
        assert canon.status == "READY" and canon.package.items == (authoritative,)
        assert canon.package.excluded_items[0].reason == "AUTHORITY_SUPERSEDED"
