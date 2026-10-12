"""Committed-memory selection through real Planning and Writing context builds.

Accepted source fixtures are prepared through the Memory API. These focused
integration tests complement the five-chapter Writing acceptance; they do not
claim that fixture prose was produced by a real model.
"""

from copy import deepcopy
from uuid import UUID

from tests.context.test_character_profile_context import profile_version
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_memory_commit import confirm, prepare
from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import chapter

INITIAL = (
    "Mira stood at Harbor. Jun waited at Pier.\n\n"
    "Vault Cipher has code RED. Mira read Vault Cipher alone.\n\n"
    "River Password has code BLUE. Jun read River Password alone.\n\n"
    "Courier remains missing and its thread is OPEN.\n\n"
    "Atlas remains missing and its separate thread is OPEN."
)
LATER = (
    "Mira moved from Harbor to Hill. Jun stayed at Pier.\n\n"
    "Mira learned Vault Cipher has code RED, without Jun present.\n\n"
    "Jun learned River Password has code BLUE, without Mira present."
)


def candidates(specifications):
    def transform(_, body):
        base = deepcopy(body["result"]["candidates"][0])
        rows = []
        for (
            identifier,
            kind,
            name,
            subject_kind,
            slot,
            value,
            paragraph,
            quote,
            extra,
        ) in specifications:
            derived = kind == "OPEN_THREAD"
            row = {
                **deepcopy(base),
                "id": identifier,
                "candidate_type": kind,
                "subject_ref": {
                    "name": name,
                    "kind": subject_kind,
                    "logical_id": None,
                    "aliases": [],
                    "resolution": "NEW",
                },
                "statement": quote,
                "slot": slot,
                "value": value,
                "state_before": None,
                "state_after": value if kind != "CANON_FACT" else None,
                "epistemic_status": "KNOWS" if kind == "CHARACTER_KNOWLEDGE" else None,
                "importance": "DERIVED_HINT" if derived else "CONTINUITY",
                "target_layer": "DERIVED" if derived else "CANON",
                "known_fact_id": None,
                "evidence": [
                    {
                        "paragraph_index": paragraph,
                        "short_excerpt": quote,
                        "reason": "Explicit persistent continuity fact in the accepted source.",
                    }
                ],
                **extra,
            }
            rows.append(row)
        body["result"]["candidates"] = rows

    return transform


def initial_candidates():
    return candidates(
        [
            (
                "a_state",
                "CHARACTER_STATE",
                "Mira",
                "CHARACTER",
                "location",
                "Harbor",
                1,
                "Mira stood at Harbor.",
                {},
            ),
            (
                "b_state",
                "CHARACTER_STATE",
                "Jun",
                "CHARACTER",
                "location",
                "Pier",
                1,
                "Jun waited at Pier.",
                {},
            ),
            (
                "x",
                "CANON_FACT",
                "Vault Cipher",
                "EVENT",
                "code",
                "RED",
                2,
                "Vault Cipher has code RED.",
                {},
            ),
            (
                "y",
                "CANON_FACT",
                "River Password",
                "EVENT",
                "code",
                "BLUE",
                3,
                "River Password has code BLUE.",
                {},
            ),
            (
                "thread",
                "OPEN_THREAD",
                "Courier",
                "EVENT",
                "status",
                "OPEN",
                4,
                "Courier remains missing and its thread is OPEN.",
                {},
            ),
            (
                "unrelated",
                "OPEN_THREAD",
                "Atlas",
                "EVENT",
                "status",
                "OPEN",
                5,
                "Atlas remains missing and its separate thread is OPEN.",
                {},
            ),
        ]
    )


def commit_initial(driver, database):
    prepare(driver, database, initial_candidates(), INITIAL)
    proposal = driver.read("/memory")[0]["proposal"]
    assert {row["conflict_status"] for row in proposal["candidates"]} == {"NONE"}, proposal
    response = confirm(driver, ["a_state", "b_state", "x", "y", "thread", "unrelated"])
    assert response.status_code == 200, response.text
    return {row["candidate_id"]: row for row in driver.read("/memory")[0]["entries"]}


def committed_items(package):
    return [item for item in package.items if item.selector_id == "committed-memory"]


