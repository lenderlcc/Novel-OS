"""Runtime smoke contract only; no CreativeBrief, Requirement persistence or workflow."""

from typing import Literal

from pydantic import Field

from novel_os.agents.schemas import AgentResult, ArtifactText, StrictOutput


class RequirementSpec(StrictOutput):
    kind: Literal["requirement_demo"]
    summary: ArtifactText = Field(min_length=1, max_length=2000)
    explicit_constraints: list[ArtifactText] = Field(max_length=20)
    simulation: Literal[True]


class SmokeAgentResult(AgentResult):
    result: RequirementSpec | None
