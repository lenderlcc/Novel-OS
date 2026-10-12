"""Object state and thread updates keep their identity without rewriting static Canon."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_memory_contracts import candidate, entry, normalize

from novel_os.memory.schemas import MemoryCandidate
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry


def object_state(**changes):
    body = candidate(
        candidate_type="CANON_FACT",
        subject_ref=dict(
            name="Object K", kind="OBJECT", logical_id=None, aliases=[], resolution="NEW"
        ),
        slot="condition",
        statement="Object K is destroyed.",
        value="DESTROYED",
        state_before="INTACT",
        state_after="DESTROYED",
    )
    body.update(changes)
    return body


def thread(**changes):
    body = candidate(
        candidate_type="OPEN_THREAD",
        subject_ref=dict(
            name="Thread T", kind="EVENT", logical_id=None, aliases=[], resolution="NEW"
        ),
        slot="investigation",
        statement="Thread T remains open; a second witness was found.",
        value="OPEN",
        state_before="OPEN",
        state_after="OPEN",
        target_layer="DERIVED",
        importance="DERIVED_HINT",
    )
    body.update(changes)
    return body


def previous_object(**changes):
    body = dict(subject_ref=dict(kind="OBJECT"), state_before=None, state_after="INTACT")
    data = dict(memory_type="CANON_FACT", slot="condition", value="INTACT", body=body)
    data.update(changes)
    return entry(**data)


def previous_thread(**changes):
    data = dict(
        memory_type="OPEN_THREAD",
        slot="investigation",
        value="OPEN",
        statement="Thread T remains open; the first witness was found.",
        authority_level="A6_DERIVED_MEMORY",
        body=dict(state_before=None, state_after=None),
    )
    data.update(changes)
    return entry(**data)


def normalized(*bodies, old=None):
    return normalize(*bodies, old=old, content="Object K was destroyed. Thread T remains open.")


def test_explicit_object_state_transition_preserves_the_previous_record():
    old = previous_object()
    row = normalized(object_state(), old=old)[0]
    assert row["conflict_status"] == "STATE_TRANSITION"
    assert row["previous_entry_id"] == str(old.id)
    assert row["authority_level"] == "A3_CANON"
    assert old.value == "INTACT" and old.version == 1


@pytest.mark.parametrize(
    "old_body",
    [dict(subject_ref=dict(kind="OBJECT")), dict(state_after="BROKEN")],
)
def test_static_or_inconsistent_object_canon_cannot_become_a_state(old_body):
    row = normalized(object_state(), old=previous_object(body=old_body))[0]
    assert row["conflict_status"] == "CONTRADICTION"


@pytest.mark.parametrize("state_before", [None, "BROKEN", "intact", "INTACT "])
def test_object_transition_requires_the_exact_previous_state(state_before):
    row = normalized(object_state(state_before=state_before), old=previous_object())[0]
    assert row["conflict_status"] == "CONTRADICTION"


def test_non_object_canon_remains_immutable_with_state_markers():
    body = object_state()
    body["subject_ref"]["kind"] = "LOCATION"
    old = previous_object(body=dict(subject_ref=dict(kind="LOCATION"), state_after="INTACT"))
    assert normalized(body, old=old)[0]["conflict_status"] == "CONTRADICTION"


def test_initial_object_state_and_static_canon_are_both_supported():
    assert normalized(object_state(state_before=None))[0]["conflict_status"] == "NONE"
    body = object_state(state_before=None, state_after=None)
    assert normalized(body)[0]["conflict_status"] == "NONE"


def test_initial_object_slot_cannot_be_both_mutable_state_and_static_canon():
    rows = normalized(
        object_state(id="mutable", state_before=None),
        object_state(id="static", state_before=None, state_after=None),
    )
    assert {row["conflict_status"] for row in rows} == {"CONTRADICTION"}


@pytest.mark.parametrize(
    "body",
    [object_state(state_after="BROKEN"), thread(state_after="CLOSED"), thread(state_after=None)],
)
def test_state_marker_disagreement_fails_the_output_schema(body):
    with pytest.raises(ValidationError):
        MemoryCandidate.model_validate(body)


def test_unchanged_thread_with_new_evidence_is_duplicate():
    old = previous_thread()
    body = thread(
        statement="  THREAD T remains open;  the first witness was found.  ",
        state_before=None,
        state_after=None,
        evidence=[
            dict(paragraph_index=2, short_excerpt="new quoted evidence", reason="same topic")
        ],
        source_refs=[dict(source_type="CHAPTER_VERSION", logical_id=uuid4(), version=2)],
    )
    assert normalized(body, old=old)[0]["conflict_status"] == "DUPLICATE"


def test_new_thread_description_versions_the_same_open_topic_at_derived_authority():
    old = previous_thread()
    row = normalized(thread(), old=old)[0]
    assert row["conflict_status"] == "STATE_TRANSITION"
    assert row["previous_entry_id"] == str(old.id)
    assert row["authority_level"] == "A6_DERIVED_MEMORY"
    assert row["value"] == old.value == "OPEN"


def test_thread_closure_is_an_explicit_transition():
    body = thread(value="CLOSED", state_after="CLOSED", statement="Thread T has been resolved.")
    assert normalized(body, old=previous_thread())[0]["conflict_status"] == "STATE_TRANSITION"


@pytest.mark.parametrize("state_before", [None, "open", "CLOSED"])
def test_thread_update_without_the_exact_previous_state_is_blocked(state_before):
    row = normalized(thread(state_before=state_before), old=previous_thread())[0]
    assert row["conflict_status"] == "CONTRADICTION"


def test_initial_thread_accepts_the_original_output_shape():
    row = normalized(thread(state_before=None, state_after=None))[0]
    assert row["conflict_status"] == "NONE"


def test_same_batch_thread_descriptions_cannot_disagree_under_the_same_open_value():
    rows = normalized(
        thread(id="t1"),
        thread(id="t2", statement="Thread T remains open; another suspect was identified."),
        thread(id="t3"),
        old=previous_thread(),
    )
    assert {row["conflict_status"] for row in rows} == {"CONTRADICTION"}


@pytest.mark.parametrize(
    "factory,previous", [(object_state, previous_object), (thread, previous_thread)]
)
def test_either_duplicate_transition_remains_individually_selectable(factory, previous):
    old = previous()
    rows = normalized(factory(id="m1"), factory(id="m2"), old=old)
    assert [row["conflict_status"] for row in rows] == ["STATE_TRANSITION", "STATE_TRANSITION"]
    assert all(row["previous_entry_id"] == str(old.id) for row in rows)


@pytest.mark.parametrize(
    "factory,previous", [(object_state, previous_object), (thread, previous_thread)]
)
def test_explicit_transition_cannot_hide_an_approved_authority_conflict(factory, previous):
    body = factory(
        authority_checks=[
            dict(
                source_ref=dict(source_type="DECISION", logical_id=uuid4(), version=1),
                outcome="CONFLICT",
                reason="The update contradicts a locked decision.",
            )
        ]
    )
    assert normalized(body, old=previous())[0]["conflict_status"] == "AUTHORITY_CONFLICT"


def test_updated_task_schema_and_prompt_keep_the_historical_versions():
    registry = PromptRegistry()
    task = TaskDefinitionRegistry().get("EXTRACT_CHAPTER_MEMORY")
    assert task.output_schema.version == 2
    current = next(
        module
        for module in task.resolve(registry)
        if module.module.module_id == "extract-chapter-memory"
    )
    assert current.module.version == 3
    assert registry.resolve(ModuleRef(module_id="extract-chapter-memory", version=1))
    assert registry.resolve(ModuleRef(module_id="extract-chapter-memory", version=2))


def test_pending_memory_task_keeps_its_historical_schema_and_prompt():
    task = TaskDefinitionRegistry().get("EXTRACT_CHAPTER_MEMORY", "chapter-memory-result.v1")
    assert task.output_schema.version == 1
    current = next(
        module
        for module in task.resolve(PromptRegistry())
        if module.module.module_id == "extract-chapter-memory"
    )
    assert current.module.version == 2
