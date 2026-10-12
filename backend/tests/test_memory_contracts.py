from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.domain.memory import CommittedMemory, MemorySubject, MemoryType
from novel_os.memory.policy import normalize_candidates, normalized, validate_evidence
from novel_os.memory.schemas import MemoryAgentResult, MemoryCandidate, MemoryExtractionOutput
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry

PROJECT, CHAPTER, SUBJECT = uuid4(), uuid4(), uuid4()
TEXT = "Mira reached Harbor after leaving Hill.\n\nMira suspects the captain has a key."


def candidate(**changes):
    body = dict(
        id="m1",
        candidate_type="CHARACTER_STATE",
        subject_ref=dict(
            name="Mira", kind="CHARACTER", logical_id=None, aliases=[], resolution="NEW"
        ),
        statement="Mira is now in Harbor.",
        slot="location",
        value="Harbor",
        state_before="Hill",
        state_after="Harbor",
        epistemic_status=None,
        importance="CONTINUITY",
        evidence=[
            dict(
                paragraph_index=1,
                short_excerpt="Mira reached Harbor",
                reason="A lasting location change.",
            )
        ],
        target_layer="CANON",
        source_refs=[dict(source_type="CHAPTER_VERSION", logical_id=CHAPTER, version=1)],
        confidence=0.9,
        existing_entry_id=None,
        authority_checks=[],
        uncertainty=None,
    )
    body.update(changes)
    return body


def normalize(*bodies, old=None, subjects=(), content=TEXT):
    return normalize_candidates(
        MemoryExtractionOutput(kind="chapter_memory", candidates=list(bodies)),
        project_id=PROJECT,
        chapter_id=CHAPTER,
        content=content,
        subjects=subjects,
        lookup=lambda *_: old,
    )


def entry(**changes):
    data = dict(
        project_id=PROJECT,
        chapter_id=uuid4(),
        chapter_version_id=uuid4(),
        batch_id=uuid4(),
        candidate_id="old",
        logical_id=uuid4(),
        version=1,
        supersedes_id=None,
        subject_id=SUBJECT,
        memory_type="CHARACTER_STATE",
        slot="location",
        value="Hill",
        statement="At Hill",
        epistemic_status=None,
        authority_level="A3_CANON",
        body={},
    )
    data.update(changes)
    return CommittedMemory(**data)


def test_schema_is_runtime_contract_and_prompt_layers_resolve():
    task = TaskDefinitionRegistry().get("EXTRACT_CHAPTER_MEMORY")
    assert task.output_schema.model is MemoryAgentResult
    assert task.resolve(PromptRegistry())
    schema = task.output_schema.model.model_json_schema()
    assert schema["properties"]["memory_proposals"]["maxItems"] == 0
    assert schema["properties"]["proposed_changes"]["maxItems"] == 0


@pytest.mark.parametrize("kind", list(MemoryType))
def test_six_types_and_service_authority(kind):
    changes = dict(candidate_type=kind)
    if kind in {"OPEN_THREAD", "DERIVED_CHAPTER_SUMMARY"}:
        changes.update(target_layer="DERIVED", importance="DERIVED_HINT")
    if kind == "CHARACTER_KNOWLEDGE":
        changes["epistemic_status"] = "BELIEVES"
    result = normalize(candidate(**changes))[0]
    assert result["authority_level"] == (
        "A6_DERIVED_MEMORY" if kind in {"OPEN_THREAD", "DERIVED_CHAPTER_SUMMARY"} else "A3_CANON"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"candidate_type": "USER_DECISION"},
        {"evidence": []},
        {"authority_level": "A1_USER_LOCKED"},
        {"version": 2},
        {"status": "APPROVED"},
        {"confidence": 1.1},
        {"candidate_type": "CANON_FACT", "epistemic_status": "BELIEVES"},
        {"candidate_type": "CHARACTER_KNOWLEDGE", "epistemic_status": None},
        {"target_layer": "DERIVED"},
        {"state_after": "Elsewhere"},
        {"subject_ref": None},
        {"importance": "DECORATIVE"},
        {"known_fact_id": str(uuid4())},
    ],
)
def test_illegal_candidate_rejected(changes):
    with pytest.raises(ValidationError):
        MemoryCandidate.model_validate(candidate(**changes))


