import json
from dataclasses import replace

import httpx
import pytest
from pydantic import SecretStr

from novel_os.core.config import Settings
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import DefaultAdapter, ProviderError
from novel_os.providers.openai import LingzhiModelProvider, OpenAIAdapter, OpenAIModelProvider
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.runtime_factory import build_agent_runtime, build_model_provider
from tests.prompts.test_providers import response_body


def settings():
    return Settings(
        postgres_url=SecretStr("postgresql+psycopg://u:p@localhost/novel_test"),
        openai_api_key=SecretStr("official-test-key"),
        lingzhi_api_key=SecretStr("gateway-test-key"),
        requirement_smoke_profile="lingzhi-requirement",
    )


def test_lingzhi_responses_wire_and_identity(prepared):
    calls = []
    profile = ModelProfileRegistry().get("lingzhi-requirement")

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://lingzhi.agibot.com/v1/responses"
        assert request.headers["authorization"] == "Bearer gateway-test-key"
        body = json.loads(request.content)
        assert body["model"] == "gpt-5.6-sol"
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["strict"] is True
        assert body["store"] is body["stream"] is False
        assert "temperature" not in body
        assert body["max_output_tokens"] == 8192
        return httpx.Response(200, json=response_body('{"example":true}'))

    provider = LingzhiModelProvider(
        settings().lingzhi_api_key,
        base_url=settings().lingzhi_base_url,
        transport=httpx.MockTransport(handler),
    )
    response = DefaultAdapter().generate(provider, replace(prepared, profile=profile))
    assert len(calls) == 1
    assert response.provider == "lingzhi" and response.model == "gpt-5.6-sol"
    assert response.content == '{"example":true}'
    assert response.usage.total_tokens == 20


