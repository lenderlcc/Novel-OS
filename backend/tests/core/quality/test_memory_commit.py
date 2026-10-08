from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import ContextRequest
from novel_os.domain.memory import CommittedMemory
from novel_os.repositories.memory import MemoryRepository
from novel_os.services.canon_context import CanonContextReader
from tests.core.quality.conftest import QualityDriver
from tests.core.quality.test_revision import finish_review
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def complete_request(d):
    draft = d.client.get(d.chapter_api + f"/versions/{d.workflow['draft_version']}").json()
    response = d.client.post(
        d.url + "/completion",
        json={
            "event_id": str(uuid4()),
            "expected_state_version": d.workflow["state_version"],
            "chapter_version_id": draft["id"],
        },
    )
    assert response.status_code == 200, response.text
    d.refresh()
    return draft


def test_empty_memory_full_slice(revision_quality_driver, core_database):
    d = revision_quality_driver
    d.client._transport.raise_server_exceptions = True
    finish_review(d, core_database, "SUCCESS")
    draft = complete_request(d)
    assert d.workflow["current_state"] == "C14_MEMORY_PREPARATION"
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C15_MEMORY_COMMIT", d.workflow
    h = d.read("/memory")[0]
    assert h["status"] == "PROPOSED" and h["proposal"]["candidates"] == []
    assert h["request"]["chapter_version_id"] == draft["id"]
    response = d.client.post(
        d.url + "/memory/confirm",
        json={
            "event_id": str(uuid4()),
            "expected_state_version": d.workflow["state_version"],
            "proposal_id": h["proposal"]["id"],
            "selected_candidate_ids": [],
        },
    )
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["current_state"] == "C16_COMPLETED"
    assert d.client.get(d.chapter_api).json()["status"] == "COMPLETED"
    assert d.read("/memory")[0]["status"] == "COMMITTED"


STORY = (
    "Mira reached Harbor after leaving Hill. The map was destroyed in the fire.\n\n"
    "Mira learned that the vault is under the tower. Jun was absent and did not hear this.\n\n"
    "Mira suspects that the captain is hiding a key.\n\n"
    "Mira and Jun agreed to work together. The missing courier has not been found."
)


