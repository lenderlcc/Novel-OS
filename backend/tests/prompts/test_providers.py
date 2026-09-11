import json
import logging
from dataclasses import replace

import httpx
import pytest
from pydantic import SecretStr

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import (
    ERROR_RETRYABLE,
    DefaultAdapter,
    ModelResponse,
    ProviderError,
    TokenUsage,
)
from novel_os.providers.openai import OpenAIAdapter, OpenAIModelProvider, native_schema
from novel_os.providers.profiles import ModelProfileRegistry


def response_body(content):
    return {
        "status": "completed",
        "id": "untrusted-id-not-persisted",
        "model": "untrusted-echo",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}],
        "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
    }


def test_same_agent_runtime_with_openai_wire_adapter_and_mock(prompt_task):
    mock = MockModelProvider()
    local = AgentRuntime(mock)
    request = local.prepare(prompt_task)
    expected = mock.generate(request)
    captured = []

    def handler(http_request):
        payload = json.loads(http_request.content)
        captured.append(payload)
        assert str(http_request.url) == "https://api.openai.com/v1/responses"
        assert http_request.headers["authorization"] == "Bearer test-key"
        assert payload["store"] is False
        assert payload["stream"] is False
        assert payload["text"]["format"]["strict"] is True
        assert payload["input"] == [
            {"role": m.role, "content": m.content} for m in request.prompt.messages
        ]
        assert payload["text"]["format"]["schema"] == native_schema(
            json.loads(request.prompt.output.schema_json)
        )
        return httpx.Response(200, json=response_body(expected.content))

    provider = OpenAIModelProvider(SecretStr("test-key"), transport=httpx.MockTransport(handler))
    runtime = AgentRuntime(
        provider, tasks=TaskDefinitionRegistry(model_profile="openai-structured")
    )
    execution = runtime.execute(prompt_task)
    assert len(captured) == 1
    assert execution.error_code is None
    assert execution.result == local.execute(prompt_task).result
    assert execution.model_metadata["usage"] == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }


@pytest.mark.parametrize(
    "content,error",
    [
        ("{broken", "FORMAT_ERROR"),
        ('{"next_event":"APPROVED"}', "SCHEMA_PARSE_ERROR"),
        ('{"status":1,"status":2}', "FORMAT_ERROR"),
    ],
)
def test_native_structured_output_still_locally_validated(prompt_task, content, error):
    provider = OpenAIModelProvider(
        SecretStr("test-key"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response_body(content))),
    )
    result = AgentRuntime(
        provider, tasks=TaskDefinitionRegistry(model_profile="openai-structured")
    ).execute(prompt_task)
    assert result.error_code == error
    assert result.retryable


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (401, None, "MODEL_AUTH_ERROR"),
        (403, None, "MODEL_AUTH_ERROR"),
        (429, None, "MODEL_RATE_LIMIT"),
        (408, None, "MODEL_TIMEOUT"),
        (500, None, "MODEL_UNAVAILABLE"),
        (503, None, "MODEL_UNAVAILABLE"),
        (200, "server_error", "MODEL_UNAVAILABLE"),
        (200, "rate_limit_exceeded", "MODEL_RATE_LIMIT"),
        (400, None, "MODEL_INVALID_REQUEST"),
        (400, "context_length_exceeded", "MODEL_CONTEXT_LIMIT"),
        (400, "content_policy_violation", "MODEL_CONTENT_BLOCKED"),
        (429, "insufficient_quota", "MODEL_INVALID_REQUEST"),
        (302, None, "MODEL_PROVIDER_ERROR"),
    ],
)
def test_http_errors_normalized_without_raw_messages(prepared, status, code, expected):
    secret = "sk-test-secret-never-expose"
    provider = OpenAIModelProvider(
        SecretStr(secret),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                status,
                json={"error": {"code": code, "message": secret}},
                headers={"x-secret-echo": secret},
            )
        ),
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate_structured(
            replace(prepared, profile=ModelProfileRegistry().get("openai-structured"))
        )
    assert exc.value.code == expected
    assert exc.value.retryable is ERROR_RETRYABLE[expected]
    assert secret not in str(exc.value)


