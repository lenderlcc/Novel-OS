"""Object and open-thread continuity through accepted chapters and human memory gates."""

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.memory import MemoryRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.memory_commit import MemoryCommitService
from tests.core.quality.test_memory_commit import confirm, next_chapter, prepare

INITIAL = (
    "Mira set Object K on the table. Object K was INTACT.\n\n"
    "Open Thread T remained OPEN: the courier had not returned."
)
CHANGED = (
    "Mira watched Object K burn. Object K changed from INTACT to DESTROYED.\n\n"
    "Open Thread T remained OPEN: Mira found the courier's broken seal."
)
THREAD_INITIAL = "The courier has not returned; Open Thread T remains OPEN."
THREAD_CHANGED = "Mira found the courier's broken seal; Open Thread T remains OPEN."


def continuity_candidates(*, changed=False, object_marker=True, before="INTACT"):
    def transform(_, body):
        rows = {row["id"]: row for row in body["result"]["candidates"]}
        fact, thread = rows["fact"], rows["thread"]
        value = "DESTROYED" if changed else "INTACT"
        fact.update(
            statement=f"Object K is {value}.",
            value=value,
            state_before=before if changed else None,
            state_after=value if object_marker else None,
        )
        fact["subject_ref"].update(name="Object K", kind="OBJECT")
        fact["evidence"] = [
            dict(
                paragraph_index=1,
                short_excerpt=(
                    "Object K changed from INTACT to DESTROYED."
                    if changed
                    else "Object K was INTACT."
                ),
                reason="Explicit object condition in the accepted source.",
            )
        ]
        thread.update(
            statement=THREAD_CHANGED if changed else THREAD_INITIAL,
            value="OPEN",
            state_before="OPEN" if changed else None,
            state_after="OPEN",
        )
        thread["subject_ref"].update(name="Open Thread T", kind="EVENT")
        thread["evidence"] = [
            dict(
                paragraph_index=2,
                short_excerpt=(
                    "Mira found the courier's broken seal."
                    if changed
                    else "the courier had not returned."
                ),
                reason="Unresolved thread and new evidence in the accepted source.",
            )
        ]
        body["result"]["candidates"] = [fact, thread]

    return transform


def first_commit(d, db, *, object_marker=True):
    prepare(d, db, continuity_candidates(object_marker=object_marker), INITIAL)
    response = confirm(d, ["fact", "thread"])
    assert response.status_code == 200, response.text
    return {entry["candidate_id"]: entry for entry in d.read("/memory")[0]["entries"]}


def assert_no_partial_commit(d, db, original):
    d.refresh()
    assert d.workflow["current_state"] == "C15_MEMORY_COMMIT"
    assert d.client.get(d.chapter_api).json()["status"] != "COMPLETED"
    assert d.read("/memory")[0]["batch"] is None
    with db.session() as session:
        assert session.execute(text("SELECT count(*) FROM memory_commit_batches")).scalar() == 1
        assert session.execute(text("SELECT count(*) FROM committed_memory")).scalar() == 2
        entries = MemoryRepository(session).entries(UUID(d.creation["project_id"]))
        assert {str(entry.id) for entry in entries} == {entry["id"] for entry in original.values()}


