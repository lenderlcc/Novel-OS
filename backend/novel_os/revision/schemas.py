from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, ArtifactText, StrictOutput
from novel_os.domain.quality import QualityCode, Severity
from novel_os.domain.revision import RevisionScope
from novel_os.quality.schemas import Confidence, ParagraphEvidence, ReviewSource, Text


class RevisionTarget(StrictOutput):
    issue_id: UUID
    issue_code: QualityCode
    priority: Severity
    problem: Text
    revision_direction: Text
    evidence_refs: list[ParagraphEvidence] = Field(min_length=1, max_length=5)


class BlockedReason(StrictOutput):
    issue_id: UUID
    reason: Text


class RevisionPlanOutput(StrictOutput):
    kind: Literal["revision_plan"]
    chapter_id: UUID
    source_chapter_version_id: UUID
    source_review_id: UUID
    target_issue_ids: list[UUID] = Field(min_length=1, max_length=60)
    preserve_items: list[Text] = Field(min_length=1, max_length=300)
    revision_targets: list[RevisionTarget] = Field(max_length=60)
    do_not_change: list[Text] = Field(min_length=1, max_length=300)
    revision_strategy: Text
    scope: RevisionScope = RevisionScope.TARGETED
    blocked_reasons: list[BlockedReason] = Field(max_length=60)
    source_refs: list[ReviewSource] = Field(min_length=1, max_length=300)
    confidence: Confidence

    @model_validator(mode="after")
    def partition(self):
        targets = [t.issue_id for t in self.revision_targets]
        blocked = [b.issue_id for b in self.blocked_reasons]
        if len(set(targets + blocked)) != len(targets + blocked) or set(targets + blocked) != set(
            self.target_issue_ids
        ):
            raise ValueError("Every selected issue must have one safe target or blocked reason")
        if len(set(self.target_issue_ids)) != len(self.target_issue_ids):
            raise ValueError("Duplicate selected issue")
        return self


class RevisionMetadata(StrictOutput):
    kind: Literal["revision_result"]
    source_chapter_version_id: UUID
    revision_plan_id: UUID
    source_review_id: UUID
    addressed_issue_ids: list[UUID] = Field(max_length=60)
    preserved_items: list[Text] = Field(min_length=1, max_length=300)
    declared_changes: list[Text] = Field(max_length=60)
    unresolved_issue_ids: list[UUID] = Field(max_length=60)
    blocked_reasons: list[BlockedReason] = Field(max_length=60)
    source_refs: list[ReviewSource] = Field(min_length=1, max_length=300)
    confidence: Confidence


class RevisionResultOutput(RevisionMetadata):
    content: ArtifactText | None = Field(max_length=100000)


class RevisionPlanAgentResult(AgentResult):
    result: RevisionPlanOutput


class RevisionAgentResult(AgentResult):
    result: RevisionResultOutput


REVISION_RESULTS = {
    "PLAN_CHAPTER_REVISION": ("chapter-revision-plan", RevisionPlanAgentResult),
    "REVISE_CHAPTER": ("chapter-revision-result", RevisionAgentResult),
}
