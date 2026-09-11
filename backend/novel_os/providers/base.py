from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from novel_os.prompts.compiler import CompiledPrompt
from novel_os.providers.profiles import ModelProfile


class ModelCapability(StrEnum):
    TEXT = "text"
    STRUCTURED_OUTPUT = "structured_output"
    STREAM = "stream"
    COUNT_TOKENS = "count_tokens"


ERROR_RETRYABLE = {
    "MODEL_AUTH_ERROR": False,
    "MODEL_RATE_LIMIT": True,
    "MODEL_TIMEOUT": True,
    "MODEL_UNAVAILABLE": True,
    "MODEL_INVALID_REQUEST": False,
    "MODEL_CONTEXT_LIMIT": False,
    "MODEL_OUTPUT_INVALID": True,
    "MODEL_CONTENT_BLOCKED": False,
    # Unknown provider errors are terminal; only known transient categories retry.
    "MODEL_PROVIDER_ERROR": False,
}


class ProviderError(Exception):
    def __init__(self, code="MODEL_UNAVAILABLE"):
        self.code = code if code in ERROR_RETRYABLE else "MODEL_PROVIDER_ERROR"
        self.retryable = ERROR_RETRYABLE[self.code]
        super().__init__(self.code)


@dataclass(frozen=True)
class ModelRequest:
    task_id: UUID
    task_type: str
    attempt_number: int
    target_ref: UUID
    output_kind: str
    prompt: CompiledPrompt
    profile: ModelProfile


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelResponse:
    content: str
    provider: str = "mock"
    model: str = "mock-v1"
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    latency_ms: int = 0
    # Transport may retain explicitly safe metadata in memory. Never persisted wholesale.
    metadata: dict = field(default_factory=dict, repr=False)

    def safe_summary(self):
        values = (self.usage.input_tokens, self.usage.output_tokens, self.usage.total_tokens)
        return {
            "usage": {
                name: value if type(value) is int and 0 <= value <= 10**9 else None
                for name, value in zip(
                    ("input_tokens", "output_tokens", "total_tokens"), values, strict=True
                )
            },
            "latency_ms": self.latency_ms
            if type(self.latency_ms) is int and 0 <= self.latency_ms <= 10**9
            else None,
            "finish_reason": self.finish_reason
            if isinstance(self.finish_reason, str)
            and self.finish_reason in {"stop", "length", "refusal"}
            else "unknown",
        }


class ModelProvider(ABC):
    provider_id = "mock"

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Untrusted output, always subject to the caller's local schema validation."""

    def get_capabilities(self) -> frozenset[ModelCapability]:
        return frozenset({ModelCapability.TEXT})

    def generate_structured(self, request: ModelRequest) -> ModelResponse:
        raise ProviderError("MODEL_INVALID_REQUEST")

    def stream(self, request: ModelRequest):
        raise ProviderError("MODEL_INVALID_REQUEST")

    def count_tokens(self, request: ModelRequest):
        raise ProviderError("MODEL_INVALID_REQUEST")


class DefaultAdapter:
    """Provider-neutral dispatch; unsupported capabilities fail before any network call."""

    def generate(self, provider: ModelProvider, request: ModelRequest) -> ModelResponse:
        capabilities = provider.get_capabilities()
        if (
            provider.provider_id != request.profile.provider
            or not set(request.profile.capabilities) <= capabilities
        ):
            raise ProviderError("MODEL_INVALID_REQUEST")
        if request.profile.structured_output:
            if ModelCapability.STRUCTURED_OUTPUT not in capabilities:
                raise ProviderError("MODEL_INVALID_REQUEST")
            return provider.generate_structured(request)
        return provider.generate(request)
