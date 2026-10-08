"""Browser-test host: real routes, migrations and worker; isolated _test schema, Mock only.

Run from backend/. No test control endpoints are added to the application.
"""

import json
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from novel_os.agents.provider import MockModelProvider, ProviderError
from novel_os.agents.runtime import AgentRuntime
from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.main import create_app
from novel_os.worker import AgentWorker

GUARD_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend/.runtime/validation001/browser-provider-guard.json"
)
GUARD_LOCK = threading.Lock()
GUARD = {
    "real_provider_calls": 0,
    "forbidden_provider_attempts": 0,
    "blocked_external_http_attempts": 0,
    "loopback_http_attempts": 0,
    "mock_provider_calls": 0,
    "isolated_test_database": False,
    "keys_removed": False,
    "background_development_worker_started": False,
}


def record_guard(**updates):
    with GUARD_LOCK:
        GUARD.update(updates)
        GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = GUARD_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(GUARD, indent=2) + "\n")
        temporary.replace(GUARD_PATH)


def install_zero_real_provider_guard(settings):
    """Fixture guard only: loopback IO allowed, paid Provider entry always rejected."""
    from novel_os.providers.openai import OpenAIModelProvider

    assert settings.database_url.database.endswith("_test")
    assert settings.agent_model_profile == "mock-default"
    assert settings.openai_api_key is settings.lingzhi_api_key is None
    record_guard(isolated_test_database=True, keys_removed=True, provider="mock")
    sync_http = httpx.HTTPTransport.handle_request
    async_http = httpx.AsyncHTTPTransport.handle_async_request

    def inspect(request):
        if request.url.host not in {"127.0.0.1", "localhost", "::1"}:
            record_guard(blocked_external_http_attempts=GUARD["blocked_external_http_attempts"] + 1)
            raise RuntimeError("Browser fixture blocks non-loopback HTTP transport")
        record_guard(loopback_http_attempts=GUARD["loopback_http_attempts"] + 1)

    def guarded_http(transport, request):
        inspect(request)
        return sync_http(transport, request)

    async def guarded_async_http(transport, request):
        inspect(request)
        return await async_http(transport, request)

    def forbidden_provider(*args, **kwargs):
        record_guard(forbidden_provider_attempts=GUARD["forbidden_provider_attempts"] + 1)
        raise RuntimeError("Real Provider is disabled for browser engineering validation")

    httpx.HTTPTransport.handle_request = guarded_http
    httpx.AsyncHTTPTransport.handle_async_request = guarded_async_http
    OpenAIModelProvider._generate = forbidden_provider


class BrowserTestProvider(MockModelProvider):
    def generate(self, request):
        record_guard(mock_provider_calls=GUARD["mock_provider_calls"] + 1)
        # Test fixture only. The production Mock provider has no marker-based behavior.
        if request.context_package and any(
            "[E2E:MODEL_FAILURE]" in item.payload_json for item in request.context_package.items
        ):
            raise ProviderError("MODEL_AUTH_ERROR")
        if request.output_kind == "chapter_narrative_review" and any(
            "[E2E:REVISION]" in item.payload_json for item in request.context_package.items
        ):
            return MockModelProvider("QUALITY_FAIL").generate(request)
        if request.output_kind == "revision_fidelity" and any(
            "[E2E:FIDELITY_FAIL]" in item.payload_json for item in request.context_package.items
        ):
            return MockModelProvider("QUALITY_FAIL").generate(request)
        time.sleep(0.15)  # Keep queued/running stages observable without slowing the suite.
        response = super().generate(request)
        if request.output_kind == "creative_brief" and any(
            "[E2E:EXPLORATION]" in item.payload_json for item in request.context_package.items
        ):
            from novel_os.providers.base import ModelResponse

            body = json.loads(response.content)
            body["result"]["creative_freedom"].update(
                level="HIGH", allowed_operations=["LOCAL_DETAIL", "LOCAL_CONFLICT"]
            )
            return ModelResponse(json.dumps(body))
        return response


def main():
    settings = (
        Settings.from_file()
        .for_test_database()
        .model_copy(
            update={
                "agent_model_profile": "mock-default",
                "agent_execution_scope": "all",
                "agent_max_attempts": None,
                "openai_api_key": None,
                "lingzhi_api_key": None,
                "log_level": "ERROR",
            }
        )
    )
    install_zero_real_provider_guard(settings)
    admin = Database(settings)
    schema = "console_e2e_" + uuid4().hex
    with admin.engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    options = settings.database_url.query.get("options", "")
    url = settings.database_url.update_query_dict({"options": f"{options} -c search_path={schema}"})
    scoped = settings.model_copy(
        update={"postgres_url": SecretStr(url.render_as_string(hide_password=False))}
    )
    database = Database(scoped)
    stopped = threading.Event()
    worker = AgentWorker(database, AgentRuntime(BrowserTestProvider()), retry_seconds=0)

    def work():
        while not stopped.is_set():
            if not worker.run_once():
                stopped.wait(0.1)

    thread = threading.Thread(target=work, daemon=True)
    try:
        config = Config("alembic.ini")
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        thread.start()
        uvicorn.run(create_app(scoped), host="127.0.0.1", port=8011, log_level="warning")
    finally:
        stopped.set()
        if thread.is_alive():
            thread.join()
        database.dispose()
        with admin.engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


if __name__ == "__main__":
    main()
