"""Current Revision wire contracts; published legacy schemas stay replayable."""

from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, Proposal
from novel_os.prompts.contracts import PromptConfigurationError
from novel_os.revision.fidelity_schemas import (
    FidelityAgentResult,
    FidelityPlanAgentResult,
    FidelityRevisionPlan,
    RevisionFidelityOutput,
)
from novel_os.revision.schemas import (
    RevisionAgentResult,
    RevisionPlanAgentResult,
    RevisionResultOutput,
)


class RevisionEnvelope(AgentResult):
    # Kept for envelope compatibility. They are never an operation channel.
    proposed_changes: list[Proposal] = Field(default_factory=list, max_length=0)
    memory_proposals: list[Proposal] = Field(default_factory=list, max_length=0)


class RevisionPlanV3(FidelityRevisionPlan):
    unresolved_issue_ids: list[UUID] = Field(max_length=60)

    @model_validator(mode="after")
    def unresolved_matches_blocked(self):
        blocked = {reason.issue_id for reason in self.blocked_reasons}
        if set(self.unresolved_issue_ids) != blocked or len(self.unresolved_issue_ids) != len(
            blocked
        ):
            raise ValueError("Unresolved issues must match blocked reasons exactly")
        return self


class RevisionPlanResultV3(RevisionEnvelope):
    result: RevisionPlanV3


def read_plan(body):
    model = RevisionPlanV3 if "unresolved_issue_ids" in body else FidelityRevisionPlan
    return model.model_validate(body)


class RevisionResultV2(RevisionEnvelope):
    result: RevisionResultOutput


class FidelityResultV2(RevisionEnvelope):
    result: RevisionFidelityOutput


SCHEMA_VERSIONS = {
    "PLAN_CHAPTER_REVISION": 3,
    "REVISE_CHAPTER": 2,
    "VALIDATE_REVISION_FIDELITY": 2,
}

# Model, task prompt and skill versions for historical replay only.
LEGACY_CONTRACTS = {
    ("PLAN_CHAPTER_REVISION", "chapter-revision-plan.v1"): (RevisionPlanAgentResult, 1, 1),
    ("PLAN_CHAPTER_REVISION", "chapter-revision-plan.v2"): (FidelityPlanAgentResult, 2, 2),
    ("REVISE_CHAPTER", "chapter-revision-result.v1"): (RevisionAgentResult, 2, 2),
    ("VALIDATE_REVISION_FIDELITY", "revision-fidelity-result.v1"): (FidelityAgentResult, 1, 1),
}


def require_current_contract(task_type, schema):
    if (task_type, schema) in LEGACY_CONTRACTS:
        raise PromptConfigurationError(
            "Historical Revision contracts are read-only; start a new current-contract task"
        )
