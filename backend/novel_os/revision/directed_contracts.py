"""Additive wire versions for AI-review and human-directed revisions."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.domain.feedback import RevisionSource
from novel_os.domain.quality import QualityCode
from novel_os.quality.schemas import ParagraphEvidence
from novel_os.revision.contracts import RevisionEnvelope, RevisionPlanV3
from novel_os.revision.fidelity_schemas import FidelityCheck, RevisionFidelityOutput
from novel_os.revision.schemas import RevisionResultOutput, RevisionTarget


class DirectedTarget(RevisionTarget):
    issue_code: QualityCode | Literal["HUMAN_FEEDBACK"]
    evidence_refs: list[ParagraphEvidence] = Field(max_length=5)

    @model_validator(mode="after")
    def review_evidence(self):
        if self.issue_code != "HUMAN_FEEDBACK" and not self.evidence_refs:
            raise ValueError("AI Review targets require their exact evidence")
        return self


class DirectedBinding:
    """Validation shared by the new Pydantic subclasses; no legacy contract changes."""

    @model_validator(mode="after")
    def source_binding(self):
        if self.revision_source == RevisionSource.AI_REVIEW:
            if self.source_feedback_id is not None or self.source_review_id is None:
                raise ValueError("AI Review revision must bind only its Review")
        elif self.source_feedback_id is None:
            raise ValueError("Human revision requires its exact Feedback")
        elif self.revision_source == RevisionSource.BOTH and self.source_review_id is None:
            raise ValueError("Combined revision needs its diagnostic Review")
        return self


class DirectedRevisionPlan(DirectedBinding, RevisionPlanV3):
    revision_source: RevisionSource = RevisionSource.AI_REVIEW
    source_feedback_id: UUID | None = None
    source_review_id: UUID | None
    revision_targets: list[DirectedTarget] = Field(max_length=60)


class DirectedRevisionOutput(DirectedBinding, RevisionResultOutput):
    revision_source: RevisionSource = RevisionSource.AI_REVIEW
    source_feedback_id: UUID | None = None
    source_review_id: UUID | None


class DirectedFidelityOutput(DirectedBinding, RevisionFidelityOutput):
    revision_source: RevisionSource = RevisionSource.AI_REVIEW
    source_feedback_id: UUID | None = None
    source_review_id: UUID | None
    checks: list[FidelityCheck] = Field(min_length=4, max_length=180)


class DirectedPlanResult(RevisionEnvelope):
    result: DirectedRevisionPlan


class DirectedRevisionResult(RevisionEnvelope):
    result: DirectedRevisionOutput


class DirectedFidelityResult(RevisionEnvelope):
    result: DirectedFidelityOutput
