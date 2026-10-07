"""A02 output is a sparse draft, never an approved character or a Canon mutation."""

from typing import Literal

from pydantic import Field

from novel_os.agents.schemas import AgentResult, StrictOutput
from novel_os.characters.schemas import CharacterBehaviorProfileBody


class CharacterProfileDraftOutput(StrictOutput):
    kind: Literal["character_profile_draft"]
    profile: CharacterBehaviorProfileBody


class CharacterProfileAgentResult(AgentResult):
    result: CharacterProfileDraftOutput | None
    proposed_changes: list = Field(default_factory=list, max_length=0)
    memory_proposals: list = Field(default_factory=list, max_length=0)
