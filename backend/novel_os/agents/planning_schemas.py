"""The same closed schemas generate model contracts and validate returned business data."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, ArtifactText, StrictOutput
from novel_os.domain.context import SourceType
from novel_os.domain.planning import ReviewVerdict

Text = Annotated[ArtifactText, Field(max_length=1200)]
ShortText = Annotated[ArtifactText, Field(max_length=600)]
Confidence = Annotated[float, Field(ge=0, le=1)]
Impact = Literal["LOW", "MEDIUM", "HIGH"]
Autonomy = Literal["LOCAL_DETAIL", "SCENE_ORDER", "INFORMATION_DELIVERY", "LOCAL_CONFLICT"]
MAX_CONSTRAINTS = 512
MAX_REFERENCES = 1024
REQUIREMENT_FIELDS = {
    "MUST": "must",
    "SHOULD": "should",
    "PREFERENCE": "preferences",
    "FORBIDDEN": "forbidden",
    "PRESERVE": "preserve",
    "QUALITY_EXPECTATION": "quality_expectations",
    "CHANGE_REQUEST": "change_requests",
}


class EvidenceRef(StrictOutput):
    source_type: SourceType
    logical_id: UUID
    version: int = Field(strict=True, ge=1)


class SourcedConstraint(StrictOutput):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    text: ArtifactText
    source_ref: EvidenceRef
    # Literal evidence is checkable; semantic interpretation is also reviewed by A05/the user.
    quote: ArtifactText

    @model_validator(mode="after")
    def exact_user_words(self):
        if self.text != self.quote:
            raise ValueError("Constraints must preserve the quoted source wording")
        return self


class Assumption(StrictOutput):
    text: Text
    impact: Impact
    confidence: Confidence


class Ambiguity(StrictOutput):
    issue: Text
    impact: Impact
    confidence: Confidence
    can_safely_infer: bool = Field(strict=True)
    impact_explanation: Text
    user_decision_needed: Text

    @property
    def requires_decision(self):
        return self.impact == "HIGH" and self.confidence < 0.6 and not self.can_safely_infer


class CreativeFreedom(StrictOutput):
    level: Impact
    allowed_operations: list[Autonomy] = Field(max_length=4)
    scope_description: Text
    major_changes: Literal["PROPOSAL_ONLY"]


class CreativeBriefOutput(StrictOutput):
    kind: Literal["creative_brief"]
    intent_summary: Text
    chapter_objective: Text
    must: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    should: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    preferences: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    forbidden: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    preserve: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    quality_expectations: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    change_requests: list[SourcedConstraint] = Field(max_length=MAX_CONSTRAINTS)
    required_outcome: Text
    desired_reader_effect: Text
    character_focus: list[ShortText] = Field(max_length=20)
    plot_focus: list[ShortText] = Field(max_length=20)
    creative_freedom: CreativeFreedom
    unresolved_ambiguities: list[Ambiguity] = Field(max_length=20)
    assumptions: list[Assumption] = Field(max_length=20)
    conflicts: list[Text] = Field(max_length=20)
    persistent_preference_candidates: list[SourcedConstraint] = Field(max_length=20)
    source_refs: list[EvidenceRef] = Field(min_length=1, max_length=MAX_REFERENCES)
    confidence: Confidence

    @model_validator(mode="after")
    def unique_constraints(self):
        ids = [c.id for c in self.constraints]
        if len(ids) != len(set(ids)):
            raise ValueError("Constraint identifiers must be unique")
        if len(ids) > MAX_CONSTRAINTS:
            raise ValueError("CreativeBrief exceeds the total constraint capacity")
        return self

    @property
    def constraints(self):
        return [item for field in REQUIREMENT_FIELDS.values() for item in getattr(self, field)]


class ScenePlan(StrictOutput):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    purpose: ShortText
    conflict: ShortText
    key_change: ShortText
    information_release: list[ShortText] = Field(max_length=8)
    character_state_change: ShortText
    exit_condition: ShortText


class Coverage(StrictOutput):
    constraint_id: str = Field(min_length=1, max_length=40)
    covered: bool = Field(strict=True)
    scope: Literal["SCENE", "PLAN_GLOBAL"]
    scene_ids: list[str] = Field(max_length=20)
    explanation: ShortText


class MajorChangeProposal(StrictOutput):
    description: Text
    reason: Text
    affected_scope: Text
    required_for_plan: bool = Field(strict=True)
    disposition: Literal["PROPOSAL_ONLY"]


class ChapterPlanOutput(StrictOutput):
    kind: Literal["chapter_plan"]
    objective: Text
    required_outcome: Text
    opening_function: ShortText
    scenes: list[ScenePlan] = Field(min_length=1, max_length=20)
    character_progression: list[ShortText] = Field(max_length=20)
    plot_progression: list[ShortText] = Field(max_length=20)
    information_release: list[ShortText] = Field(max_length=20)
    foreshadow_actions: list[ShortText] = Field(max_length=20)
    ending_function: ShortText
    ending_state: Text
    creative_freedom: CreativeFreedom
    constraints: list[ArtifactText] = Field(max_length=MAX_CONSTRAINTS)
    preserved_elements: list[ArtifactText] = Field(max_length=MAX_CONSTRAINTS)
    locked_dependencies: list[EvidenceRef] = Field(max_length=MAX_REFERENCES)
    assumptions: list[Assumption] = Field(max_length=20)
    risks: list[Text] = Field(max_length=20)
    proposed_new_elements: list[ShortText] = Field(max_length=20)
    proposed_major_changes: list[MajorChangeProposal] = Field(max_length=20)
    requirement_coverage: list[Coverage] = Field(max_length=MAX_CONSTRAINTS)
    source_refs: list[EvidenceRef] = Field(min_length=1, max_length=MAX_REFERENCES)

    @model_validator(mode="after")
    def coverage_scenes(self):
        ids = {s.id for s in self.scenes}
        if len(ids) != len(self.scenes):
            raise ValueError("Scene identifiers must be unique")
        if any(set(c.scene_ids) - ids for c in self.requirement_coverage):
            raise ValueError("Coverage references an unknown scene")
        if len({c.constraint_id for c in self.requirement_coverage}) != len(
            self.requirement_coverage
        ):
            raise ValueError("Duplicate coverage entry")
        return self


HardGateCode = Literal[
    "MISSING_MUST",
    "FORBIDDEN_VIOLATION",
    "LOCKED_CONFLICT",
    "DIRECTION_CONFLICT",
    "OUTCOME_UNACHIEVABLE",
    "MAJOR_LOGIC_BREAK",
    "REQUIREMENT_MISUNDERSTANDING",
]


class HardGateIssue(StrictOutput):
    code: HardGateCode
    description: Text
    constraint_id: str | None = Field(default=None, min_length=1, max_length=40)


class LogicRisk(StrictOutput):
    description: Text
    impact: Impact


class PlanReviewRecord(StrictOutput):
    """Read shape for immutable reports, including historic invalid v1 evidence."""

    kind: Literal["plan_review"]
    verdict: ReviewVerdict
    # The overall output has a 150 KB parser bound; derived hard gates must never be truncated.
    hard_gate_issues: list[HardGateIssue]
    quality_issues: list[Text] = Field(max_length=30)
    requirement_coverage: list[Coverage] = Field(max_length=MAX_CONSTRAINTS)
    missing_requirements: list[Text] = Field(max_length=MAX_CONSTRAINTS)
    forbidden_violations: list[Text] = Field(max_length=30)
    locked_conflicts: list[Text] = Field(max_length=30)
    direction_conflicts: list[Text] = Field(max_length=30)
    logic_risks: list[LogicRisk] = Field(max_length=30)
    over_specification_issues: list[Text] = Field(max_length=30)
    recommendations: list[Text] = Field(max_length=30)
    source_refs: list[EvidenceRef] = Field(min_length=2, max_length=MAX_REFERENCES)
    confidence: Confidence


class PlanReviewOutput(PlanReviewRecord):
    """New execution results must satisfy the v2 invariants before being accepted."""

    @model_validator(mode="after")
    def consistent_review(self):
        if len({c.constraint_id for c in self.requirement_coverage}) != len(
            self.requirement_coverage
        ):
            raise ValueError("Review coverage identifiers must be unique")
        coverage = {entry.constraint_id: entry for entry in self.requirement_coverage}
        for code, field in (
            ("MISSING_MUST", "missing_requirements"),
            ("FORBIDDEN_VIOLATION", "forbidden_violations"),
        ):
            ids = {issue.constraint_id for issue in self.hard_gate_issues if issue.code == code}
            values = getattr(self, field)
            if None in ids or ids != set(values) or len(values) != len(set(values)):
                raise ValueError(f"{code} and {field} must name the same unique constraint ids")
        for issue in self.hard_gate_issues:
            if issue.code == "MISSING_MUST" or issue.constraint_id is not None:
                entry = coverage.get(issue.constraint_id)
                if entry is None or entry.covered:
                    raise ValueError("Hard constraint failure requires matching uncovered evidence")
        hard_evidence = bool(
            self.hard_gate_issues
            or self.forbidden_violations
            or self.locked_conflicts
            or self.direction_conflicts
            or any(r.impact == "HIGH" for r in self.logic_risks)
        )
        if self.verdict == ReviewVerdict.FAIL and not hard_evidence:
            raise ValueError("FAIL requires hard evidence; quality advice alone cannot fail a Plan")
        if hard_evidence and self.verdict != ReviewVerdict.FAIL:
            raise ValueError("Hard evidence requires FAIL")
        return self


class RequirementAgentResult(AgentResult):
    result: CreativeBriefOutput

    @model_validator(mode="after")
    def consistent_semantic_confidence(self):
        if self.confidence != self.result.confidence:
            raise ValueError("Requirement envelope and Brief confidence must agree")
        return self


class PlanningAgentResult(AgentResult):
    result: ChapterPlanOutput


class PlanReviewAgentResult(AgentResult):
    result: PlanReviewOutput


BUSINESS_RESULTS = {
    "PARSE_CHAPTER_REQUIREMENT": ("chapter-requirement-result", RequirementAgentResult),
    "PLAN_CHAPTER": ("chapter-planning-result", PlanningAgentResult),
    "REVIEW_CHAPTER_PLAN": ("chapter-plan-review-result", PlanReviewAgentResult),
}


def result_model(task_type):
    if task_type == "WRITE_CHAPTER":
        from novel_os.agents.writing_schemas import WritingAgentResult

        return WritingAgentResult
    return BUSINESS_RESULTS[task_type][1] if task_type in BUSINESS_RESULTS else AgentResult


# New review calls use a versioned cross-field contract; persisted v1 reports stay untouched.
BUSINESS_SCHEMA_VERSIONS = {"REVIEW_CHAPTER_PLAN": 2}
