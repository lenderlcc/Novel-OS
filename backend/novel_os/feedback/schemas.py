from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, Proposal, StrictOutput
from novel_os.domain.feedback import FeedbackAction, FeedbackScope
from novel_os.quality.schemas import Confidence, ReviewSource, Text


class RequestedChange(StrictOutput):
    description: Text
    target_regions: list[Text] = Field(min_length=1, max_length=20)


class FeedbackConflict(StrictOutput):
    boundary: Literal["LOCK", "CANON", "APPROVED_PLAN", "PROJECT_PROFILE", "USER_INSTRUCTIONS"]
    explanation: Text


class FeedbackInterpretationOutput(StrictOutput):
    kind: Literal["human_feedback_interpretation"]
    feedback_id: UUID
    source_chapter_version_id: UUID
    intent_summary: Text
    requested_changes: list[RequestedChange] = Field(max_length=30)
    preserve_requests: list[Text] = Field(max_length=30)
    do_not_change: list[Text] = Field(max_length=30)
    target_regions: list[Text] = Field(max_length=20)
    quality_concerns: list[Text] = Field(max_length=20)
    scope: FeedbackScope
    safe_inferences: list[Text] = Field(max_length=20)
    ambiguities: list[Text] = Field(max_length=20)
    conflicts: list[FeedbackConflict] = Field(max_length=20)
    change_impact: Literal["PROSE_ONLY", "STORY_DIRECTION", "PROJECT_PREFERENCE", "NONE"]
    action: FeedbackAction
    user_message: Text
    decision_question: Text | None
    feedback_evidence: list[Text] = Field(min_length=1, max_length=20)
    supporting_review_issue_ids: list[UUID] = Field(max_length=30)
    source_refs: list[ReviewSource] = Field(min_length=1, max_length=300)
    confidence: Confidence

    @model_validator(mode="after")
    def routing_and_scope(self):
        action = self.action
        boundaries = {c.boundary for c in self.conflicts}
        required_action = (
            FeedbackAction.USER_DECISION_REQUIRED
            if boundaries & {"LOCK", "CANON", "USER_INSTRUCTIONS"}
            else FeedbackAction.PROFILE_CHANGE_REQUIRED
            if self.change_impact == "PROJECT_PREFERENCE" or "PROJECT_PROFILE" in boundaries
            else FeedbackAction.REPLAN_REQUIRED
            if self.change_impact == "STORY_DIRECTION" or "APPROVED_PLAN" in boundaries
            else None
        )
        if required_action is not None and action != required_action:
            raise ValueError("Action conflicts with the declared authority boundary")
        if action == FeedbackAction.REVISION and (
            self.change_impact != "PROSE_ONLY"
            or self.conflicts
            or not self.requested_changes
            or self.confidence < 0.6
            or self.decision_question is not None
        ):
            raise ValueError("Revision requires safe, confident prose-only targets")
        if action == FeedbackAction.NO_CHANGE and (
            self.requested_changes or self.change_impact != "NONE" or self.conflicts
        ):
            raise ValueError("No-change cannot request mutations")
        if action == FeedbackAction.USER_DECISION_REQUIRED and not self.decision_question:
            raise ValueError("A user decision needs one concise question")
        if any(
            not set(c.target_regions) <= set(self.target_regions) for c in self.requested_changes
        ):
            raise ValueError("Every change must stay within the declared semantic regions")
        for values in (
            self.target_regions,
            self.preserve_requests,
            self.do_not_change,
            self.supporting_review_issue_ids,
        ):
            if len(set(values)) != len(values):
                raise ValueError("Feedback references must be unique")
        return self


class FeedbackAgentResult(AgentResult):
    result: FeedbackInterpretationOutput
    proposed_changes: list[Proposal] = Field(default_factory=list, max_length=0)
    memory_proposals: list[Proposal] = Field(default_factory=list, max_length=0)
