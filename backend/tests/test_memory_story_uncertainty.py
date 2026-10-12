"""Story questions stay derived without relaxing identity or authority checks."""

from uuid import uuid4

import pytest
from test_memory_contracts import PROJECT, TEXT, candidate, entry, normalize
from test_memory_transition_contracts import normalized as normalize_threads
from test_memory_transition_contracts import thread

from novel_os.domain.memory import MemorySubject


@pytest.mark.parametrize("value", ["OPEN", "PLANNED"])
def test_story_uncertainty_keeps_an_identified_thread_derived(value):
    body = thread(
        value=value,
        state_before=None,
        state_after=value,
        uncertainty="Whether the unresolved question will be answered is not yet known.",
    )
    row = normalize_threads(body)[0]
    assert row["conflict_status"] == "NONE"
    assert row["subject_id"] is not None
    assert row["normalized_subject"]["name"] == "Thread T"
    assert row["authority_level"] == "A6_DERIVED_MEMORY"
    assert row["uncertainty"] == body["uncertainty"]
    assert row["value"] == value


@pytest.mark.parametrize("uncertain_first", [False, True])
def test_story_uncertainty_does_not_change_the_same_subject_between_slots_or_selection(
    uncertain_first,
):
    clear = thread(id="clear", slot="investigation")
    unresolved = thread(
        id="unresolved", slot="commitment", uncertainty="The promised outcome is unresolved."
    )
    bodies = [unresolved, clear] if uncertain_first else [clear, unresolved]
    rows = {row["id"]: row for row in normalize_threads(*bodies)}
    selected = normalize_threads(unresolved)[0]
    assert rows["clear"]["conflict_status"] == rows["unresolved"]["conflict_status"] == "NONE"
    assert rows["clear"]["subject_id"] == rows["unresolved"]["subject_id"]
    assert selected["subject_id"] == rows["unresolved"]["subject_id"]
    assert selected["normalized_subject"] == rows["unresolved"]["normalized_subject"]
    assert selected["authority_level"] == "A6_DERIVED_MEMORY"


@pytest.mark.parametrize(
    "blocked_by", ["confidence", "identity", "missing_name", "cross_kind", "unknown_id"]
)
def test_blocked_thread_identity_cannot_supply_another_candidates_alias(blocked_by):
    blocked = thread(
        id="blocked",
        subject_ref=dict(
            name="Mira", kind="CHARACTER", logical_id=None, aliases=["Jun"], resolution="NEW"
        ),
        uncertainty="The future outcome of this story question is unresolved.",
    )
    subjects = []
    if blocked_by == "confidence":
        blocked["confidence"] = 0.59
    elif blocked_by == "identity":
        blocked["subject_ref"]["resolution"] = "AMBIGUOUS"
    elif blocked_by == "missing_name":
        blocked["subject_ref"]["name"] = "Missing Person"
    elif blocked_by == "cross_kind":
        subjects = [
            MemorySubject(
                id=uuid4(),
                project_id=PROJECT,
                name="Mira",
                normalized_name="mira",
                kind="OBJECT",
                aliases=[],
                batch_id=uuid4(),
            )
        ]
    else:
        blocked["subject_ref"].update(logical_id=str(uuid4()), resolution="EXISTING")
    clear = candidate(
        id="clear",
        subject_ref=dict(
            name="Jun", kind="CHARACTER", logical_id=None, aliases=[], resolution="NEW"
        ),
        slot="presence",
        statement="Jun was absent.",
        value="absent",
        state_before=None,
        state_after="absent",
    )
    content = TEXT + " Jun was absent."
    rows = {row["id"]: row for row in normalize(blocked, clear, subjects=subjects, content=content)}
    selected = normalize(clear, subjects=subjects, content=content)[0]
    assert rows["blocked"]["conflict_status"] == "AMBIGUOUS"
    assert rows["blocked"]["subject_id"] is None
    assert rows["clear"]["conflict_status"] == "NONE"
    assert rows["clear"]["subject_id"] == selected["subject_id"]
    assert rows["clear"]["normalized_subject"]["name"] == "Jun"
    assert rows["clear"]["normalized_subject"]["aliases"] == []


@pytest.mark.parametrize("kind", ["CANON_FACT", "CHARACTER_STATE", "DERIVED_CHAPTER_SUMMARY"])
def test_story_uncertainty_does_not_relax_other_memory_types(kind):
    body = candidate(candidate_type=kind, uncertainty="This extracted claim is not confirmed.")
    if kind == "DERIVED_CHAPTER_SUMMARY":
        body.update(subject_ref=None, target_layer="DERIVED", importance="DERIVED_HINT")
    assert normalize(body)[0]["conflict_status"] == "AMBIGUOUS"


@pytest.mark.parametrize("source_type", ["REQUIREMENT", "EXTENSION"])
@pytest.mark.parametrize("outcome", ["COMPATIBLE", "UNCERTAIN", "CONFLICT"])
def test_story_uncertainty_never_overrides_thread_authority_checks(source_type, outcome):
    body = thread(
        uncertainty="The story question remains unanswered.",
        authority_checks=[
            dict(
                source_ref=dict(source_type=source_type, logical_id=uuid4(), version=1),
                outcome=outcome,
                reason="Comparison against the supplied story boundary.",
            )
        ],
    )
    row = normalize_threads(body)[0]
    expected = {
        "COMPATIBLE": "NONE",
        "UNCERTAIN": "AMBIGUOUS",
        "CONFLICT": "CONTRADICTION" if source_type == "EXTENSION" else "AUTHORITY_CONFLICT",
    }[outcome]
    assert row["conflict_status"] == expected
    assert row["authority_level"] == "A6_DERIVED_MEMORY"


def test_story_uncertainty_preserves_existing_thread_contradiction():
    old = entry(
        memory_type="OPEN_THREAD",
        slot="investigation",
        value="OPEN",
        statement="Thread T remains open.",
        authority_level="A6_DERIVED_MEMORY",
        body=dict(state_before=None, state_after=None),
    )
    body = thread(
        value="CLOSED",
        state_before=None,
        state_after="CLOSED",
        statement="Thread T was closed without an evidenced prior state.",
        uncertainty="The underlying question is still not confirmed.",
    )
    row = normalize_threads(body, old=old)[0]
    assert row["conflict_status"] == "CONTRADICTION"
    assert row["previous_entry_id"] == str(old.id)
    assert row["authority_level"] == "A6_DERIVED_MEMORY"
