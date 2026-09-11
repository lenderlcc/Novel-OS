"""Untrusted provider output contracts. Every object rejects extra fields."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from novel_os.domain.agents import Capability, ResultStatus


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def validate_artifact_text(value: str) -> str:
    if not value.strip() or "\x00" in value:
        raise ValueError("Artifact text must be nonblank and contain no NUL characters")
    # Validate without stripping intentional whitespace or changing paragraph layout.
    return value


ArtifactText = Annotated[str, AfterValidator(validate_artifact_text)]


class Acknowledgement(StrictOutput):
    kind: Literal["ack"]
    simulation: Literal[True]


class PlanOutput(StrictOutput):
    kind: Literal["plan"]
    objective: ArtifactText = Field(min_length=1, max_length=2000)
    required_outcome: ArtifactText = Field(min_length=1, max_length=2000)


class DraftOutput(StrictOutput):
    kind: Literal["draft"]
    content: ArtifactText = Field(min_length=1, max_length=100_000)
    change_reason: ArtifactText = Field(min_length=1, max_length=2000)


class ReviewOutput(StrictOutput):
    kind: Literal["review"]
    verdict: Literal["PASS", "FAIL", "WARN"]


class Proposal(StrictOutput):
    capability: Capability
    target_ref: UUID


class Issue(StrictOutput):
    code: str = Field(pattern=r"^[A-Z][A-Z_]{0,63}$")
    severity: Literal["INFO", "WARNING", "ERROR"]
    description: str = Field(max_length=2000)


class Escalation(StrictOutput):
    required: bool
    reason: str = Field(max_length=2000)


ResultPayload = Annotated[
    Acknowledgement | PlanOutput | DraftOutput | ReviewOutput, Field(discriminator="kind")
]


class AgentResult(StrictOutput):
    task_id: UUID
    status: ResultStatus
    result: ResultPayload | None
    confidence: float = Field(ge=0, le=1)
    assumptions: list[str] = Field(max_length=20)
    issues: list[Issue] = Field(max_length=20)
    proposed_changes: list[Proposal] = Field(max_length=20)
    memory_proposals: list[Proposal] = Field(max_length=20)
    escalation: Escalation | None
