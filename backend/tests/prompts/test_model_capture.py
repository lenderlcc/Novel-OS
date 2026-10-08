import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from novel_os.core.config import Settings
from novel_os.infrastructure.model_capture import CapturingModelProvider
from novel_os.providers.base import ModelProvider, ModelResponse, ProviderError
from novel_os.runtime_factory import build_agent_runtime


class RecordedResponse(ModelProvider):
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return self.response

    def generate_structured(self, request):
        return self.generate(request)


def test_capture_preserves_invalid_output_before_parser_and_keeps_it_private(prepared, tmp_path):
    response = ModelResponse('{"unexpected":"private story"}', metadata={"authorization": "secret"})
    inner = RecordedResponse(response)
    directory = tmp_path / "capture"
    provider = CapturingModelProvider(inner, directory)
    assert provider.generate_structured(prepared) is response
    with pytest.raises(ValidationError):
        prepared.prompt.output.parse(response.content)
    path = next(directory.iterdir())
    saved = json.loads(path.read_text())
    assert saved["output"] == response.content
    assert saved["task_id"] == str(prepared.task_id)
    assert saved["schema_hash"] == prepared.prompt.output.schema_hash
    assert saved["compiled_prompt_hash"] == prepared.prompt.compiled_hash
    assert "secret" not in path.read_text() and "authorization" not in path.read_text()
    assert directory.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert inner.calls == 1


def test_capture_failure_never_causes_provider_retry_or_overwrites_old_evidence(prepared, tmp_path):
    inner = RecordedResponse(ModelResponse("first"))
    provider = CapturingModelProvider(inner, tmp_path / "capture")
    provider.generate(prepared)
    first = next(provider.directory.iterdir()).read_bytes()
    inner.response = ModelResponse("second")
    assert provider.generate(prepared) is inner.response
    assert next(provider.directory.iterdir()).read_bytes() == first
    provider.generate(replace(prepared, attempt_number=prepared.attempt_number + 1))
    assert len(list(provider.directory.iterdir())) == 2
    assert inner.calls == 3


def test_provider_errors_are_not_captured_or_retried(prepared, tmp_path):
    class FailedProvider(RecordedResponse):
        def generate(self, request):
            self.calls += 1
            raise ProviderError("MODEL_AUTH_ERROR")

    inner = FailedProvider(None)
    provider = CapturingModelProvider(inner, tmp_path / "capture")
    with pytest.raises(ProviderError):
        provider.generate(prepared)
    assert inner.calls == 1 and not list(provider.directory.iterdir())


def test_record_building_and_logging_failure_preserve_response(prepared, tmp_path, monkeypatch):
    def broken_summary(self):
        raise RuntimeError("diagnostic summary unavailable")

    def broken_log(*args, **kwargs):
        raise RuntimeError("diagnostic log unavailable")

    inner = RecordedResponse(ModelResponse("original response"))
    provider = CapturingModelProvider(inner, tmp_path / "capture")
    monkeypatch.setattr(ModelResponse, "safe_summary", broken_summary)
    monkeypatch.setattr("novel_os.infrastructure.model_capture.logger.warning", broken_log)
    assert provider.generate(prepared) is inner.response
    assert inner.calls == 1 and not list(provider.directory.iterdir())


def test_runtime_capture_is_opt_in_and_initialization_does_not_call_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inner = RecordedResponse(ModelResponse("unused"))
    monkeypatch.setattr("novel_os.runtime_factory.build_model_provider", lambda *args: inner)
    settings = Settings(postgres_url="postgresql+psycopg://u:p@localhost/novel_test")
    assert build_agent_runtime(settings).provider is inner
    assert not (tmp_path / ".runtime").exists()
    enabled = settings.model_copy(update={"agent_capture_outputs": True})
    provider = build_agent_runtime(enabled).provider
    assert isinstance(provider, CapturingModelProvider)
    assert provider.provider is inner and inner.calls == 0
    assert not list(provider.directory.iterdir())


def test_capture_directory_failure_does_not_prevent_worker_runtime(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    inner = RecordedResponse(ModelResponse("unused"))
    monkeypatch.setattr("novel_os.runtime_factory.build_model_provider", lambda *args: inner)

    def denied(*args, **kwargs):
        raise PermissionError("read-only runtime directory")

    monkeypatch.setattr("novel_os.runtime_factory.CapturingModelProvider", denied)
    settings = Settings(
        postgres_url="postgresql+psycopg://u:p@localhost/novel_test",
        agent_capture_outputs=True,
    )
    runtime = build_agent_runtime(settings)
    assert runtime.provider is inner
    assert "model_output_capture_initialization_failed" in caplog.text