def test_writer_current_state_and_linked_canon_follow_two_real_knowledge_owners(
    revision_quality_driver, core_database
):
    first = revision_quality_driver
    initial = commit_initial(first, core_database)
    project = first.chapter_api.split("/chapters/")[0]
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
    response = confirm(second, ["a_state", "a_knows", "b_knows"])
    assert response.status_code == 200, response.text
    updated = {row["candidate_id"]: row for row in second.read("/memory")[0]["entries"]}
    assert updated["a_state"]["supersedes_id"] == initial["a_state"]["id"]
    # Exercise both approved behavior and knowledge in one real Writer call.
    # A newer unapproved preference must not replace the approved profile.
    project_id = UUID(first.workflow["project_id"])
    approved = profile_version(
        core_database,
        project_id,
        UUID(initial["a_state"]["subject_id"]),
        communication_style="APPROVED_MIRA_VOICE: answers directly without revealing secrets",
    )
    profile_version(
        core_database,
        project_id,
        approved.character_id,
        1,
        approved=False,
        communication_style="UNAPPROVED_MIRA_VOICE_MUST_STAY_OUT",
    )
    # Commit a later chapter first. Its successor must neither hide the state
    # effective before the Writer's chapter nor enter the actual model input.
    future = QualityDriver(first.client, chapter(first.client, project, 5), "Mira moves onward.")
    future.approve_plan(core_database)
    prepare(
        future,
        core_database,
        candidates(
            [
                (
                    "future_state",
                    "CHARACTER_STATE",
                    "Mira",
                    "CHARACTER",
                    "location",
                    "FUTURE_LOCATION_MUST_STAY_OUT",
                    1,
                    "Mira moved from Hill to FUTURE_LOCATION_MUST_STAY_OUT.",
                    {"state_before": "Hill"},
                )
            ]
        ),
        "Mira moved from Hill to FUTURE_LOCATION_MUST_STAY_OUT.",
    )
    response = confirm(future, ["future_state"])
    assert response.status_code == 200, response.text
    future_entry = future.read("/memory")[0]["entries"][0]
    assert future_entry["supersedes_id"] == updated["a_state"]["id"]
    for sequence, owner, forbidden in [(3, "a", "b"), (4, "b", "a")]:
        owner_id = initial[owner + "_state"]["subject_id"]

        def bind_pov(request, body, owner_id=owner_id):
            if request.output_kind == "chapter_plan":
                body["result"]["pov_character_id"] = owner_id

        provider = RecordedProvider(bind_pov)
        driver = QualityDriver(
            first.client, chapter(first.client, project, sequence), "Mira meets Jun near Courier."
        )
        for _ in range(3):
            run_one(core_database, driver, provider=provider)
        assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL", driver.workflow
        assert driver.decide().status_code == 200
        run_one(core_database, driver, provider=provider)
        package = provider.requests[-1].context_package
        assert package.request.character_id == UUID(owner_id)
        memory = committed_items(package)
        included = {str(item.source_id) for item in memory}
        expected = {
            updated[owner + "_knows"]["id"],
            (updated if owner == "a" else initial)[owner + "_state"]["id"],
            initial["x" if owner == "a" else "y"]["id"],
        }
        assert included == expected
        assert initial["a_state"]["id"] not in included
        assert updated[forbidden + "_knows"]["id"] not in included
        assert initial["y" if owner == "a" else "x"]["id"] not in included
        assert future_entry["id"] not in included
        profiles = [
            item
            for item in package.items
            if item.selector_id == "approved-character-behavior-profiles"
        ]
        assert len(profiles) == 1
        selected_profile = profiles[0]
        assert selected_profile.source_id == approved.id
        assert selected_profile.source_version == approved.version == 1
        assert (
            selected_profile.structured_payload["character_profile_hash"] == approved.profile_hash
        )
        # Assert final compiled context, not only repository recall or a side snapshot.
        context_message = next(
            message.content
            for message in provider.requests[-1].prompt.messages
            if message.layer == "CONTEXT_DATA"
        )
        assert "APPROVED_MIRA_VOICE" in context_message
        assert all(identity in context_message for identity in expected)
        for excluded in (
            "UNAPPROVED_MIRA_VOICE_MUST_STAY_OUT",
            "FUTURE_LOCATION_MUST_STAY_OUT",
            updated[forbidden + "_knows"]["id"],
            initial["y" if owner == "a" else "x"]["id"],
        ):
            assert excluded not in context_message
        knowledge = next(
            item
            for item in memory
            if item.structured_payload["memory_type"] == "CHARACTER_KNOWLEDGE"
        )
        assert knowledge.character_id == UUID(owner_id)
        assert knowledge.knowledge_scope == "CHARACTER_KNOWLEDGE"
        assert knowledge.structured_payload["epistemic_status"] == "KNOWS"
        assert knowledge.structured_payload["subject_id"] == owner_id
        assert (
            knowledge.structured_payload["known_fact_id"]
            == initial["x" if owner == "a" else "y"]["id"]
        )
        assert driver.event("CANCEL").status_code == 200


def test_uncommitted_proposal_is_absent_from_an_actual_planning_context(
    revision_quality_driver, core_database
):
    first = revision_quality_driver
    prepare(first, core_database, initial_candidates(), INITIAL)
    assert first.read("/memory")[0]["status"] == "PROPOSED"
    project = first.chapter_api.split("/chapters/")[0]
    other = PlanningDriver(
        first.client, chapter(first.client, project, 2), "Mira meets Jun near Courier and Atlas."
    )
    provider = RecordedProvider()
    run_one(core_database, other, provider=provider)
    run_one(core_database, other, provider=provider)
    package = provider.requests[-1].context_package
    assert package.request.task_type == "PLAN_CHAPTER"
    assert committed_items(package) == []
    assert not any(item.selector_id == "memory-subjects" for item in package.items)


def test_planning_gets_relevant_open_thread_without_all_project_memory(
    revision_quality_driver, core_database
):
    first = revision_quality_driver
    initial = commit_initial(first, core_database)
    project = first.chapter_api.split("/chapters/")[0]
    other = PlanningDriver(
        first.client, chapter(first.client, project, 2), "Mira searches for Courier."
    )
    provider = RecordedProvider()
    run_one(core_database, other, provider=provider)
    run_one(core_database, other, provider=provider)
    package = provider.requests[-1].context_package
    memory = committed_items(package)
    assert {str(item.source_id) for item in memory} == {
        initial["a_state"]["id"],
        initial["thread"]["id"],
    }
    thread = next(item for item in memory if str(item.source_id) == initial["thread"]["id"])
    assert thread.logical_id == UUID(initial["thread"]["logical_id"])
    assert thread.structured_payload["value"] == "OPEN"
    assert thread.structured_payload["role"] == "DERIVED_HINT"
    assert thread.authority_level == "A6_DERIVED_MEMORY"
    assert initial["unrelated"]["id"] not in {str(item.source_id) for item in memory}
    assert initial["b_state"]["id"] not in {str(item.source_id) for item in memory}
