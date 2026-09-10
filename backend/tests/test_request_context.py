import asyncio
import json
import logging
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novel_os.core.logging import JsonFormatter, configure_logging, request_id_context


@pytest.mark.parametrize("request_id", ["trace_123.A-b", "x" * 128])
def test_valid_request_id_is_preserved(client: TestClient, request_id: str) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})
    assert response.headers["x-request-id"] == request_id


@pytest.mark.parametrize("request_id", ["", "x" * 129, "has spaces", "bad\tvalue"])
def test_invalid_request_id_is_replaced(client: TestClient, request_id: str) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})
    assert UUID(response.headers["x-request-id"]).version == 4


def test_duplicate_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health", headers=[("X-Request-ID", "one"), ("X-Request-ID", "two")]
    )
    assert UUID(response.headers["x-request-id"]).version == 4


def test_concurrent_requests_have_isolated_context(app: FastAPI) -> None:
    @app.get("/_test/context")
    async def context() -> dict[str, str | None]:
        await asyncio.sleep(0.01)
        return {"request_id": request_id_context.get()}

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.get("/_test/context", headers={"X-Request-ID": f"id-{i}"})
                    for i in range(8)
                )
            )
        for i, response in enumerate(responses):
            assert response.json() == {"request_id": f"id-{i}"}
            assert response.headers["x-request-id"] == f"id-{i}"
        assert request_id_context.get() is None

    asyncio.run(exercise())


def test_access_log_is_correlated_without_query_values(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    client.get("/api/v1/health?token=private-query", headers={"X-Request-ID": "log-id"})
    record = next(record for record in caplog.records if record.message == "request_completed")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "log-id"
    assert payload["status_code"] == 200
    assert payload["path"] == "/api/v1/health"
    assert payload["duration_ms"] >= 0
    assert "private-query" not in json.dumps(payload)


def test_json_logging_includes_context_and_omits_exception_message() -> None:
    token = request_id_context.set("context-id")
    try:
        exception = RuntimeError("private-exception")
        record = logging.LogRecord(
            "novel_os.test",
            logging.ERROR,
            __file__,
            1,
            "failure",
            (),
            (RuntimeError, exception, None),
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)
    assert payload["request_id"] == "context-id"
    assert payload["error_type"] == "RuntimeError"
    assert "private-exception" not in json.dumps(payload)


def test_logging_configuration_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    handlers = [h for h in logging.getLogger().handlers if h.get_name() == "novel_os_json"]
    assert len(handlers) == 1
