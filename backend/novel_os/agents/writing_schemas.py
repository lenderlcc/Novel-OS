"""Single source for the generated Writing output contract and validation."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from novel_os.agents.schemas import AgentResult, ArtifactText, StrictOutput
from novel_os.domain.writing import DeviationSeverity

Text = Annotated[ArtifactText, Field(max_length=2000)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class SceneExecution(StrictOutput):
    scene_id: Text
    planned_function: Text
    execution_summary: Text
    source_location: Text
    function_completed: bool = Field(strict=True)
    deviation: Text | None


class PlanDeviation(StrictOutput):
    type: Literal[
        "LOCAL_EXECUTION",
        "SCENE_FUNCTION",
        "REQUIRED_OUTCOME",
        "ENDING_DIRECTION",
        "MAJOR_DIRECTION",
        "LOCKED_DECISION",
        "CORE_CHARACTER",
        "WORLD_RULE",
        "FUTURE_STRUCTURE",
        "FORBIDDEN_CONSTRAINT",
    ]
    location: Text
    planned_behavior: Text
    actual_behavior: Text
    reason: Text
    impact: Text
    severity: DeviationSeverity
    requires_replan: bool = Field(strict=True)
    confidence: Confidence


class ProposedFact(StrictOutput):
    fact: Text
    scope: Text
    importance: Literal["MINOR", "SUPPORTING", "MAJOR"]
    reason: Text
    source_location: Text
    confidence: Confidence


class IntroducedElement(StrictOutput):
    description: Text
    scope: Literal["LOCAL", "SUPPORTING", "MAJOR"]
    source_location: Text


class KnowledgeRisk(StrictOutput):
    character_ref: Text | None
    fact: Text
    knowledge_type: Literal[
        "GLOBAL_ONLY", "KNOWLEDGE", "BELIEF", "SUSPICION", "MISUNDERSTANDING", "UNKNOWN"
    ]
    source_location: Text
    risk: Text
    confirmed_leak: bool = Field(strict=True)


class WritingMetadata(StrictOutput):
    kind: Literal["writing_result"]
    chapter_id: UUID
    plan_id: UUID
    plan_version: int = Field(strict=True, gt=0)
    scene_execution: list[SceneExecution] = Field(min_length=1, max_length=100)
    introduced_elements: list[IntroducedElement] = Field(max_length=100)
    proposed_new_facts: list[ProposedFact] = Field(max_length=100)
    plan_deviations: list[PlanDeviation] = Field(max_length=100)
    unresolved_questions: list[Text] = Field(max_length=50)
    assumptions: list[Text] = Field(max_length=50)
    knowledge_risk_flags: list[KnowledgeRisk] = Field(max_length=50)
    style_notes: list[Text] = Field(max_length=50)
    confidence: Confidence

    @model_validator(mode="after")
    def unique_scenes(self):
        if len({s.scene_id for s in self.scene_execution}) != len(self.scene_execution):
            raise ValueError("Scene execution identifiers must be unique")
        return self


class WritingResult(WritingMetadata):
    content: ArtifactText = Field(min_length=1, max_length=100_000)


class WritingAgentResult(AgentResult):
    result: WritingResult