@pytest.mark.parametrize("epistemic", ["KNOWS", "BELIEVES", "SUSPECTS", "DOUBTS"])
def test_knowledge_has_owner_and_preserves_epistemic_status(epistemic):
    result = normalize(candidate(candidate_type="CHARACTER_KNOWLEDGE", epistemic_status=epistemic))[
        0
    ]
    assert result["subject_id"] and result["epistemic_status"] == epistemic
    assert result["candidate_type"] == "CHARACTER_KNOWLEDGE"


def test_empty_and_duplicate_candidate_identifiers():
    assert MemoryExtractionOutput(kind="chapter_memory", candidates=[]).candidates == []
    with pytest.raises(ValidationError):
        MemoryExtractionOutput(kind="chapter_memory", candidates=[candidate(), candidate()])


@pytest.mark.parametrize(
    "change",
    [
        {"source_refs": [dict(source_type="CHAPTER_PLAN", logical_id=CHAPTER, version=1)]},
        {"source_refs": [dict(source_type="CHAPTER_VERSION", logical_id=CHAPTER, version=2)]},
        {
            "evidence": [
                dict(paragraph_index=2, short_excerpt="Mira reached Harbor", reason="bad index")
            ]
        },
        {
            "evidence": [
                dict(
                    paragraph_index=1,
                    short_excerpt="Mira is courageous",
                    reason="unsupported inference",
                )
            ]
        },
    ],
)
def test_exact_source_and_minimal_quote_evidence(change):
    output = MemoryExtractionOutput(kind="chapter_memory", candidates=[candidate(**change)])
    with pytest.raises(ValueError):
        validate_evidence(output, SimpleNamespace(chapter_id=CHAPTER, draft_version=1), TEXT, set())


def test_quote_evidence_passes():
    validate_evidence(
        MemoryExtractionOutput(kind="chapter_memory", candidates=[candidate()]),
        SimpleNamespace(chapter_id=CHAPTER, draft_version=1),
        TEXT,
        set(),
    )


@pytest.mark.parametrize("confidence,uncertainty", [(0.2, None), (0.99, "Identity unclear")])
def test_confidence_does_not_bypass_uncertainty(confidence, uncertainty):
    assert (
        normalize(candidate(confidence=confidence, uncertainty=uncertainty))[0]["conflict_status"]
        == "AMBIGUOUS"
    )


def test_state_transition_and_old_version_preserved():
    old = entry()
    result = normalize(candidate(), old=old)[0]
    assert result["conflict_status"] == "STATE_TRANSITION" and result["previous_entry_id"] == str(
        old.id
    )
    assert old.value == "Hill" and old.version == 1


def test_canon_contradiction_and_duplicate():
    old = entry(memory_type="CANON_FACT", value="destroyed")
    assert (
        normalize(candidate(candidate_type="CANON_FACT", value="intact"), old=old)[0][
            "conflict_status"
        ]
        == "CONTRADICTION"
    )
    assert (
        normalize(candidate(value="destroyed", state_after="destroyed"), old=old)[0][
            "conflict_status"
        ]
        == "DUPLICATE"
    )


def test_knowledge_correction_is_versioned():
    old = entry(memory_type="CHARACTER_KNOWLEDGE", value="key", epistemic_status="SUSPECTS")
    result = normalize(
        candidate(
            candidate_type="CHARACTER_KNOWLEDGE",
            value="key",
            state_before="key",
            state_after="key",
            epistemic_status="KNOWS",
        ),
        old=old,
    )[0]
    assert result["conflict_status"] == "STATE_TRANSITION"


def test_alias_identity_reuses_logical_id_and_unknown_id_is_ambiguous():
    subject = MemorySubject(
        id=SUBJECT,
        project_id=PROJECT,
        name="Mira",
        normalized_name="mira",
        kind="CHARACTER",
        aliases=["navigator"],
        batch_id=uuid4(),
    )
    a = candidate()
    a["subject_ref"]["name"] = "Navigator"
    assert normalize(a, subjects=[subject])[0]["subject_id"] == str(SUBJECT)
    a["subject_ref"].update(logical_id=str(uuid4()), resolution="EXISTING")
    assert normalize(a, subjects=[subject])[0]["conflict_status"] == "AMBIGUOUS"