def install_draft(d, content=STORY):
    response = d.client.post(
        d.chapter_api + "/versions",
        json={
            "content": content,
            "change_reason": "Accepted source fixture",
            "expected_version": d.client.get(d.chapter_api).json()["current_version"] or 0,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def fixture_candidates(request, body):
    package = request.context_package
    source = next(i for i in package.items if i.selector_id == "target-version")
    checks = [
        dict(
            source_ref=dict(
                source_type=i.source_type, logical_id=str(i.logical_id), version=i.source_version
            ),
            outcome="COMPATIBLE",
            reason="No conflict with this boundary.",
        )
        for i in package.items
        if (
            i.source_type in {"REQUIREMENT", "DECISION", "CHAPTER_PLAN", "CHAPTER_VERSION"}
            and i.source_id != source.source_id
            and (i.locked or i.authority_level.value <= "A4_APPROVED_PLAN")
        )
        or (
            i.source_type == "EXTENSION"
            and i.provenance[0] == "committed_memory"
            and i.authority_level.value == "A3_CANON"
        )
    ]

    def row(id, kind, name, subject_kind, statement, slot, value, quote, index=1):
        derived = kind in {"OPEN_THREAD", "DERIVED_CHAPTER_SUMMARY"}
        return dict(
            id=id,
            candidate_type=kind,
            subject_ref=dict(
                name=name, kind=subject_kind, logical_id=None, aliases=[], resolution="NEW"
            )
            if name
            else None,
            statement=statement,
            slot=slot,
            value=value,
            state_before=None,
            state_after=value
            if kind in {"CHARACTER_STATE", "CHARACTER_KNOWLEDGE", "RELATIONSHIP_STATE"}
            else None,
            epistemic_status=None,
            importance="DERIVED_HINT" if derived else "CONTINUITY",
            evidence=[
                dict(
                    paragraph_index=index, short_excerpt=quote, reason="Future continuity evidence."
                )
            ],
            target_layer="DERIVED" if derived else "CANON",
            source_refs=[
                dict(
                    source_type="CHAPTER_VERSION",
                    logical_id=str(source.logical_id),
                    version=source.source_version,
                )
            ],
            confidence=0.9,
            existing_entry_id=None,
            authority_checks=deepcopy(checks),
            uncertainty=None,
        )

    rows = [
        row(
            "state",
            "CHARACTER_STATE",
            "Mira",
            "CHARACTER",
            "Mira is in Harbor.",
            "location",
            "Harbor",
            "Mira reached Harbor",
        ),
        row(
            "fact",
            "CANON_FACT",
            "map",
            "OBJECT",
            "The map is destroyed.",
            "condition",
            "destroyed",
            "The map was destroyed in the fire.",
        ),
        row(
            "knowledge",
            "CHARACTER_KNOWLEDGE",
            "Mira",
            "CHARACTER",
            "Mira knows the vault location.",
            "knowledge:vault",
            "under the tower",
            "Mira learned that the vault is under the tower.",
            2,
        ),
        row(
            "belief",
            "CHARACTER_KNOWLEDGE",
            "Mira",
            "CHARACTER",
            "Mira suspects the captain hides a key.",
            "knowledge:key",
            "captain has key",
            "Mira suspects that the captain is hiding a key.",
            3,
        ),
        row(
            "relationship",
            "RELATIONSHIP_STATE",
            "Mira",
            "CHARACTER",
            "Mira and Jun will cooperate.",
            "relationship:Jun",
            "cooperating",
            "Mira and Jun agreed to work together.",
            4,
        ),
        row(
            "thread",
            "OPEN_THREAD",
            "courier",
            "CHARACTER",
            "The courier is still missing.",
            "search",
            "missing",
            "The missing courier has not been found.",
            4,
        ),
        row(
            "summary",
            "DERIVED_CHAPTER_SUMMARY",
            None,
            None,
            "Mira reaches Harbor and learns a location; the courier remains missing.",
            "summary",
            "Harbor chapter",
            "Mira reached Harbor",
        ),
    ]
    rows[2]["epistemic_status"] = "KNOWS"
    rows[3]["epistemic_status"] = "SUSPECTS"
    body["result"]["candidates"] = rows


def prepare(d, db, transform=None, content=STORY):
    finish_review(d, db, "SUCCESS")
    draft = install_draft(d, content)
    d.refresh()
    response = d.client.post(
        d.url + "/completion",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            chapter_version_id=draft["id"],
        ),
    )
    assert response.status_code == 200, response.text
    d.refresh()

    def generated(request, body):
        fixture_candidates(request, body)
        if transform:
            transform(request, body)

    run_one(db, d, provider=RecordedProvider(generated))
    return draft


def confirm(d, ids):
    proposal = d.read("/memory")[0]["proposal"]
    return d.client.post(
        d.url + "/memory/confirm",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            proposal_id=proposal["id"],
            selected_candidate_ids=ids,
        ),
    )


