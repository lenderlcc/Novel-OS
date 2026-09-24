"""The single source for provider JSON schemas and review API values."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, ArtifactText, StrictOutput
from novel_os.domain.context import SourceType
from novel_os.domain.quality import (
    IssueCategory,
    QualityCode,
    Severity,
    Verdict,
    category_for,
    verdict_for,
)

Text = Annotated[ArtifactText, Field(max_length=2000)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class ReviewSource(StrictOutput):
    source_type: SourceType
    source_id: UUID
    source_version: int = Field(strict=True, gt=0)
    field: str | None = Field(max_length=200)


class ParagraphEvidence(StrictOutput):
    paragraph_index: int = Field(strict=True, gt=0)
    excerpt: ArtifactText = Field(max_length=280)
    reason: Text


class QualityIssue(StrictOutput):
    code: QualityCode
    severity: Severity
    category: IssueCategory
    title: Text
    description: Text
    evidence: list[ParagraphEvidence] = Field(min_length=1, max_length=5)
    source_refs: list[ReviewSource] = Field(max_length=20)
    impact: Text
    revision_direction: Text
    confidence: Confidence
    requires_revision: bool = Field(strict=True)

    @model_validator(mode="after")
    def coherent_issue(self):
        if self.code in {QualityCode.LOCKED_CONFLICT, QualityCode.MAJOR_DIRECTION_VIOLATION} and (
            self.severity != Severity.P0 or not self.requires_revision
        ):
            raise ValueError("Confirmed locked or major direction conflicts are P0 boundaries")
        if self.code in {
            QualityCode.MISSING_MUST,
            QualityCode.FORBIDDEN_VIOLATION,
            QualityCode.CANON_CONFLICT,
            QualityCode.CHARACTER_KNOWLEDGE_LEAK,
        } and (self.severity not in {Severity.P0, Severity.P1} or not self.requires_revision):
            raise ValueError(
                "A confirmed authority or knowledge violation cannot be downgraded to a suggestion"
            )
        if self.category != category_for(self.code):
            raise ValueError("Issue code and category disagree")
        if self.severity == Severity.P0 and (
            self.category != IssueCategory.COMPLIANCE
            or self.code == QualityCode.NARRATIVE_POV_MISMATCH
        ):
            raise ValueError("Subjective quality and A5 preferences cannot become P0 gates")
        if (
            self.requires_revision != (self.severity == Severity.P0)
            and self.severity != Severity.P1
        ):
            raise ValueError("Only P0 or impactful P1 issues can require revision")
        if self.code in {
            QualityCode.SAFE_GENERIC_CREATIVE_CHOICE,
            QualityCode.LOW_CREATIVE_NOVELTY,
        } and self.severity not in {Severity.P2, Severity.P3}:
            raise ValueError("Creative choice findings remain suggestions")
        return self


class Strength(StrictOutput):
    description: Text
    evidence: list[ParagraphEvidence] = Field(min_length=1, max_length=3)
    preservation_direction: Text


class RevisionPriority(StrictOutput):
    issue_code: QualityCode
    direction: Text
    preserve: Text


class ReviewPassBase(StrictOutput):
    chapter_id: UUID
    chapter_version_id: UUID
    strengths: list[Strength] = Field(max_length=10)
    revision_priorities: list[RevisionPriority] = Field(max_length=10)
    source_refs: list[ReviewSource] = Field(max_length=100)
    confidence: Confidence

    def check_priorities(self, issues):
        if any(p.issue_code not in {i.code for i in issues} for p in self.revision_priorities):
            raise ValueError("Revision priority references a missing issue")
        if len({i.code for i in issues}) != len(issues):
            raise ValueError("Consolidate evidence for the same issue code")


class ComplianceReview(ReviewPassBase):
    kind: Literal["chapter_compliance_review"]
    compliance_verdict: Verdict
    hard_gate_issues: list[QualityIssue] = Field(max_length=30)

    @model_validator(mode="after")
    def coherent_pass(self):
        if any(i.category != IssueCategory.COMPLIANCE for i in self.hard_gate_issues):
            raise ValueError("Compliance pass cannot upgrade quality preferences")
        if self.compliance_verdict != verdict_for(self.hard_gate_issues):
            raise ValueError("Compliance verdict contradicts findings")
        self.check_priorities(self.hard_gate_issues)
        return self


class NarrativeReview(ReviewPassBase):
    kind: Literal["chapter_narrative_review"]
    narrative_verdict: Verdict
    audience_fit_verdict: Verdict
    quality_issues: list[QualityIssue] = Field(max_length=30)

    @model_validator(mode="after")
    def coherent_pass(self):
        if any(i.category == IssueCategory.COMPLIANCE for i in self.quality_issues):
            raise ValueError("Narrative pass cannot invent hard gates")
        audience = [i for i in self.quality_issues if i.category == IssueCategory.AUDIENCE]
        narrative = [i for i in self.quality_issues if i.category != IssueCategory.AUDIENCE]
        if (self.narrative_verdict, self.audience_fit_verdict) != (
            verdict_for(narrative),
            verdict_for(audience),
        ):
            raise ValueError("Narrative/audience verdict contradicts findings")
        self.check_priorities(self.quality_issues)
        return self


class ComplianceAgentResult(AgentResult):
    result: ComplianceReview


class NarrativeAgentResult(AgentResult):
    result: NarrativeReview


class ChapterReviewResult(ReviewPassBase):
    kind: Literal["chapter_quality_review"] = "chapter_quality_review"
    overall_verdict: Verdict
    compliance_verdict: Verdict
    narrative_verdict: Verdict
    audience_fit_verdict: Verdict
    hard_gate_issues: list[QualityIssue]
    quality_issues: list[QualityIssue]
    source_refs: list[ReviewSource] = Field(max_length=200)
    reviewer_version: str
    prompt_lineage_id: UUID
    context_package_id: UUID
    compliance_prompt_lineage_id: UUID
    compliance_context_package_id: UUID
    created_at: datetime

    @model_validator(mode="after")
    def coherent_aggregate(self):
        common = self.model_dump(
            include={"chapter_id", "chapter_version_id", "strengths", "confidence"}
        )
        ComplianceReview(
            **common,
            kind="chapter_compliance_review",
            compliance_verdict=self.compliance_verdict,
            hard_gate_issues=self.hard_gate_issues,
            revision_priorities=[],
            source_refs=[],
        )
        NarrativeReview(
            **common,
            kind="chapter_narrative_review",
            narrative_verdict=self.narrative_verdict,
            audience_fit_verdict=self.audience_fit_verdict,
            quality_issues=self.quality_issues,
            revision_priorities=[],
            source_refs=[],
        )
        self.check_priorities(self.hard_gate_issues + self.quality_issues)
        if self.overall_verdict != verdict_for(self.hard_gate_issues + self.quality_issues):
            raise ValueError("Overall verdict contradicts findings")
        return self


QUALITY_RESULTS = {
    "REVIEW_CHAPTER_COMPLIANCE": ("chapter-compliance-review", ComplianceAgentResult),
    "REVIEW_CHAPTER_NARRATIVE": ("chapter-narrative-review", NarrativeAgentResult),
}
