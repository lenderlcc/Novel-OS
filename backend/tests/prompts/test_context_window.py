from dataclasses import replace
from uuid import uuid4

import pytest

from novel_os.context.engine import ContextEngine
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.context import CandidateBatch, ContextRequest, ContextStatus
from novel_os.prompts.contracts import PromptConfigurationError, canonical
from novel_os.providers.base import (
    DefaultAdapter,
    ModelCapability,
    ModelProvider,
    ModelResponse,
    ProviderError,
)
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.providers.tokens import prompt_overhead
from tests.context.test_context import item, profile


@pytest.fixture
def request_value():
    return ContextRequest(
        project_id=uuid4(), task_id=uuid4(), chapter_id=uuid4(), task_type="TEST_CONTEXT"
    )


class CountingProvider(ModelProvider):
    provider_id = "openai"

    def __init__(self):
        self.calls = 0

    def get_capabilities(self):
        return frozenset({ModelCapability.TEXT, ModelCapability.STRUCTURED_OUTPUT})

    def generate(self, request):
        self.calls += 1
        return ModelResponse("{}")

    def generate_structured(self, request):
        return self.generate(request)


def test_large_p0_blocked_by_model_window_without_rewriting_profile(request_value):
    configured = profile().model_copy(update={"token_budget": 240000})
    evidence = item(request_value, payload_json=canonical({"content": " 𐀀" * 40000}))
    batch = CandidateBatch((evidence,))
    engine = ContextEngine()
    kwargs = dict(prompt_overhead=27500, output_reservation=4096)
    unlimited = engine.build(request_value, configured, batch, **kwargs)
    limited = engine.build(request_value, configured, batch, model_context_window=128000, **kwargs)
    assert unlimited.status == ContextStatus.READY
    assert limited.status == ContextStatus.BLOCKED
    assert limited.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert limited.package.items == unlimited.package.items
    assert limited.package.items[0].payload_json == evidence.payload_json
    assert limited.package.token_budget == 128000
    assert limited.package.profile_json == unlimited.package.profile_json
    assert limited.package.profile_hash == configured.profile_hash
    restored = ContextSerializer.restore(ContextSerializer.snapshot(limited.package))
    assert ContextSerializer.hash(restored) == limited.package.package_hash


@pytest.mark.parametrize("window", [None, 1050000])
def test_larger_model_never_increases_context_policy_budget(request_value, window):
    configured = profile().model_copy(update={"token_budget": 240000})
    built = ContextEngine().build(
        request_value,
        configured,
        CandidateBatch((item(request_value),)),
        model_context_window=window,
    )
    assert built.status == ContextStatus.READY
    assert built.package.token_budget == 240000


def test_final_prompt_guard_blocks_network_after_context_preflight(prepared):
    model = ModelProfileRegistry().get("openai-structured")
    message = replace(prepared.prompt.messages[-1], content=" 𐀀" * 40000)
    request = replace(
        prepared,
        profile=model,
        prompt=replace(prepared.prompt, messages=(*prepared.prompt.messages[:-1], message)),
    )
    provider = CountingProvider()
    with pytest.raises(ProviderError, match="MODEL_CONTEXT_LIMIT") as error:
        DefaultAdapter().generate(provider, request)
    assert not error.value.retryable
    assert provider.calls == 0


@pytest.mark.parametrize("extra", [0, 1])
def test_total_budget_includes_output_at_exact_boundary(prepared, tmp_path, extra):
    request = replace(prepared, profile=ModelProfileRegistry().get("openai-structured"))
    total = prompt_overhead(request) + request.profile.max_output_tokens
    path = tmp_path / "profiles.toml"
    path.write_text(
        f'profiles = []\n[context_windows.openai]\n"{request.profile.model}" = {total - extra}\n'
    )
    provider = CountingProvider()
    adapter = DefaultAdapter(ModelProfileRegistry(path))
    if extra:
        with pytest.raises(ProviderError, match="MODEL_CONTEXT_LIMIT"):
            adapter.generate(provider, request)
        assert provider.calls == 0
    else:
        adapter.generate(provider, request)
        assert provider.calls == 1


def test_unknown_real_model_fails_closed_before_provider(prepared):
    model = (
        ModelProfileRegistry()
        .get("openai-structured")
        .model_copy(update={"model": "unconfigured-model"})
    )
    provider = CountingProvider()
    with pytest.raises(PromptConfigurationError, match="context window"):
        DefaultAdapter().generate(provider, replace(prepared, profile=model))
    assert provider.calls == 0


@pytest.mark.parametrize("value", ["true", "0", "-1", "128000.0"])
def test_invalid_window_configuration_rejected(tmp_path, value):
    path = tmp_path / "profiles.toml"
    path.write_text(f"profiles = []\n[context_windows.openai]\nmodel = {value}\n")
    with pytest.raises(PromptConfigurationError):
        ModelProfileRegistry(path)