def test_similar_name_is_not_a_new_subject():
    subject = MemorySubject(
        id=SUBJECT,
        project_id=PROJECT,
        name="Mirah",
        normalized_name="mirah",
        kind="CHARACTER",
        aliases=[],
        batch_id=uuid4(),
    )
    assert normalize(candidate(), subjects=[subject])[0]["conflict_status"] == "AMBIGUOUS"


def test_intrabatch_conflicting_states_block_both():
    rows = normalize(candidate(), candidate(id="m2", value="Ocean", state_after="Ocean"))
    assert {r["conflict_status"] for r in rows} == {"CONTRADICTION"}


@pytest.mark.parametrize(
    "values",
    [
        ("Harbor", "Ocean", "Forest"),
        ("Forest", "Ocean", "Harbor"),
        ("Harbor", "Ocean", "Harbor"),
        ("Harbor", "Harbor", "Ocean"),
        ("Ocean", "Harbor", "Harbor"),
        ("Harbor", "Ocean", "Forest", "Ocean"),
    ],
)
def test_intrabatch_conflicting_state_group_blocks_every_candidate(values):
    rows = normalize(
        *(candidate(id=f"m{i}", value=value, state_after=value) for i, value in enumerate(values))
    )
    assert all(row["conflict_status"] == "CONTRADICTION" for row in rows)


@pytest.mark.parametrize(
    "blocked_by", ["confidence", "uncertainty", "identity", "authority", "boundary_uncertain"]
)
@pytest.mark.parametrize("blocked_first", [True, False])
def test_blocked_candidate_aliases_do_not_change_clear_candidate_identity(
    blocked_by, blocked_first
):
    blocked = candidate(
        id="unclear",
        subject_ref=dict(
            name="Mira", kind="CHARACTER", logical_id=None, aliases=["Jun"], resolution="NEW"
        ),
    )
    if blocked_by == "confidence":
        blocked["confidence"] = 0.2
    elif blocked_by == "uncertainty":
        blocked["uncertainty"] = "Mira and Jun may be different people."
    elif blocked_by == "identity":
        blocked["subject_ref"]["resolution"] = "AMBIGUOUS"
    else:
        blocked["authority_checks"] = [
            dict(
                source_ref=dict(source_type="REQUIREMENT", logical_id=uuid4(), version=1),
                outcome="CONFLICT" if blocked_by == "authority" else "UNCERTAIN",
                reason="The identity assertion does not satisfy the approved boundary.",
            )
        ]
    clear = candidate(
        id="clear",
        subject_ref=dict(
            name="Jun", kind="CHARACTER", logical_id=None, aliases=[], resolution="NEW"
        ),
        slot="presence",
        value="absent",
        state_before=None,
        state_after="absent",
    )
    bodies = [blocked, clear] if blocked_first else [clear, blocked]
    rows = {row["id"]: row for row in normalize(*bodies, content=TEXT + " Jun was absent.")}
    assert rows["unclear"]["conflict_status"] in {"AMBIGUOUS", "AUTHORITY_CONFLICT"}
    assert rows["clear"]["conflict_status"] == "NONE"
    assert rows["clear"]["normalized_subject"]["name"] == "Jun"
    assert rows["clear"]["normalized_subject"]["aliases"] == []


def test_duplicate_cannot_hide_authority_conflict():
    ref = dict(source_type="REQUIREMENT", logical_id=str(uuid4()), version=1)
    body = candidate(
        id="m2",
        authority_checks=[
            dict(source_ref=ref, outcome="CONFLICT", reason="Locked: Mira cannot know key")
        ],
    )
    assert normalize(candidate(), body)[1]["conflict_status"] == "AUTHORITY_CONFLICT"


