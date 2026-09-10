from uuid import UUID

from fastapi.testclient import TestClient


def test_liveness_works_without_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert UUID(response.headers["x-request-id"]).version == 4


def test_database_unavailable_returns_503_and_liveness_stays_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health/db", headers={"X-Request-ID": "db-outage"})
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database is unavailable",
            "request_id": "db-outage",
            "details": [],
        }
    }
    assert response.headers["x-request-id"] == "db-outage"
    assert "unit-test-only" not in response.text
    assert client.get("/api/v1/health").status_code == 200


def test_openapi_describes_readiness_error(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    response = schema["paths"]["/api/v1/health/db"]["get"]["responses"]["503"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