def test_selected_commit_lineage_immutable_and_completed_mutation_guards(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    d.client._transport.raise_server_exceptions = True
    draft = prepare(d, core_database)
    h = d.read("/memory")[0]
    assert h["status"] == "PROPOSED", h
    assert d.client.get(d.chapter_api.split("/chapters/")[0] + "/memory").json() == []
    ids = ["state", "fact", "knowledge", "belief", "relationship", "thread", "summary"]
    result = confirm(d, ids)
    assert result.status_code == 200, result.text
    d.refresh()
    h = d.read("/memory")[0]
    assert h["batch"]["selected_candidate_ids"] == ids
    assert len(h["entries"]) == 7 and {e["chapter_version_id"] for e in h["entries"]} == {
        draft["id"]
    }
    assert (
        h["proposal"]["agent_run_id"]
        and h["proposal"]["prompt_lineage_id"]
        and h["proposal"]["context_package_id"]
    )
    for table in [
        "memory_requests",
        "memory_commit_proposals",
        "memory_commit_batches",
        "memory_subjects",
        "committed_memory",
    ]:
        with core_database.session() as s, pytest.raises(IntegrityError), s.begin():
            s.execute(text(f"DELETE FROM {table}"))
    response = d.client.post(
        d.chapter_api + "/versions",
        json=dict(content="changed", change_reason="bad", expected_version=2),
    )
    assert response.status_code == 409, response.text
    response = d.client.post(
        d.url + "/feedback",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            source_chapter_version_id=draft["id"],
            raw_feedback="Change prose",
        ),
    )
    assert response.status_code == 409
    with core_database.session() as s:
        assert (
            s.execute(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE schemaname=current_schema() "
                    "AND indexname='ix_memory_fts'"
                )
            ).scalar()
            == 1
        )
        entries = MemoryRepository(s).entries(UUID(d.creation["project_id"]))
        owner = next(e.subject_id for e in entries if e.memory_type == "CHARACTER_KNOWLEDGE")
        profile = ContextProfileRegistry().for_task("WRITE_CHAPTER")
        selector = next(v for v in profile.selectors if v.selector_id == "committed-memory")
        req = ContextRequest(
            project_id=UUID(d.creation["project_id"]),
            task_id=uuid4(),
            task_type="WRITE_CHAPTER",
            chapter_id=uuid4(),
            chapter_sequence=2,
            objective="Mira",
            character_id=owner,
        )
        items, _ = CanonContextReader(s).query(req, selector)
        assert any(i.structured_payload["epistemic_status"] == "SUSPECTS" for i in items)
        assert not any(i.structured_payload["memory_type"] == "CANON_FACT" for i in items)
        assert CanonContextReader(s).query(replace(req, character_id=uuid4()), selector)[0] == ()
        assert CanonContextReader(s).query(replace(req, character_id=None), selector)[0] == ()
        planning = ContextProfileRegistry().resolve("CP-004", 6)
        ps = next(v for v in planning.selectors if v.selector_id == "committed-memory")
        found, _ = CanonContextReader(s).query(
            replace(req, task_type="PLAN_CHAPTER", objective="Mira examines map"), ps
        )
        assert any(i.structured_payload["memory_type"] == "CANON_FACT" for i in found)
        identity = next(v for v in planning.selectors if v.selector_id == "memory-subjects")
        assert CanonContextReader(s).query(replace(req, task_type="PLAN_CHAPTER"), identity)[0]


@pytest.mark.parametrize(
    "failure", ["bad_quote", "plan_source", "missing_boundary", "fake_authority", "known_fact"]
)
def test_invalid_extraction_fails_before_proposal(revision_quality_driver, core_database, failure):
    def change(_, body):
        row = body["result"]["candidates"][0]
        if failure == "bad_quote":
            row["evidence"][0]["short_excerpt"] = "Mira is definitely courageous."
        if failure == "plan_source":
            row["source_refs"][0]["source_type"] = "CHAPTER_PLAN"
        if failure == "missing_boundary":
            row["authority_checks"] = []
        if failure == "fake_authority":
            row["authority_level"] = "A1_USER_LOCKED"
        if failure == "known_fact":
            row["known_fact_id"] = str(uuid4())

    d = revision_quality_driver
    prepare(d, core_database, change)
    assert d.workflow["current_state"] != "C15_MEMORY_COMMIT"
    assert d.read("/memory")[0]["proposal"] is None
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "EXTRACT_CHAPTER_MEMORY")
    assert task["last_error_code"] == "SCHEMA_PARSE_ERROR"


@pytest.mark.parametrize("kind", ["CONFLICT", "UNCERTAIN"])
def test_selected_conflicts_block_and_excluding_them_preserves_memory(
    revision_quality_driver, core_database, kind
):
    def change(_, body):
        body["result"]["candidates"][0]["authority_checks"][0]["outcome"] = kind

    d = revision_quality_driver
    prepare(d, core_database, change)
    h = d.read("/memory")[0]
    assert h["proposal"] is not None, h
    assert h["proposal"]["candidates"][0]["conflict_status"] in {"AUTHORITY_CONFLICT", "AMBIGUOUS"}
    response = confirm(d, ["state"])
    assert response.status_code == 409, response.text
    assert d.client.get(d.chapter_api).json()["status"] != "COMPLETED"
    assert confirm(d, ["fact"]).status_code == 200