def test_file_selection_does_not_enable_paid_worker_or_cross_credentials():
    config = settings()
    assert build_agent_runtime(config).provider.provider_id == "mock"
    gateway = build_agent_runtime(config, model_profile=config.requirement_smoke_profile)
    assert gateway.provider.provider_id == "lingzhi"
    assert gateway.profile_for_task("PARSE_CHAPTER_REQUIREMENT").model == "gpt-5.6-sol"
    registry = ModelProfileRegistry()
    assert isinstance(
        build_model_provider(config, registry.get("openai-structured")), OpenAIModelProvider
    )
    no_gateway_key = config.model_copy(update={"lingzhi_api_key": None})
    provider = build_model_provider(no_gateway_key, registry.get("lingzhi-requirement"))
    with pytest.raises(ProviderError, match="MODEL_AUTH_ERROR"):
        provider.generate(None)  # Must not fall back to the configured OpenAI credential.


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_gateway_errors_never_redirect_or_retry(prepared, status):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, headers={"location": "https://example.com/steal"})

    provider = LingzhiModelProvider(SecretStr("dummy"), transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        provider.generate(prepared)
    assert calls == ["https://lingzhi.agibot.com/v1/responses"]


def test_gateway_origin_cannot_be_rebound_to_another_provider():
    with pytest.raises(ProviderError, match="MODEL_INVALID_REQUEST"):
        LingzhiModelProvider(SecretStr("dummy"), base_url="https://api.openai.com/v1")


def test_existing_profile_hashes_and_sampling_remain_compatible(prepared):
    profiles = ModelProfileRegistry()
    # Baselines captured from HEAD before adding Lingzhi; historical lineage must resolve.
    hashes = {
        "lingzhi-requirement": "91b8069edec67c0b92de2903bf3226bc8a8318f046860acfa235f9f2626b0e49",
        "mock-default": "20a9b51392e4f4f14867693c836ddccda34b63425db3d6e99f87b2048e14d94d",
        "openai-structured": "4cac70033a20a8d13e37fe5de9c1d76605784d77434ecdff130c03d097b63e46",
        "mock-writing": "ef0752cf4f225a7b3df54823ef753ce335f6137d89a9a8c418c16691a3ffbade",
        "openai-writing": "2e4dc588333e51795288bc6ab46701b532348180eb09dfd51f1be7ef43972413",
    }
    for name, expected_hash in hashes.items():
        profile = profiles.get(name)
        snapshot = profile.model_dump(mode="json")
        temperature = None if name == "lingzhi-requirement" else 0.2
        assert snapshot["generation"] == {"temperature": temperature}
        assert profile.profile_hash == expected_hash
        assert (
            OpenAIAdapter.request(replace(prepared, profile=profile), structured=True).get(
                "temperature"
            )
            == temperature
        )


@pytest.mark.parametrize(
    "task_type",
    ["PARSE_CHAPTER_REQUIREMENT", "PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN", "WRITE_CHAPTER"],
)
def test_full_workflow_profile_uses_lingzhi_for_every_business_stage(task_type, prepared):
    config = Settings(
        postgres_url="postgresql+psycopg://u:p@localhost/novel_test",
        agent_model_profile="lingzhi-structured",
        agent_execution_scope="chapter-writing",
        agent_max_attempts=1,
        lingzhi_api_key="gateway-test-key",
    )
    runtime = build_agent_runtime(config)
    definition = runtime.prompts.tasks.get(task_type)
    profile = runtime.profile_for_task(task_type)
    assert task_type in config.agent_task_types and config.agent_max_attempts == 1
    assert runtime.provider.provider_id == profile.provider == "lingzhi"
    assert profile.profile_id == definition.model_profile == "lingzhi-structured"
    assert profile.model == "gpt-5.6-sol"
    assert profile.timeout_seconds == 300 and profile.max_output_tokens == 8192
    request = replace(prepared, profile=profile, task_type=task_type)
    request = replace(request, prompt=replace(request.prompt, output=definition.output_schema))
    calls = []

    def handler(http_request):
        calls.append(http_request)
        assert str(http_request.url) == "https://lingzhi.agibot.com/v1/responses"
        body = json.loads(http_request.content)
        assert (
            body["text"]["format"]["schema"]
            == OpenAIAdapter.request(request, structured=True)["text"]["format"]["schema"]
        )
        assert body["model"] == "gpt-5.6-sol" and body["max_output_tokens"] == 8192
        assert "temperature" not in body
        return httpx.Response(200, json=response_body('{"wire_only":true}'))

    provider = LingzhiModelProvider(config.lingzhi_api_key, transport=httpx.MockTransport(handler))
    assert DefaultAdapter().generate(provider, request).provider == "lingzhi"
    assert len(calls) == 1


def test_planning_literal_contract_selects_new_prompt_without_rewriting_old_lineage():
    registry = PromptRegistry()
    definition = TaskDefinitionRegistry(model_profile="lingzhi-structured").get("PLAN_CHAPTER")
    selected = {item.module.module_id: item for item in definition.resolve(registry)}
    assert selected["plan-chapter"].module.version == 10
    old = registry.resolve(ModuleRef(module_id="plan-chapter", version=1))
    assert (
        old.module.content_hash
        == "5578650e5e4349bc1b460806d9e4635fb6a80d4cbafc1464a171b268a2e61af3"
    )


def test_review_contract_and_prompt_are_versioned_without_overwriting_old_prompt():
    registry = PromptRegistry()
    definition = TaskDefinitionRegistry().get("REVIEW_CHAPTER_PLAN")
    assert definition.output_schema.version == 3
    selected = {item.module.module_id: item for item in definition.resolve(registry)}
    assert selected["review-chapter-plan"].module.version == 6
    assert registry.resolve(ModuleRef(module_id="plan-chapter", version=2)).module.content_hash == (
        "9987241d0d79a898ac7ec1447d5bbbd3806a53dd2aae9a67942acae476a13993"
    )
    assert registry.resolve(
        ModuleRef(module_id="review-chapter-plan", version=1)
    ).module.content_hash == ("f0da11ab8d40e3ce2b112b0707ea60edd9203dad5952d84ea7b7acd997389835")
