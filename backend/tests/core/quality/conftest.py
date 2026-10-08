from uuid import uuid4

import pytest

from tests.core.writing.conftest import WritingDriver


class QualityDriver(WritingDriver):
    def __init__(
        self,
        client,
        chapter_api,
        raw_requirement="两人在雨夜会合，约定沿河寻找失落的信件。不要新增核心能力。",
    ):
        self.client, self.chapter_api = client, chapter_api
        parts = chapter_api.split("/")
        self.creation = dict(
            project_id=parts[4],
            chapter_id=parts[6],
            event_id=str(uuid4()),
            raw_requirement=raw_requirement,
        )
        response = client.post("/api/v1/workflows/chapter-quality", json=self.creation)
        assert response.status_code == 201, response.text
        self.workflow = response.json()["workflow"]
        self.url = "/api/v1/workflows/" + self.workflow["id"]
        assert self.event("USER_SUBMITTED").status_code == 200

    def reviews(self):
        response = self.client.get(self.chapter_api + "/quality-reviews")
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def quality_driver(core_client, chapter_api, core_database):
    return QualityDriver(core_client, chapter_api).approve_plan(core_database)


@pytest.fixture
def revision_quality_driver(core_client, chapter_api, core_database):
    from tests.core.test_writing_profiles import approve, draft

    d = QualityDriver(core_client, chapter_api)
    project = chapter_api.split("/chapters/")[0]
    draft(core_client, project, narrative_perspective="THIRD_PERSON")
    approve(core_client, project)
    return d.approve_plan(core_database)