@pytest.mark.parametrize("blocked_by", ["confidence", "uncertainty", "authority"])
def test_excluded_candidate_cannot_supply_the_selected_subject_identity(
    revision_quality_driver, core_database, blocked_by
):
    def change(_, body):
        blocked = deepcopy(body["result"]["candidates"][0])
        blocked["subject_ref"]["aliases"] = ["Jun"]
        if blocked_by == "confidence":
            blocked["confidence"] = 0.2
        elif blocked_by == "uncertainty":
            blocked["uncertainty"] = "Mira and Jun may be different people."
        else:
            blocked["authority_checks"][0]["outcome"] = "CONFLICT"
        clear = deepcopy(body["result"]["candidates"][0])
        clear.update(
            id="jun",
            statement="Jun was absent.",
            slot="presence",
            value="absent",
            state_before=None,
            state_after="absent",
        )
        clear["subject_ref"]["name"] = "Jun"
        clear["evidence"] = [
            dict(paragraph_index=2, short_excerpt="Jun was absent", reason="Absent character.")
        ]
        body["result"]["candidates"] = [blocked, clear]

    d = revision_quality_driver
    prepare(d, core_database, change)
    candidates = d.read("/memory")[0]["proposal"]["candidates"]
    assert candidates[0]["conflict_status"] in {"AMBIGUOUS", "AUTHORITY_CONFLICT"}
    response = confirm(d, ["jun"])
    assert response.status_code == 200, response.text
    history = d.read("/memory")[0]
    assert len(history["entries"]) == 1
    with core_database.session() as session:
        repo = MemoryRepository(session)
        subjects = repo.subjects(UUID(d.creation["project_id"]))
        assert len(subjects) == 1
        assert subjects[0].name == "Jun" and subjects[0].aliases == []
        assert history["entries"][0]["subject_id"] == str(subjects[0].id)


@pytest.mark.parametrize("source_blocked", [False, True])
def test_selected_identity_requires_its_selected_alias_evidence(
    revision_quality_driver, core_database, source_blocked
):
    def change(_, body):
        source = deepcopy(body["result"]["candidates"][0])
        source["subject_ref"]["aliases"] = ["Jun"]
        if source_blocked:
            source["existing_entry_id"] = str(uuid4())
        clear = deepcopy(body["result"]["candidates"][0])
        clear.update(
            id="jun",
            statement="Jun was absent.",
            slot="presence",
            value="absent",
            state_before=None,
            state_after="absent",
        )
        clear["subject_ref"]["name"] = "Jun"
        clear["evidence"] = [
            dict(paragraph_index=2, short_excerpt="Jun was absent", reason="Absent character.")
        ]
        body["result"]["candidates"] = [source, clear]

    d = revision_quality_driver
    prepare(d, core_database, change)
    candidates = d.read("/memory")[0]["proposal"]["candidates"]
    assert candidates[0]["conflict_status"] == ("AMBIGUOUS" if source_blocked else "NONE")
    response = confirm(d, ["jun"])
    assert response.status_code == 409, response.text
    with core_database.session() as session:
        for table in ["memory_commit_batches", "committed_memory", "memory_subjects"]:
            assert session.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    d.refresh()
    assert d.workflow["current_state"] == "C15_MEMORY_COMMIT"
    response = confirm(d, ["state", "jun"])
    assert response.status_code == (409 if source_blocked else 200), response.text
    with core_database.session() as session:
        repo = MemoryRepository(session)
        subjects = repo.subjects(UUID(d.creation["project_id"]))
        if source_blocked:
            assert subjects == []
            assert repo.entries(UUID(d.creation["project_id"])) == []
        else:
            assert len(subjects) == 1
            assert subjects[0].name == "Mira" and subjects[0].aliases == ["jun"]
            entries = repo.entries(UUID(d.creation["project_id"]))
            assert len(entries) == 2 and {entry.subject_id for entry in entries} == {subjects[0].id}


def test_commit_failure_rolls_back_all_rows(revision_quality_driver, core_database, monkeypatch):
    d = revision_quality_driver
    prepare(d, core_database)
    original = MemoryRepository.add

    def fail(self, record):
        if isinstance(record, CommittedMemory) and record.candidate_id == "fact":
            raise RuntimeError("injected storage failure")
        return original(self, record)

    monkeypatch.setattr(MemoryRepository, "add", fail)
    response = confirm(d, ["state", "fact"])
    assert response.status_code == 500
    assert d.client.get(d.chapter_api).json()["status"] != "COMPLETED"
    with core_database.session() as s:
        for table in ["memory_commit_batches", "committed_memory", "memory_subjects"]:
            assert s.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    monkeypatch.setattr(MemoryRepository, "add", original)
    assert confirm(d, ["state", "fact"]).status_code == 200