@pytest.mark.parametrize(
    "error,expected",
    [(httpx.ReadTimeout, "MODEL_TIMEOUT"), (httpx.ConnectError, "MODEL_UNAVAILABLE")],
)
def test_transport_errors_normalized(prepared, error, expected):
    def handler(request):
        raise error("secret request data", request=request)

    provider = OpenAIModelProvider(SecretStr("key"), transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as exc:
        provider.generate(prepared)
    assert exc.value.code == expected
    assert exc.value.retryable


@pytest.mark.parametrize(
    "body,error",
    [
        (
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
            "MODEL_CONTENT_BLOCKED",
        ),
        (
            {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
            "MODEL_OUTPUT_INVALID",
        ),
        (
            {"status": "incomplete", "incomplete_details": {"reason": "content_filter"}},
            "MODEL_CONTENT_BLOCKED",
        ),
        ({"status": "failed"}, "MODEL_PROVIDER_ERROR"),
        ({"status": "completed", "output": []}, "MODEL_OUTPUT_INVALID"),
        ([], "MODEL_OUTPUT_INVALID"),
    ],
)
def test_finish_and_malformed_response_errors(prepared, body, error):
    with pytest.raises(ProviderError) as exc:
        OpenAIAdapter.response(body, prepared, 10)
    assert exc.value.code == error


def test_missing_key_is_nonretryable_and_does_not_send(prepared):
    with pytest.raises(ProviderError) as exc:
        OpenAIModelProvider(None).generate(prepared)
    assert exc.value.code == "MODEL_AUTH_ERROR"
    assert not exc.value.retryable


def test_profiles_and_unsupported_capability(prepared):
    profiles = ModelProfileRegistry()
    assert profiles.get("mock-default").model == "mock-v1"
    assert profiles.get("openai-structured").structured_output
    unsupported = replace(prepared, profile=profiles.get("openai-structured"))
    with pytest.raises(ProviderError) as exc:
        DefaultAdapter().generate(MockModelProvider(), unsupported)
    assert exc.value.code == "MODEL_INVALID_REQUEST"
    for method in ("stream", "count_tokens", "generate_structured"):
        with pytest.raises(ProviderError) as exc:
            getattr(MockModelProvider(), method)(prepared)
        assert not exc.value.retryable


def test_mock_receives_compilation_and_schema_before_generating(prompt_task):
    class InspectingMock(MockModelProvider):
        def generate(self, request):
            assert request.prompt.compiled_hash
            assert request.prompt.output.model.__name__ == "AgentResult"
            assert request.prompt.messages[-2].layer == "CONTEXT_DATA"
            return super().generate(request)

    execution = AgentRuntime(InspectingMock("MALFORMED_OUTPUT")).execute(prompt_task)
    assert execution.error_code == "SCHEMA_PARSE_ERROR"


def test_provider_arbitrary_metadata_never_used_as_safe_summary():
    response = ModelResponse(
        "private content",
        metadata={"Authorization": "sk-test"},
        provider="sk-test",
        model="sk-test",
        usage=TokenUsage("sk-test", -1, True),
        finish_reason=["sk-test"],
        latency_ms="sk-test",
    )
    assert response.safe_summary() == {
        "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        "finish_reason": "unknown",
        "latency_ms": None,
    }


def test_provider_secret_absent_from_debug_logs(prepared, caplog):
    secret = "sk-credential-secret-logger-test"
    caplog.set_level(logging.DEBUG)
    provider = OpenAIModelProvider(
        SecretStr(secret),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                401, json={"error": {"message": secret}}, headers={"authorization": secret}
            )
        ),
    )
    with pytest.raises(ProviderError):
        provider.generate(prepared)
    assert secret not in caplog.text
    assert secret not in repr(provider)


def test_smoke_demo_returns_requirement_spec_without_workflow():
    result = AgentRuntime(MockModelProvider()).execute_smoke("A short hopeful story")
    assert result.error_code is None
    assert result.result.result.kind == "requirement_demo"
    assert result.result.proposed_changes == []
    assert result.result.result.simulation is True


@pytest.mark.live_model
def test_live_openai_smoke_is_explicit_opt_in(request):
    if not request.config.getoption("--live-model"):
        pytest.skip("Real provider disabled; opt in with --live-model")
    from novel_os.core.config import Settings

    settings = Settings.from_file()
    if settings.openai_api_key is None:
        pytest.skip("No OpenAI credential configured in TOML")
    runtime = AgentRuntime(
        OpenAIModelProvider(settings.openai_api_key),
        tasks=TaskDefinitionRegistry(model_profile="openai-structured"),
    )
    result = runtime.execute_smoke("A short hopeful story set beside the sea.")
    assert result.error_code is None
    assert result.result.result.kind == "requirement_demo"


def test_bounded_provider_body_and_debug_headers(prepared, caplog):
    from novel_os.core.logging import configure_logging

    configure_logging("DEBUG")
    secret = "sk-fake-provider-reason-phrase"
    provider = OpenAIModelProvider(
        SecretStr(secret),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=b"x" * 2_000_001, extensions={"reason_phrase": secret.encode()}
            )
        ),
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate(prepared)
    assert exc.value.code == "MODEL_OUTPUT_INVALID"
    assert secret not in caplog.text


def test_wrong_provider_profile_fails_before_network(prompt_task):
    provider = OpenAIModelProvider(
        SecretStr("unused"),
        transport=httpx.MockTransport(
            lambda _: pytest.fail("Wrong provider/profile must not call network")
        ),
    )
    assert AgentRuntime(provider).execute(prompt_task).error_code == "MODEL_INVALID_REQUEST"