def test_missing_authority_assessment_fails_output_validation():
    with pytest.raises(ValueError):
        validate_evidence(
            MemoryExtractionOutput(kind="chapter_memory", candidates=[candidate()]),
            SimpleNamespace(chapter_id=CHAPTER, draft_version=1),
            TEXT,
            {("REQUIREMENT", str(uuid4()), 1)},
        )


def test_normalization_is_unicode_stable():
    assert normalized("Ｍｉｒａ") == normalized("Mira")


def test_same_batch_aliases_resolve_one_identity_even_if_alias_comes_first():
    first = candidate(
        id="short",
        subject_ref=dict(
            name="Mi", kind="CHARACTER", logical_id=None, aliases=[], resolution="NEW"
        ),
    )
    second = candidate(
        id="full",
        subject_ref=dict(
            name="Mira", kind="CHARACTER", logical_id=None, aliases=["Mi"], resolution="NEW"
        ),
    )
    rows = normalize(first, second)
    assert rows[0]["subject_id"] == rows[1]["subject_id"]
    assert rows[0]["normalized_subject"]["aliases"] == ["mi"]
    assert rows[1]["conflict_status"] == "DUPLICATE"


def test_decimal_values_do_not_compare_equal():
    rows = normalize(
        candidate(value="15 metres", state_after="15 metres", state_before=None),
        old=entry(value="1.5 metres"),
    )
    assert rows[0]["conflict_status"] == "CONTRADICTION"


def test_canon_semantic_boundary_conflict_is_not_relabelled_new_fact():
    check = dict(
        source_ref=dict(source_type="EXTENSION", logical_id=uuid4(), version=1),
        outcome="CONFLICT",
        reason="Contradicts a supplied canon fact",
    )
    assert normalize(candidate(authority_checks=[check]))[0]["conflict_status"] == "CONTRADICTION"


def test_current_writer_profile_has_no_raw_previous_chapter_leak():
    from novel_os.context.profiles import ContextProfileRegistry

    profile = ContextProfileRegistry().for_task("WRITE_CHAPTER")
    assert profile.version >= 6
    assert not any(s.source_type == "CHAPTER_VERSION" for s in profile.selectors)


def test_completion_uses_actual_hard_gate_issues(monkeypatch):
    from novel_os.domain.errors import DomainError
    from novel_os.services.memory_commit import MemoryCommitService, QualityRepository

    source = uuid4()
    review = SimpleNamespace(
        chapter_version_id=source,
        body=dict(hard_gate_issues=[dict(severity="P0", code="LOCKED_CONFLICT")]),
    )
    monkeypatch.setattr(QualityRepository, "history", lambda *_: [review])
    with pytest.raises(DomainError, match="authority conflict"):
        MemoryCommitService(None).check_review(PROJECT, CHAPTER, source)
    # A subjective preference cannot block the user's acceptance.
    review.body["hard_gate_issues"][0] = dict(severity="P1", code="AI_STYLE")
    MemoryCommitService(None).check_review(PROJECT, CHAPTER, source)


def test_shortened_dialogue_cannot_invent_a_closing_quote():
    source = "Mira said: “Five minutes. Then we leave.”"
    bad = candidate(
        evidence=[dict(paragraph_index=1, short_excerpt="“Five minutes.”", reason="deadline")]
    )
    request = SimpleNamespace(chapter_id=CHAPTER, draft_version=1)
    with pytest.raises(ValueError, match="exact numbered paragraph"):
        validate_evidence(
            MemoryExtractionOutput(kind="chapter_memory", candidates=[bad]), request, source, set()
        )
    bad["evidence"][0]["short_excerpt"] = "Five minutes."
    validate_evidence(
        MemoryExtractionOutput(kind="chapter_memory", candidates=[bad]), request, source, set()
    )


def test_exact_quote_prompt_patch_preserves_history():
    registry = PromptRegistry()
    task = TaskDefinitionRegistry().get("EXTRACT_CHAPTER_MEMORY")
    modules = task.resolve(registry)
    selected = next(m for m in modules if m.module.module_id == "extract-chapter-memory")
    assert selected.module.version == 3
    from novel_os.prompts.contracts import ModuleRef

    assert registry.resolve(ModuleRef(module_id="extract-chapter-memory", version=1))