def test_back_cancels_without_memory_and_can_extract_again(revision_quality_driver, core_database):
    d = revision_quality_driver
    prepare(d, core_database)
    h = d.read("/memory")[0]
    result = d.client.post(
        d.url + "/memory/discard",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            request_id=h["request"]["id"],
        ),
    )
    assert result.status_code == 200, result.text
    d.refresh()
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS"
    assert d.read("/memory")[0]["status"] == "CANCELLED"
    assert d.client.get(d.chapter_api.split("/chapters/")[0] + "/memory").json() == []
    complete_request(d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C15_MEMORY_COMMIT"


def test_stale_draft_cannot_confirm(revision_quality_driver, core_database):
    d = revision_quality_driver
    prepare(d, core_database)
    install_draft(d, STORY + "\n\nMira returned.")
    assert d.read("/memory")[0]["status"] == "STALE"
    response = confirm(d, ["state"])
    assert response.status_code == 409, response.text


def test_duplicate_candidates_keep_one_even_if_first_excluded(
    revision_quality_driver, core_database
):
    def change(_, body):
        row = deepcopy(body["result"]["candidates"][0])
        row["id"] = "copy"
        body["result"]["candidates"].append(row)

    d = revision_quality_driver
    prepare(d, core_database, change)
    assert confirm(d, ["copy"]).status_code == 200
    h = d.read("/memory")[0]
    assert len(h["entries"]) == 1 and h["entries"][0]["candidate_id"] == "copy"


def next_chapter(d, db, sequence):
    base = d.chapter_api.split("/chapters/")[0]
    chapter = d.client.post(
        base + "/chapters", json=dict(title=f"Chapter {sequence}", sequence=sequence)
    )
    assert chapter.status_code == 201, chapter.text
    return QualityDriver(d.client, base + "/chapters/" + chapter.json()["id"]).approve_plan(db)


@pytest.mark.parametrize("selected", [["copy", "fact"], ["state", "copy", "fact"]])
def test_temporal_versions_aliases_future_subjects_and_duplicate_commit(
    revision_quality_driver, core_database, selected
):
    d = revision_quality_driver

    def aliases(_, body):
        body["result"]["candidates"][0]["subject_ref"]["aliases"] = ["Mi"]

    prepare(d, core_database, aliases)
    assert confirm(d, ["state", "fact"]).status_code == 200
    first = d.read("/memory")[0]["entries"]
    original = next(e for e in first if e["memory_type"] == "CHARACTER_STATE")
    other = next_chapter(d, core_database, 3)

    def transition(_, body):
        body["result"]["candidates"] = body["result"]["candidates"][:2]
        c = body["result"]["candidates"][0]
        c.update(
            state_before="Harbor",
            state_after="Hill",
            value="Hill",
            statement="Mira returned to Hill.",
        )
        c["evidence"][0]["short_excerpt"] = "Mira reached Hill"
        copy = deepcopy(c)
        copy["id"] = "copy"
        body["result"]["candidates"].append(copy)

    prepare(
        other,
        core_database,
        transition,
        STORY.replace("Harbor after leaving Hill", "Hill after leaving Harbor"),
    )
    candidates = other.read("/memory")[0]["proposal"]["candidates"]
    assert [c["conflict_status"] for c in candidates] == [
        "STATE_TRANSITION",
        "DUPLICATE",
        "STATE_TRANSITION",
    ]
    result = confirm(other, selected)
    assert result.status_code == 200, result.text
    h = other.read("/memory")[0]
    assert set(h["batch"]["skipped_candidate_ids"]) == (
        {"fact", "copy"} if "state" in selected else {"fact"}
    )
    assert len(h["entries"]) == 1
    assert h["entries"][0]["version"] == 2 and h["entries"][0]["supersedes_id"] == original["id"]
    project = UUID(d.creation["project_id"])
    with core_database.session() as s:
        repo = MemoryRepository(s)
        assert repo.subjects_in_text(project, "Mi", before_sequence=2)[0].id == UUID(
            original["subject_id"]
        )
        assert repo.subjects_in_text(project, "Mira", before_sequence=1) == []
        at_two = repo.entries(project, types=["CHARACTER_STATE"], before_sequence=2)
        assert len(at_two) == 1 and at_two[0].value == "Harbor"
        assert (
            repo.entries(project, types=["CHARACTER_STATE"], before_sequence=4)[0].value == "Hill"
        )
        assert len(repo.entries(project, types=["CHARACTER_STATE"], historical=True)) == 2


def test_intrabatch_conflicting_state_group_cannot_complete_chapter(
    revision_quality_driver, core_database
):
    def change(_, body):
        state = body["result"]["candidates"][0]
        rows = []
        for index, value in enumerate(["Harbor", "Ocean", "Forest", "Harbor"]):
            row = deepcopy(state)
            row.update(id=f"state-{index}", value=value, state_after=value)
            rows.append(row)
        body["result"]["candidates"] = rows

    d = revision_quality_driver
    prepare(d, core_database, change)
    candidates = d.read("/memory")[0]["proposal"]["candidates"]
    assert all(c["conflict_status"] == "CONTRADICTION" for c in candidates)
    response = confirm(d, [candidates[-1]["id"]])
    assert response.status_code == 409, response.text
    d.refresh()
    assert d.workflow["current_state"] == "C15_MEMORY_COMMIT"
    assert d.client.get(d.chapter_api).json()["status"] != "COMPLETED"
    with core_database.session() as session:
        assert session.execute(text("SELECT count(*) FROM memory_commit_batches")).scalar() == 0
        assert session.execute(text("SELECT count(*) FROM committed_memory")).scalar() == 0


def test_concurrent_confirmation_and_replay_commit_once(revision_quality_driver, core_database):
    from concurrent.futures import ThreadPoolExecutor

    d = revision_quality_driver
    prepare(d, core_database)
    h = d.read("/memory")[0]
    body = dict(
        event_id=str(uuid4()),
        expected_state_version=d.workflow["state_version"],
        proposal_id=h["proposal"]["id"],
        selected_candidate_ids=["state"],
    )
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(lambda _: d.client.post(d.url + "/memory/confirm", json=body), range(2))
        )
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert sorted(r.json()["duplicate"] for r in responses) == [False, True]
    with core_database.session() as s:
        assert s.execute(text("SELECT count(*) FROM memory_commit_batches")).scalar() == 1
        assert s.execute(text("SELECT count(*) FROM committed_memory")).scalar() == 1


