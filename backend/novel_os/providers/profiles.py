import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field

from novel_os.prompts.contracts import (
    FrozenModel,
    Identifier,
    PromptConfigurationError,
    canonical,
    digest,
)


class GenerationParameters(FrozenModel):
    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)


class ModelProfile(FrozenModel):
    profile_id: Identifier
    provider: Literal["mock", "openai"]
    model: Identifier
    capabilities: tuple[Literal["text", "structured_output", "stream", "count_tokens"], ...]
    structured_output: bool
    stream_support: bool
    timeout_seconds: float = Field(gt=0, le=300, allow_inf_nan=False)
    max_output_tokens: int = Field(strict=True, ge=16, le=100_000)
    generation: GenerationParameters

    @property
    def profile_hash(self):
        return digest(canonical(self.model_dump(mode="json")))


class ModelProfileRegistry:
    def __init__(self, path: Path | None = None):
        try:
            with (path or Path(__file__).with_name("profiles.toml")).open("rb") as handle:
                document = tomllib.load(handle)
            if set(document) != {"profiles"}:
                raise ValueError
            self._profiles = {}
            for entry in document["profiles"]:
                profile = ModelProfile.model_validate(entry)
                if profile.profile_id in self._profiles:
                    raise ValueError
                if profile.structured_output != (
                    "structured_output" in profile.capabilities
                ) or profile.stream_support != ("stream" in profile.capabilities):
                    raise ValueError
                self._profiles[profile.profile_id] = profile
        except (ValueError, TypeError, OSError):
            raise PromptConfigurationError("Invalid model profile configuration") from None

    def get(self, profile_id: str):
        try:
            return self._profiles[profile_id]
        except KeyError:
            raise PromptConfigurationError("Unknown model profile") from None