def test_object_and_thread_keep_identity_history_and_survive_an_omitted_chapter(
    revision_quality_driver, core_database, migration_config
):
    d = revision_quality_driver
    original = first_commit(d, core_database)
    other = next_chapter(d, core_database, 2)
    draft = prepare(other, core_database, continuity_candidates(changed=True), CHANGED)
    proposal = other.read("/memory")[0]["proposal"]
    task = next(
        task for task in other.read("/agent-tasks") if task["task_type"] == "EXTRACT_CHAPTER_MEMORY"
    )
    assert task["expected_output_schema"] == "chapter-memory-result.v2"
    with core_database.session() as session:
        lineage = PromptLineageRepository(session).for_run(UUID(proposal["agent_run_id"]))
        assert str(lineage.lineage_id) == proposal["prompt_lineage_id"]
        assert lineage.output_schema_version == 2
        assert lineage.task_template["module_id"] == "extract-chapter-memory"
        assert lineage.task_template["version"] == 3
        package = ContextPackageRepository(session).for_run(UUID(proposal["agent_run_id"]))
        assert str(package.context_package_id) == proposal["context_package_id"]
        previous = {
            item.structured_payload["memory_type"]: item
            for item in package.items
            if item.provenance and item.provenance[0] == "committed_memory"
        }
        assert previous["CANON_FACT"].structured_payload["value"] == "INTACT"
        assert previous["CANON_FACT"].structured_payload["state_after"] == "INTACT"
        assert str(previous["CANON_FACT"].source_id) == original["fact"]["id"]
        assert previous["OPEN_THREAD"].structured_payload["state_after"] == "OPEN"
        assert str(previous["OPEN_THREAD"].source_id) == original["thread"]["id"]
    assert [row["conflict_status"] for row in proposal["candidates"]] == [
        "STATE_TRANSITION",
        "STATE_TRANSITION",
    ]
    response = confirm(other, ["fact", "thread"])
    assert response.status_code == 200, response.text
    updated = {entry["candidate_id"]: entry for entry in other.read("/memory")[0]["entries"]}
    for candidate_id in ["fact", "thread"]:
        before, after = original[candidate_id], updated[candidate_id]
        assert after["logical_id"] == before["logical_id"]
        assert after["subject_id"] == before["subject_id"]
        assert after["version"] == 2 and after["supersedes_id"] == before["id"]
        assert after["chapter_version_id"] == draft["id"]
    assert updated["fact"]["value"] == "DESTROYED"
    assert updated["fact"]["authority_level"] == "A3_CANON"
    assert updated["thread"]["value"] == "OPEN"
    assert updated["thread"]["statement"] == THREAD_CHANGED
    assert updated["thread"]["authority_level"] == "A6_DERIVED_MEMORY"
    assert d.read("/memory")[0]["entries"] == list(original.values())

    later = next_chapter(other, core_database, 3)

    def omit_memory(_, body):
        body["result"]["candidates"] = []

    prepare(later, core_database, omit_memory, "Mira crossed the square without incident.")
    response = confirm(later, [])
    assert response.status_code == 200, response.text
    with core_database.session() as session:
        repo = MemoryRepository(session)
        project_id = UUID(d.creation["project_id"])
        current = {entry.memory_type: entry for entry in repo.entries(project_id)}
        assert current["CANON_FACT"].value == "DESTROYED"
        assert str(current["OPEN_THREAD"].id) == updated["thread"]["id"]
        assert current["OPEN_THREAD"].value == "OPEN"
        assert len(repo.entries(project_id, historical=True)) == 4
        past = repo.entries(project_id, types=["CANON_FACT"], before_sequence=2)
        assert len(past) == 1 and past[0].value == "INTACT"
        for entry in original.values():
            with pytest.raises(IntegrityError), session.begin_nested():
                session.execute(
                    text("UPDATE committed_memory SET statement='overwrite' WHERE id=:id"),
                    {"id": UUID(entry["id"])},
                )
    with (
        pytest.raises(DBAPIError, match="Export object/thread transition history before downgrade"),
        core_database.engine.begin() as connection,
    ):
        migration_config.attributes["connection"] = connection
        # Keep exercising 0017's export guard after newer migrations are added.
        command.downgrade(migration_config, "0016_memory_commit")
    with core_database.session() as session:
        assert session.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
            "0022_feedback_before_review"
        )
        assert session.execute(text("SELECT count(*) FROM committed_memory")).scalar() == 4