def test_extraction_contract_failure_can_return_to_draft(revision_quality_driver, core_database):
    def invalid(_, body):
        body["result"]["candidates"][0]["evidence"][0]["short_excerpt"] = "invented"

    d = revision_quality_driver
    prepare(d, core_database, invalid)

    def again(request, body):
        fixture_candidates(request, body)
        invalid(request, body)

    for _ in range(2):
        if d.workflow["status"] == "WAITING_AGENT":
            run_one(core_database, d, provider=RecordedProvider(again))
    assert d.workflow["status"] == "BLOCKED", d.workflow
    h = d.read("/memory")[0]
    response = d.client.post(
        d.url + "/memory/discard",
        json=dict(
            event_id=str(uuid4()),
            expected_state_version=d.workflow["state_version"],
            request_id=h["request"]["id"],
        ),
    )
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS"


def test_canon_change_invalidates_other_prepared_proposal(revision_quality_driver, core_database):
    d = revision_quality_driver
    prepare(d, core_database)
    other = next_chapter(d, core_database, 2)
    prepare(other, core_database)
    assert confirm(other, ["fact"]).status_code == 200
    assert d.read("/memory")[0]["status"] == "STALE"
    result = confirm(d, ["state"])
    assert result.status_code == 409, result.text
    assert d.client.get(d.chapter_api).json()["status"] != "COMPLETED"


def test_lock_after_extraction_invalidates_proposal(revision_quality_driver, core_database):
    d = revision_quality_driver
    prepare(d, core_database)
    result = d.client.post(
        d.chapter_api.split("/chapters/")[0] + "/locks",
        json=dict(
            target_type="CHAPTER_VERSION", target_id=d.creation["chapter_id"], expected_version=2
        ),
    )
    assert result.status_code == 201, result.text
    assert d.read("/memory")[0]["status"] == "STALE"
    assert confirm(d, ["state"]).status_code == 409


def test_memory_repository_never_owns_commit(core_database, monkeypatch):
    from unittest.mock import MagicMock

    from novel_os.domain.memory import MemorySubject

    session = MagicMock()
    record = MemorySubject(
        id=uuid4(),
        project_id=uuid4(),
        name="Mira",
        normalized_name="mira",
        kind="CHARACTER",
        aliases=[],
        batch_id=uuid4(),
    )
    MemoryRepository(session).add(record)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
