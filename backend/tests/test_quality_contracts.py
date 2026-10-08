from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.domain.context import KnowledgeScope, SourceType
from novel_os.domain.enums import Authority
from novel_os.domain.quality import QualityCode, category_for, verdict_for
from novel_os.quality.policy import check_evidence, validate_pass
from novel_os.quality.schemas import (
    ComplianceReview,
    NarrativeReview,
    ParagraphEvidence,
    QualityIssue,
)


def issue(code="LOW_IMMERSION", severity=None, **changes):
    hard = code in {
        "LOCKED_CONFLICT",
        "MAJOR_DIRECTION_VIOLATION",
        "MISSING_MUST",
        "FORBIDDEN_VIOLATION",
        "CANON_CONFLICT",
        "CHARACTER_KNOWLEDGE_LEAK",
    }
    severity = severity or ("P0" if hard else "P2")
    return dict(
        code=code,
        category=category_for(QualityCode(code)),
        severity=severity,
        title="场景缺少人物感受",
        description="关键选择只以解释呈现。",
        evidence=[
            dict(
                paragraph_index=1,
                excerpt="他推开门。",
                reason="动作紧接着抽象总结，缺少具体选择的代价。",
            )
        ],
        source_refs=[],
        impact="关键选择的紧张感偏弱。",
        revision_direction="保留主线，让选择的代价通过行动显现。",
        confidence=0.7,
        requires_revision=severity == "P0",
        **changes,
    )


def output(issues=(), *, compliance=False, **changes):
    values = dict(
        chapter_id=uuid4(),
        chapter_version_id=uuid4(),
        strengths=[],
        revision_priorities=[],
        source_refs=[],
        confidence=0.8,
    )
    if compliance:
        values.update(
            kind="chapter_compliance_review",
            compliance_verdict=verdict_for(issues),
            hard_gate_issues=issues,
        )
        values.update(changes)
        return ComplianceReview(**values)
    values.update(
        kind="chapter_narrative_review",
        narrative_verdict=verdict_for([i for i in issues if i.category != "AUDIENCE"]),
        audience_fit_verdict=verdict_for([i for i in issues if i.category == "AUDIENCE"]),
        quality_issues=issues,
    )
    values.update(changes)
    return NarrativeReview(**values)


def package(review, extra=()):
    draft = SimpleNamespace(
        selector_id="target-version",
        source_type=SourceType.CHAPTER_VERSION,
        source_id=review.chapter_version_id,
        source_version=1,
        structured_payload={"content": "他推开门。\n\n“我不会走。”她说。"},
    )
    return SimpleNamespace(
        items=(draft, *extra),
        request=SimpleNamespace(chapter_id=review.chapter_id, chapter_sequence=4),
    )


@pytest.mark.parametrize("code", list(QualityCode))
def test_every_taxonomy_code_has_closed_contract(code):
    parsed = QualityIssue(**issue(code))
    assert QualityIssue.model_validate_json(parsed.model_dump_json()) == parsed
    assert verdict_for([parsed]) == ("FAIL" if parsed.severity == "P0" else "PASS_WITH_WARNINGS")


@pytest.mark.parametrize(
    "severity,required,verdict",
    [
        ("P0", True, "FAIL"),
        ("P1", True, "FAIL"),
        ("P1", False, "PASS_WITH_WARNINGS"),
        ("P2", False, "PASS_WITH_WARNINGS"),
        ("P3", False, "PASS_WITH_WARNINGS"),
    ],
)
def test_verdict_depends_on_impact_not_issue_count(severity, required, verdict):
    data = issue("LOCKED_CONFLICT" if severity == "P0" else "LOW_IMMERSION", severity)
    data["requires_revision"] = required
    parsed = QualityIssue(**data)
    assert verdict_for([parsed]) == verdict
    assert verdict_for([parsed] * 20) == verdict
    assert verdict_for([]) == "PASS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("score", 98),
        ("authority_level", "A1_USER_LOCKED"),
        ("status", "APPROVED"),
        ("next_event", "REVIEW_PASSED"),
        ("version", 1),
    ],
)
def test_review_rejects_fabricated_control_and_score_fields(field, value):
    with pytest.raises(ValidationError):
        output(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence", []),
        ("confidence", 1.1),
        ("confidence", -1),
        ("confidence", float("nan")),
        ("severity", "P0"),
        ("requires_revision", True),
        ("category", "COMPLIANCE"),
    ],
)
def test_invalid_issue_rejected(field, value):
    data = issue()
    data[field] = value
    with pytest.raises(ValidationError):
        QualityIssue(**data)


