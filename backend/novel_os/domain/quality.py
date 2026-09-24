"""Review facts and immutable evidence; no framework or persistence dependency."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from novel_os.domain.core import now


class Verdict(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


class Severity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IssueCategory(StrEnum):
    COMPLIANCE = "COMPLIANCE"
    NARRATIVE = "NARRATIVE"
    CREATIVE = "CREATIVE"
    AUDIENCE = "AUDIENCE"


class QualityCode(StrEnum):
    MISSING_MUST = "MISSING_MUST"
    FORBIDDEN_VIOLATION = "FORBIDDEN_VIOLATION"
    CANON_CONFLICT = "CANON_CONFLICT"
    LOCKED_CONFLICT = "LOCKED_CONFLICT"
    MAJOR_DIRECTION_VIOLATION = "MAJOR_DIRECTION_VIOLATION"
    NARRATIVE_POV_MISMATCH = "NARRATIVE_POV_MISMATCH"
    CHARACTER_KNOWLEDGE_LEAK = "CHARACTER_KNOWLEDGE_LEAK"
    LOW_IMMERSION = "LOW_IMMERSION"
    WEAK_POV_ANCHOR = "WEAK_POV_ANCHOR"
    UNSELECTIVE_DETAIL = "UNSELECTIVE_DETAIL"
    MISALLOCATED_NARRATIVE_DETAIL = "MISALLOCATED_NARRATIVE_DETAIL"
    OVER_EXPLAINED_REASONING = "OVER_EXPLAINED_REASONING"
    OVER_EXPLAINED_EMOTIONAL_MEANING = "OVER_EXPLAINED_EMOTIONAL_MEANING"
    FUNCTIONAL_DIALOGUE = "FUNCTIONAL_DIALOGUE"
    OVER_STRUCTURED_DIALOGUE = "OVER_STRUCTURED_DIALOGUE"
    WEAK_CHARACTER_VOICE = "WEAK_CHARACTER_VOICE"
    CHARACTERS_AS_ARGUMENTS = "CHARACTERS_AS_ARGUMENTS"
    OVER_SYMMETRICAL_CONFLICT = "OVER_SYMMETRICAL_CONFLICT"
    ABSTRACT_STAKES = "ABSTRACT_STAKES"
    EXCESSIVE_CLOSURE = "EXCESSIVE_CLOSURE"
    REQUIREMENT_VISIBILITY_BIAS = "REQUIREMENT_VISIBILITY_BIAS"
    SAFE_GENERIC_CREATIVE_CHOICE = "SAFE_GENERIC_CREATIVE_CHOICE"
    LOW_CREATIVE_NOVELTY = "LOW_CREATIVE_NOVELTY"
    AUDIENCE_STYLE_MISMATCH = "AUDIENCE_STYLE_MISMATCH"


COMPLIANCE_CODES = frozenset(list(QualityCode)[:7])
CREATIVE_CODES = frozenset(
    {QualityCode.SAFE_GENERIC_CREATIVE_CHOICE, QualityCode.LOW_CREATIVE_NOVELTY}
)
QUALITY_TASKS = frozenset({"REVIEW_CHAPTER_COMPLIANCE", "REVIEW_CHAPTER_NARRATIVE"})


def category_for(code):
    if code in COMPLIANCE_CODES:
        return IssueCategory.COMPLIANCE
    if code in CREATIVE_CODES:
        return IssueCategory.CREATIVE
    if code == QualityCode.AUDIENCE_STYLE_MISMATCH:
        return IssueCategory.AUDIENCE
    return IssueCategory.NARRATIVE


def verdict_for(issues):
    if any(
        i.severity == Severity.P0 or (i.severity == Severity.P1 and i.requires_revision)
        for i in issues
    ):
        return Verdict.FAIL
    return Verdict.PASS_WITH_WARNINGS if issues else Verdict.PASS


@dataclass(frozen=True, kw_only=True)
class QualityBinding:
    id: UUID = field(default_factory=uuid4)
    project_id: UUID
    chapter_id: UUID
    workflow_id: UUID
    state_version: int
    chapter_version_id: UUID
    draft_version: int
    plan_id: UUID
    plan_version: int
    brief_id: UUID
    profile_record_id: UUID | None
    profile_version: int | None
    profile_hash: str | None
    profile_json: str
    source_snapshots: list[dict]
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class QualityPass:
    id: UUID = field(default_factory=uuid4)
    binding_id: UUID
    pass_name: str
    task_id: UUID
    run_id: UUID
    prompt_lineage_id: UUID
    context_package_id: UUID
    body: dict
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True, kw_only=True)
class ChapterQualityReview:
    id: UUID = field(default_factory=uuid4)
    binding_id: UUID
    project_id: UUID
    chapter_id: UUID
    chapter_version_id: UUID
    version: int
    compliance_pass_id: UUID
    narrative_pass_id: UUID
    body: dict
    created_at: datetime = field(default_factory=now)
