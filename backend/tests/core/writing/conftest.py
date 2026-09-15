from uuid import uuid4

import pytest

from tests.core.workflow.test_planning_vertical_slice import PlanningDriver, run_one


class WritingDriver(PlanningDriver):
    def __init__(self, client, chapter_api):
        self.client, self.chapter_api = client, chapter_api
        parts = chapter_api.split("/")
        self.creation = dict(
            project_id=parts[4],
            chapter_id=parts[6],
            event_id=str(uuid4()),
            raw_requirement="两人在雨夜会合，约定沿河寻找失落的信件。不要新增核心能力。",
        )
        response = client.post("/api/v1/workflows/chapter-writing", json=self.creation)
        assert response.status_code == 201, response.text
        self.workflow = response.json()["workflow"]
        self.url = "/api/v1/workflows/" + self.workflow["id"]
        assert self.event("USER_SUBMITTED").status_code == 200

    def approve_plan(self, database):
        for _ in range(3):
            run_one(database, self)
        assert self.workflow["current_state"] == "C06_PLAN_APPROVAL", self.workflow
        result = self.decide()
        assert result.status_code == 200, result.text
        assert self.workflow["current_state"] == "C07_WRITING", self.workflow
        return self


@pytest.fixture
def writing_driver(core_client, chapter_api):
    return WritingDriver(core_client, chapter_api)


@pytest.fixture
def ready_writer(writing_driver, core_database):
    return writing_driver.approve_plan(core_database)