def test_contradictory_verdict_cannot_be_accepted():
    with pytest.raises(ValidationError):
        output([QualityIssue(**issue())], narrative_verdict="PASS")
    with pytest.raises(ValidationError):
        output(
            [QualityIssue(**issue("MISSING_MUST", "P0"))],
            compliance=True,
            compliance_verdict="PASS",
        )


def test_no_evidence_or_wrong_paragraph_rejected():
    for index, quote in [(2, "他推开门。"), (9, "他推开门。"), (1, "伪造原文")]:
        with pytest.raises(ValueError):
            check_evidence(
                [ParagraphEvidence(paragraph_index=index, excerpt=quote, reason="理由")],
                "他推开门。\n\n她关上窗。",
            )


def test_dialogue_first_person_does_not_trigger_deterministic_pov_issue():
    review = output(compliance=True)
    validate_pass(review, package(review))
    assert review.compliance_verdict == "PASS"


@pytest.mark.parametrize(
    "code",
    [
        "MISSING_MUST",
        "FORBIDDEN_VIOLATION",
        "CANON_CONFLICT",
        "LOCKED_CONFLICT",
        "MAJOR_DIRECTION_VIOLATION",
        "CHARACTER_KNOWLEDGE_LEAK",
        "NARRATIVE_POV_MISMATCH",
        "AUDIENCE_STYLE_MISMATCH",
        "SAFE_GENERIC_CREATIVE_CHOICE",
    ],
)
def test_claims_without_relevant_sources_are_rejected(code):
    parsed = QualityIssue(**issue(code))
    review = output([parsed], compliance=parsed.category == "COMPLIANCE")
    with pytest.raises(ValueError):
        validate_pass(review, package(review))


@pytest.mark.parametrize(
    "code,field",
    [
        ("MISSING_MUST", "must.M1"),
        ("FORBIDDEN_VIOLATION", "forbidden.F1"),
        ("NARRATIVE_POV_MISMATCH", "narrative_perspective"),
        ("AUDIENCE_STYLE_MISMATCH", "target_audience"),
        ("MAJOR_DIRECTION_VIOLATION", None),
        ("LOCKED_CONFLICT", None),
        ("CANON_CONFLICT", None),
        ("CHARACTER_KNOWLEDGE_LEAK", None),
    ],
)
def test_supported_context_claims_keep_exact_reference(code, field):
    kind = (
        SourceType.CREATIVE_BRIEF
        if code in {"MISSING_MUST", "FORBIDDEN_VIOLATION"}
        else SourceType.PROJECT_WRITING_PROFILE
        if code in {"NARRATIVE_POV_MISMATCH", "AUDIENCE_STYLE_MISMATCH"}
        else SourceType.CHAPTER_PLAN
        if code == "MAJOR_DIRECTION_VIOLATION"
        else SourceType.DECISION
    )
    record = SimpleNamespace(
        source_type=kind,
        source_id=uuid4(),
        source_version=2,
        selector_id="approved-plan" if code == "MAJOR_DIRECTION_VIOLATION" else "test",
        structured_payload={
            "must": [{"id": "M1"}],
            "forbidden": [{"id": "F1"}],
            "narrative_perspective": "THIRD_PERSON",
            "target_audience": "儿童冒险",
        },
        authority_level=Authority.A5_USER_PREFERENCE
        if kind == SourceType.PROJECT_WRITING_PROFILE
        else Authority.A1_USER_LOCKED,
        locked=True,
        knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE,
        character_id=uuid4(),
    )
    ref = dict(source_type=kind, source_id=record.source_id, source_version=2, field=field)
    data = issue(code)
    data["source_refs"] = [ref]
    parsed = QualityIssue(**data)
    review = output([parsed], compliance=parsed.category == "COMPLIANCE", source_refs=[ref])
    validate_pass(review, package(review, [record]))
    # A forged version of an otherwise existing source is not accepted.
    bad = review.model_copy(
        update={"source_refs": [review.source_refs[0].model_copy(update={"source_version": 3})]}
    )
    with pytest.raises(ValueError):
        validate_pass(bad, package(bad, [record]))


