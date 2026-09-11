from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from novel_os.main import create_app


class Driver:
    def __init__(self, client, chapter_api):
        self.client = client
        self.chapter_api = chapter_api
        parts = chapter_api.split("/")
        self.creation = {"project_id": parts[4], "chapter_id": parts[6], "event_id": str(uuid4())}
        response = client.post("/api/v1/workflows/chapter", json=self.creation)
        assert response.status_code == 201, response.text
        self.workflow = response.json()["workflow"]
        self.url = "/api/v1/workflows/" + self.workflow["id"]

    def refresh(self):
        response = self.client.get(self.url)
        assert response.status_code == 200, response.text
        self.workflow = response.json()
        return self.workflow

    def command(self, **extra):
        return {
            "event_id": str(uuid4()),
            "expected_state_version": self.workflow["state_version"],
            **extra,
        }

    def post(self, suffix, body):
        response = self.client.post(self.url + suffix, json=body)
        if response.status_code < 300:
            self.workflow = response.json()["workflow"]
        return response

    def event(self, event_type, **extra):
        return self.post("/events", self.command(event_type=event_type, **extra))

    def fake(self, outcome="success"):
        return self.post(
            "/fake-execute",
            self.command(origin_state=self.workflow["current_state"], outcome=outcome),
        )

    def gate(self):
        response = self.client.get(self.url + "/human-gates")
        assert response.status_code == 200
        return next(g for g in response.json() if g["status"] == "WAITING")

    def decide(self, decision="APPROVE", **extra):
        gate = self.gate()
        body = self.command(
            expected_artifact_version=gate["artifact_version"], decision=decision, **extra
        )
        response = self.client.post("/api/v1/human-gates/" + gate["id"] + "/decision", json=body)
        if response.status_code < 300:
            self.workflow = response.json()["workflow"]
        return response

    def advance_to(self, target):
        for _ in range(40):
            current = self.workflow["current_state"]
            if current == target:
                return
            if current == "C00_CREATED":
                response = self.event("USER_SUBMITTED")
            elif current in {"C06_PLAN_APPROVAL", "C12_USER_REVIEW"}:
                response = self.decide()
            else:
                response = self.fake()
            assert response.status_code == 200, response.text
            assert self.workflow["current_state"] != "C90_BLOCKED", self.workflow
        pytest.fail("Workflow did not reach target within its expected transition count")


@pytest.fixture
def workflow_client(core_settings):
    settings = core_settings.model_copy(update={"workflow_fake_executor_enabled": True})
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def driver(workflow_client, chapter_api):
    return Driver(workflow_client, chapter_api)