def test_unchanged_memory_is_skipped_even_with_new_chapter_evidence(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    original = first_commit(d, core_database)
    other = next_chapter(d, core_database, 2)
    prepare(other, core_database, continuity_candidates(), INITIAL)
    candidates = other.read("/memory")[0]["proposal"]["candidates"]
    assert [row["conflict_status"] for row in candidates] == ["DUPLICATE", "DUPLICATE"]
    response = confirm(other, ["fact", "thread"])
    assert response.status_code == 200, response.text
    history = other.read("/memory")[0]
    assert history["entries"] == []
    assert set(history["batch"]["skipped_candidate_ids"]) == {"fact", "thread"}
    with core_database.session() as session:
        entries = MemoryRepository(session).entries(UUID(d.creation["project_id"]))
        assert {str(entry.id) for entry in entries} == {entry["id"] for entry in original.values()}
        assert all(entry.version == 1 for entry in entries)


@pytest.mark.parametrize("invalid", ["static_canon", "missing_before", "wrong_before"])
def test_object_change_cannot_replace_static_canon_or_an_unmatched_state(
    revision_quality_driver, core_database, invalid
):
    d = revision_quality_driver
    original = first_commit(d, core_database, object_marker=invalid != "static_canon")
    other = next_chapter(d, core_database, 2)
    before = (
        None if invalid == "missing_before" else "OTHER" if invalid == "wrong_before" else "INTACT"
    )
    prepare(other, core_database, continuity_candidates(changed=True, before=before), CHANGED)
    candidates = other.read("/memory")[0]["proposal"]["candidates"]
    assert candidates[0]["conflict_status"] == "CONTRADICTION"
    assert candidates[1]["conflict_status"] == "STATE_TRANSITION"
    response = confirm(other, ["thread", "fact"])
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "CONTEXT_AUTHORITY_CONFLICT"
    assert_no_partial_commit(other, core_database, original)


def test_thread_description_change_needs_the_confirmed_prior_state(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    original = first_commit(d, core_database)
    other = next_chapter(d, core_database, 2)

    def missing_thread_before(request, body):
        continuity_candidates(changed=True)(request, body)
        body["result"]["candidates"][1]["state_before"] = None

    prepare(other, core_database, missing_thread_before, CHANGED)
    candidates = other.read("/memory")[0]["proposal"]["candidates"]
    assert candidates[1]["conflict_status"] == "CONTRADICTION"
    response = confirm(other, ["fact", "thread"])
    assert response.status_code == 409, response.text
    assert_no_partial_commit(other, core_database, original)


def test_object_state_transition_cannot_override_a_locked_decision(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    original = first_commit(d, core_database)
    project = d.chapter_api.split("/chapters/")[0]
    response = d.client.post(
        project + "/decisions",
        json={"question": "Object K continuity?", "decision": "Object K must remain INTACT."},
    )
    assert response.status_code == 201, response.text
    decision = response.json()
    decision_path = project + "/decisions/" + decision["logical_id"]
    response = d.client.post(decision_path + "/approve", json={"expected_version": 1})
    assert response.status_code == 200, response.text
    response = d.client.post(
        project + "/locks",
        json={
            "target_type": "DECISION",
            "target_id": decision["logical_id"],
            "expected_version": 1,
            "reason": "Keep the object's approved condition.",
        },
    )
    assert response.status_code == 201, response.text
    other = next_chapter(d, core_database, 2)

    def conflict_with_lock(request, body):
        continuity_candidates(changed=True)(request, body)
        checks = body["result"]["candidates"][0]["authority_checks"]
        check = next(
            row for row in checks if row["source_ref"]["logical_id"] == decision["logical_id"]
        )
        check.update(outcome="CONFLICT", reason="Destruction violates the locked condition.")

    prepare(other, core_database, conflict_with_lock, CHANGED)
    candidates = other.read("/memory")[0]["proposal"]["candidates"]
    assert candidates[0]["conflict_status"] == "AUTHORITY_CONFLICT"
    response = confirm(other, ["thread", "fact"])
    assert response.status_code == 409, response.text
    assert_no_partial_commit(other, core_database, original)
    assert d.client.get(decision_path).json()["locked"] is True


@pytest.mark.parametrize("candidate_id", ["fact", "thread"])
def test_database_rejects_a_false_transition_even_if_the_normalizer_misclassifies_it(
    revision_quality_driver, core_database, monkeypatch, candidate_id
):
    d = revision_quality_driver
    original = first_commit(d, core_database)
    other = next_chapter(d, core_database, 2)
    normalize = MemoryCommitService.normalize
    add = MemoryRepository.add
    violations = []

    def misclassify(self, *args):
        rows = normalize(self, *args)
        for row in rows:
            if row["id"] == candidate_id:
                row["conflict_status"] = "STATE_TRANSITION"
        return rows

    def capture_constraint(self, record):
        try:
            return add(self, record)
        except IntegrityError as error:
            violations.append(str(error.orig))
            raise

    monkeypatch.setattr(MemoryCommitService, "normalize", misclassify)
    monkeypatch.setattr(MemoryRepository, "add", capture_constraint)

    def missing_before(request, body):
        continuity_candidates(changed=True)(request, body)
        row = next(row for row in body["result"]["candidates"] if row["id"] == candidate_id)
        row["state_before"] = None

    prepare(other, core_database, missing_before, CHANGED)
    response = confirm(other, [candidate_id])
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    assert violations and "Memory supersession is invalid" in violations[0]
    assert_no_partial_commit(other, core_database, original)