@pytest.mark.parametrize(
    "code",
    [
        "LOCKED_CONFLICT",
        "MAJOR_DIRECTION_VIOLATION",
        "MISSING_MUST",
        "FORBIDDEN_VIOLATION",
        "CANON_CONFLICT",
        "CHARACTER_KNOWLEDGE_LEAK",
    ],
)
@pytest.mark.parametrize("severity", ["P1", "P2", "P3"])
def test_authoritative_conflicts_cannot_be_downgraded(code, severity):
    data = issue(code, severity)
    data["requires_revision"] = False
    with pytest.raises(ValidationError):
        QualityIssue(**data)


@pytest.mark.parametrize(
    "code,kind", [("MISSING_MUST", "MUST"), ("FORBIDDEN_VIOLATION", "FORBIDDEN")]
)
@pytest.mark.parametrize(
    "status,authority", [("APPROVED", "A2_USER_APPROVED"), ("LOCKED", "A1_USER_LOCKED")]
)
def test_approved_requirement_can_prove_exact_hard_constraint(code, kind, status, authority):
    record = SimpleNamespace(
        source_type=SourceType.REQUIREMENT,
        source_id=uuid4(),
        source_version=2,
        selector_id="effective-requirements",
        structured_payload={"content": "正式硬约束", "requirement_type": kind},
        status=status,
        authority_level=authority,
    )
    ref = dict(
        source_type=record.source_type,
        source_id=record.source_id,
        source_version=2,
        field="content",
    )
    data = issue(code)
    data["source_refs"] = [ref]
    review = output([QualityIssue(**data)], compliance=True, source_refs=[ref])
    validate_pass(review, package(review, [record]))


@pytest.mark.parametrize(
    "changes",
    [
        {"requirement_type": "SHOULD"},
        {"requirement_type": "PREFERENCE"},
        {"requirement_type": "MUST"},
        {"status": "PROPOSED"},
        {"status": "SUPERSEDED"},
        {"authority_level": "A5_USER_PREFERENCE"},
        {"authority_level": "A7_AI_INFERENCE"},
        {"status": "APPROVED", "authority_level": "A1_USER_LOCKED"},
        {"status": "LOCKED", "authority_level": "A2_USER_APPROVED"},
        {"field": "requirement_type"},
        {"source_version": 3},
    ],
)
def test_requirement_hard_constraint_proof_rejects_soft_wrong_or_stale_sources(changes):
    record = SimpleNamespace(
        source_type=SourceType.REQUIREMENT,
        source_id=uuid4(),
        source_version=2,
        selector_id="effective-requirements",
        structured_payload={
            "content": "禁止事项",
            "requirement_type": changes.get("requirement_type", "FORBIDDEN"),
        },
        status=changes.get("status", "APPROVED"),
        authority_level=changes.get("authority_level", "A2_USER_APPROVED"),
    )
    ref = dict(
        source_type=record.source_type,
        source_id=record.source_id,
        source_version=changes.get("source_version", 2),
        field=changes.get("field", "content"),
    )
    data = issue("FORBIDDEN_VIOLATION")
    data["source_refs"] = [ref]
    review = output([QualityIssue(**data)], compliance=True, source_refs=[ref])
    with pytest.raises(ValueError):
        validate_pass(review, package(review, [record]))
