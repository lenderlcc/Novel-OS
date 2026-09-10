import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [("get", "/missing", 404, "NOT_FOUND"), ("post", "/api/v1/health", 405, "METHOD_NOT_ALLOWED")],
)
def test_routing_errors_use_envelope(
    client: TestClient, method: str, path: str, status: int, code: str
) -> None:
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    if status == 405:
        assert "GET" in response.headers["allow"]


class ValidationPayload(BaseModel):
    count: int


def test_validation_errors_do_not_echo_inputs(app: FastAPI, client: TestClient) -> None:
    @app.post("/_test/validation")
    def validate(payload: ValidationPayload) -> ValidationPayload:
        return payload

    response = client.post("/_test/validation", json={"count": "private-input"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["request_id"] == response.headers["x-request-id"]
    assert error["details"] == [{"location": ["body", "count"], "type": "int_parsing"}]
    assert "private-input" not in response.text


def test_http_error_preserves_required_headers(app: FastAPI, client: TestClient) -> None:
    @app.get("/_test/http-error")
    def fail() -> None:
        raise HTTPException(401, detail="private-detail", headers={"WWW-Authenticate": "Bearer"})

    response = client.get("/_test/http-error")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "private-detail" not in response.text


def test_unexpected_error_has_correlated_safe_response_and_log(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    @app.get("/_test/crash")
    def fail() -> None:
        raise RuntimeError("private-exception-data")

    with caplog.at_level(logging.INFO):
        response = client.get("/_test/crash", headers={"X-Request-ID": "failure-id"})
    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failure-id"
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "Internal server error",
        "request_id": "failure-id",
        "details": [],
    }
    failure = next(record for record in caplog.records if record.message == "request_failed")
    assert failure.request_id == "failure-id"
    assert failure.error_type == "RuntimeError"
    assert "private-exception-data" not in caplog.text + response.text
