"""Versioned locality contract. No changes to the chapter quality taxonomy."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, StrictOutput
from novel_os.domain.revision import ChangeBudget, FidelityCode, StructuralChange
from novel_os.quality.schemas import Confidence, ParagraphEvidence, ReviewSource, Text
from novel_os.revision.schemas import RevisionPlanOutput


class PreservationElement(StrictOutput):
    element_id: Text
    description: Text
    evidence: list[ParagraphEvidence] = Field(min_length=1, max_length=5)


class StrengthPreservation(StrictOutput):
    strength_id: Text
    mode: Literal["DIRECT", "FUNCTIONAL"]
    preservation_direction: Text


class StrengthRegressionRisk(StrictOutput):
    strength_id: Text
    risk: Text
    mitigation: Text


class RevisionZone(StrictOutput):
    issue_ids: list[UUID] = Field(min_length=1, max_length=60)
    semantic_range: Text
    paragraph_start: int | None = Field(default=None, ge=1)
    paragraph_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def bounds(self):
        if (self.paragraph_start is None) != (self.paragraph_end is None):
            raise ValueError("Both paragraph bounds are required together")
        if self.paragraph_start is not None and self.paragraph_end < self.paragraph_start:
            raise ValueError("Reversed revision zone")
        if len(set(self.issue_ids)) != len(self.issue_ids):
            raise ValueError("Duplicate zone issue")
        return self


class StructuralAuthorization(StrictOutput):
    issue_id: UUID
    review_root_cause: Text
    reason: Text
    why_local_insufficient: Text


class FidelityRevisionPlan(RevisionPlanOutput):
    preserve_scene_elements: list[PreservationElement] = Field(min_length=1, max_length=30)
    preserve_relationship_elements: list[PreservationElement] = Field(max_length=30)
    preserve_effective_details: list[PreservationElement] = Field(min_length=1, max_length=30)
    strength_preservation: list[StrengthPreservation] = Field(max_length=20)
    strength_regression_risks: list[StrengthRegressionRisk] = Field(max_length=20)
    revision_zones: list[RevisionZone] = Field(max_length=60)
    allowed_structural_change: StructuralChange = StructuralChange.LOCAL
    structural_authorization: StructuralAuthorization | None = None
    change_budget: ChangeBudget = ChangeBudget.MINIMAL

    @model_validator(mode="after")
    def locality(self):
        targets = {t.issue_id for t in self.revision_targets}
        if {i for z in self.revision_zones for i in z.issue_ids} != targets:
            raise ValueError("Revision zones must cover exactly the actionable targets")
        if self.allowed_structural_change == StructuralChange.CHAPTER_WIDE:
            if (
                not self.structural_authorization
                or self.structural_authorization.issue_id not in targets
            ):
                raise ValueError(
                    "Chapter-wide changes require an explicit Review root cause "
                    "and why local repair is insufficient"
                )
        elif (
            self.structural_authorization is not None
            or self.change_budget == ChangeBudget.BROAD
            or self.scope == "FULL_PASS"
        ):
            raise ValueError("Broad/full-pass changes require chapter-wide authorization")
        ids = [
            e.element_id
            for e in self.preserve_scene_elements
            + self.preserve_relationship_elements
            + self.preserve_effective_details
        ]
        if len(set(ids)) != len(ids) or any(
            i.startswith("strength:") or i in REQUIRED_CHECKS for i in ids
        ):
            raise ValueError("Preservation element IDs must be unique and not reserved")
        strengths = [s.strength_id for s in self.strength_preservation]
        risks = [s.strength_id for s in self.strength_regression_risks]
        if (
            len(set(strengths)) != len(strengths)
            or len(set(risks)) != len(risks)
            or not set(risks) <= set(strengths)
        ):
            raise ValueError("Strength preservation and risks must reference unique strengths")
        return self


REQUIRED_CHECKS = frozenset(
    {"SCENE_PREMISE", "RELATIONSHIP_FUNCTION", "UNAFFECTED_MATERIAL", "STRUCTURAL_SCOPE"}
)


class FidelityCheck(StrictOutput):
    check_id: Text
    preserved: bool = Field(strict=True)
    reason: Text
    source_evidence: list[ParagraphEvidence] = Field(min_length=1, max_length=5)
    revised_evidence: list[ParagraphEvidence] = Field(max_length=5)


class FidelityViolation(StrictOutput):
    code: FidelityCode
    check_ids: list[Text] = Field(min_length=1, max_length=110)
    description: Text


class RevisionFidelityOutput(StrictOutput):
    kind: Literal["revision_fidelity"]
    source_chapter_version_id: UUID
    source_review_id: UUID
    revision_plan_id: UUID
    candidate_id: UUID
    candidate_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["PASS", "FAIL"]
    checks: list[FidelityCheck] = Field(min_length=4, max_length=114)
    violations: list[FidelityViolation] = Field(max_length=60)
    source_refs: list[ReviewSource] = Field(min_length=1, max_length=300)
    confidence: Confidence

    @model_validator(mode="after")
    def consistent(self):
        ids = [c.check_id for c in self.checks]
        failed = {c.check_id for c in self.checks if not c.preserved}
        violations = {i for v in self.violations for i in v.check_ids}
        if len(set(ids)) != len(ids) or not set(ids) >= REQUIRED_CHECKS:
            raise ValueError("Missing or duplicate fidelity checks")
        if failed != violations or (self.verdict == "PASS") != (not failed):
            raise ValueError("Fidelity verdict, checks and violations disagree")
        if any(c.preserved and not c.revised_evidence for c in self.checks):
            raise ValueError("A preservation claim requires revised evidence")
        return self


class FidelityPlanAgentResult(AgentResult):
    result: FidelityRevisionPlan


class FidelityAgentResult(AgentResult):
    result: RevisionFidelityOutput
