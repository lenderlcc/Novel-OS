"""OpenAI Responses HTTP adapter. Credentials, native options and errors stay here."""

import json
import time

import httpx
from pydantic import SecretStr

from novel_os.providers.base import (
    ModelCapability,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderError,
    TokenUsage,
)


def native_schema(node):
    """Derive the provider's schema dialect, retaining local Pydantic validation.

    Our oneOfs are Pydantic tagged unions: distinct required literal tags make
    anyOf equivalent. No independently maintained schema or permissive defaults.
    """
    if isinstance(node, list):
        return [native_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key == "discriminator":
            continue
        if key == "oneOf":
            if "discriminator" not in node:
                raise ProviderError("MODEL_INVALID_REQUEST")
            result["anyOf"] = native_schema(value)
        elif key == "const":
            result["enum"] = [value]
        else:
            result[key] = native_schema(value)
    return result


class OpenAIAdapter:
    @staticmethod
    def request(request: ModelRequest, *, structured: bool):
        payload = {
            "model": request.profile.model,
            "input": [
                {"role": message.role, "content": message.content}
                for message in request.prompt.messages
            ],
            "max_output_tokens": request.profile.max_output_tokens,
            "temperature": request.profile.generation.temperature,
            "store": False,
            "stream": False,
        }
        if structured:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "novel_os_result",
                    "strict": True,
                    "schema": native_schema(json.loads(request.prompt.output.schema_json)),
                }
            }
        return payload

    @staticmethod
    def error(status: int, body) -> ProviderError:
        error = body.get("error", {}) if isinstance(body, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        if status in {401, 403}:
            normalized = "MODEL_AUTH_ERROR"
        elif code == "context_length_exceeded":
            normalized = "MODEL_CONTEXT_LIMIT"
        elif code in {"content_filter", "content_policy_violation"}:
            normalized = "MODEL_CONTENT_BLOCKED"
        elif code == "insufficient_quota":
            normalized = "MODEL_INVALID_REQUEST"
        elif status == 429 or code == "rate_limit_exceeded":
            normalized = "MODEL_RATE_LIMIT"
        elif status == 408:
            normalized = "MODEL_TIMEOUT"
        elif status >= 500 or code == "server_error":
            normalized = "MODEL_UNAVAILABLE"
        elif status in {400, 404, 413, 422}:
            normalized = "MODEL_INVALID_REQUEST"
        else:
            normalized = "MODEL_PROVIDER_ERROR"
        return ProviderError(normalized)

    @staticmethod
    def response(body, request, latency_ms):
        try:
            if not isinstance(body, dict):
                raise ValueError
            if body.get("error"):
                raise OpenAIAdapter.error(200, body)
            output = body.get("output", [])
            contents = [
                part
                for item in output
                if item.get("type") == "message"
                for part in item.get("content", [])
            ]
            if any(part.get("type") == "refusal" for part in contents):
                raise ProviderError("MODEL_CONTENT_BLOCKED")
            if body.get("status") == "incomplete":
                details = body.get("incomplete_details") or {}
                raise ProviderError(
                    "MODEL_CONTENT_BLOCKED"
                    if details.get("reason") == "content_filter"
                    else "MODEL_OUTPUT_INVALID"
                )
            if body.get("status") != "completed":
                raise ProviderError("MODEL_PROVIDER_ERROR")
            text = "".join(part["text"] for part in contents if part.get("type") == "output_text")
            if not text:
                raise ValueError
            usage = body.get("usage") or {}
            # Response/header IDs, arbitrary metadata and echoed model names are not trusted.
            return ModelResponse(
                text,
                "openai",
                request.profile.model,
                TokenUsage(
                    *(usage.get(key) for key in ("input_tokens", "output_tokens", "total_tokens"))
                ),
                latency_ms=latency_ms,
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("MODEL_OUTPUT_INVALID") from None


class OpenAIModelProvider(ModelProvider):
    provider_id = "openai"

    def __init__(self, api_key: SecretStr | None, *, transport: httpx.BaseTransport | None = None):
        self._api_key = api_key
        self._transport = transport

    def get_capabilities(self):
        return frozenset({ModelCapability.TEXT, ModelCapability.STRUCTURED_OUTPUT})

    def generate(self, request):
        return self._generate(request, structured=False)

    def generate_structured(self, request):
        return self._generate(request, structured=True)

    def _generate(self, request, *, structured):
        if self._api_key is None or not self._api_key.get_secret_value().strip():
            raise ProviderError("MODEL_AUTH_ERROR")
        payload = OpenAIAdapter.request(request, structured=structured)
        started = time.monotonic()
        try:
            # Fixed endpoint, no redirect/retry, no proxy/environment configuration.
            # Each attempt owns a client and closes it even after timeout or parse failure.
            with (
                httpx.Client(
                    transport=self._transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=request.profile.timeout_seconds,
                ) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/responses",
                    json=payload,
                    headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                ) as response,
            ):
                content = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > request.profile.timeout_seconds:
                        raise ProviderError("MODEL_TIMEOUT")
                    if len(content) + len(chunk) > 2_000_000:
                        raise ProviderError("MODEL_OUTPUT_INVALID")
                    content.extend(chunk)
                try:
                    body = json.loads(content)
                except (ValueError, RecursionError):
                    body = None
                if not response.is_success:
                    raise OpenAIAdapter.error(response.status_code, body)
                return OpenAIAdapter.response(
                    body, request, int((time.monotonic() - started) * 1000)
                )
        except httpx.TimeoutException:
            raise ProviderError("MODEL_TIMEOUT") from None
        except httpx.RequestError:
            raise ProviderError("MODEL_UNAVAILABLE") from None
