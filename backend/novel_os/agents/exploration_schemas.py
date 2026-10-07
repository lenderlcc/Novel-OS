"""A03 concept diagnostics; the model cannot grant story or persistence authority."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.planning_schemas import EvidenceRef, Impact, ShortText, Text
from novel_os.agents.schemas import AgentResult, Proposal, StrictOutput
from novel_os.domain.agents import ResultStatus


class StoryConceptCandidate(StrictOutput):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    concept_summary: Text
    core_event: ShortText
    conflict_engine: ShortText
    character_pressure: ShortText
    story_progression: ShortText
    reader_interest: ShortText
    continuity_fit: ShortText
    requirement_fit: ShortText
    creative_freedom_fit: ShortText
    audience_fit: ShortText
    execution_feasibility: ShortText
    required_new_elements: list[ShortText] = Field(max_length=10)
    major_change_risk: Impact
    major_change_reason: ShortText
    similarity_risk: Impact
    similarity_reason: ShortText
    authority_fit: Literal["WITHIN_BOUNDS", "REQUIRES_MAJOR_CHANGE", "VIOLATES_LOCK_OR_CANON"]
    authority_reason: ShortText
    strengths: list[ShortText] = Field(min_length=1, max_length=5)
    risks: list[ShortText] = Field(max_length=5)


class RejectedConcept(StrictOutput):
    candidate_id: str = Field(min_length=1, max_length=40)
    code: Literal[
        "NOT_SELECTED",
        "REPETITION_RISK",
        "WEAKER_STORY_FIT",
        "SURFACE_ONLY_VARIATION",
        "REQUIRES_MAJOR_CHANGE",
        "VIOLATES_AUTHORITY",
    ]
    reason: ShortText


class CreativeExplorationOutput(StrictOutput):
    kind: Literal["creative_exploration"]
    brief_id: UUID
    mode: Literal["FOCUSED", "DIVERGENT"]
    focused_reason: ShortText | None
    candidates: list[StoryConceptCandidate] = Field(min_length=1, max_length=4)
    selected_candidate_id: str | None = Field(min_length=1, max_length=40)
    selection_reason: Text
    rejected_reasons: list[RejectedConcept] = Field(max_length=4)
    source_refs: list[EvidenceRef] = Field(min_length=1, max_length=1024)
    blocked_reason: Text | None

    @model_validator(mode="after")
    def bounded_selection(self):
        candidates = {candidate.id: candidate for candidate in self.candidates}
        if len(candidates) != len(self.candidates):
            raise ValueError("Candidate identifiers must be unique")
        if self.mode == "FOCUSED":
            if len(candidates) != 1 or self.focused_reason is None:
                raise ValueError("Focused exploration requires one concept and a reason")
        elif len(candidates) < 2 or self.focused_reason is not None:
            raise ValueError("Divergent exploration requires multiple concepts")
        selected = self.selected_candidate_id
        if selected is not None:
            candidate = candidates.get(selected)
            if candidate is None:
                raise ValueError("Selected candidate must exist")
            if candidate.major_change_risk == "HIGH" or candidate.authority_fit != "WITHIN_BOUNDS":
                raise ValueError("Selected candidate must remain within approved authority")
            if self.blocked_reason is not None:
                raise ValueError("A selected exploration cannot be blocked")
        elif self.blocked_reason is None:
            raise ValueError("Unselected exploration requires a blocked reason")
        rejected = {item.candidate_id: item for item in self.rejected_reasons}
        if len(rejected) != len(self.rejected_reasons) or set(rejected) != set(candidates) - {
            selected
        }:
            raise ValueError("Every unselected candidate requires exactly one rejection")
        for candidate_id, rejection in rejected.items():
            candidate = candidates[candidate_id]
            if (
                candidate.major_change_risk == "HIGH"
                or candidate.authority_fit == "REQUIRES_MAJOR_CHANGE"
            ):
                if rejection.code != "REQUIRES_MAJOR_CHANGE":
                    raise ValueError("Major changes must be rejected as REQUIRES_MAJOR_CHANGE")
            elif (
                candidate.authority_fit == "VIOLATES_LOCK_OR_CANON"
                and rejection.code != "VIOLATES_AUTHORITY"
            ):
                raise ValueError("Lock or Canon violations must be rejected as VIOLATES_AUTHORITY")
        keys = [(ref.source_type, ref.logical_id, ref.version) for ref in self.source_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("Source references must be unique")
        return self


class ExplorationAgentResult(AgentResult):
    result: CreativeExplorationOutput
    proposed_changes: list[Proposal] = Field(max_length=0)
    memory_proposals: list[Proposal] = Field(max_length=0)

    @model_validator(mode="after")
    def consistent_outcome(self):
        selected = self.result.selected_candidate_id is not None
        expected = ResultStatus.SUCCESS if selected else ResultStatus.BLOCKED
        if self.status != expected:
            raise ValueError("Exploration status must match its selected or blocked outcome")
        if self.escalation is not None and self.escalation.required:
            raise ValueError("Exploration uses blocked context, not a new human approval gate")
        return self
