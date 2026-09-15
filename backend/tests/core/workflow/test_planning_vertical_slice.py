from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.worker import AgentWorker
from tests.core.workflow.workflow_test_support import Driver


class PlanningDriver(Driver):
    def __init__(
        self, client, chapter_api, raw="本章必须找到线索，不能杀死主角，保留人物之间的信任。"
    ):
        self.client = client
        self.chapter_api = chapter_api
        parts = chapter_api.split("/")
        self.creation = {
            "project_id": parts[4],
            "chapter_id": parts[6],
            "event_id": str(uuid4()),
            "raw_requirement": raw,
        }
        response = client.post("/api/v1/workflows/chapter-planning", json=self.creation)
        assert response.status_code == 201, response.text
        self.workflow = response.json()["workflow"]
        self.url = "/api/v1/workflows/" + self.workflow["id"]
        assert self.event("USER_SUBMITTED").status_code == 200

    def read(self, suffix):
        result = self.client.get(self.url + suffix)
        assert result.status_code == 200, result.text
        return result.json()


@pytest.fixture
def planning_driver(core_client, chapter_api):
    return PlanningDriver(core_client, chapter_api)


def run_one(database, driver, scenario="SUCCESS", provider=None):
    worker = AgentWorker(
        database, AgentRuntime(provider or MockModelProvider(scenario)), retry_seconds=0
    )
    assert worker.run_once()
    driver.refresh()
    return worker


def test_e2e_a_business_slice_stops_at_c07(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING", d.workflow
    brief = d.read("/creative-brief")
    assert brief["raw_requirement"] == d.creation["raw_requirement"]
    assert brief["version"] == 1 and brief["status"] == "READY"
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C05_PLAN_REVIEW", d.workflow
    plan = d.read("/planning/plan")
    assert plan["generation"]["brief_id"] == brief["id"]
    worker = run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL", d.workflow
    review = d.read("/planning/review")
    assert review["plan_id"] == plan["plan"]["id"] and review["verdict"] == "PASS"
    assert d.decide().status_code == 200
    assert d.workflow["current_state"] == "C07_WRITING"
    assert d.workflow["draft_version"] is None
    assert worker.run_once() is False
    chapter = d.client.get(d.chapter_api).json()
    assert chapter["approved_plan_version"] == 1
    assert chapter["current_version"] is None and chapter["approved_version"] is None
    history = d.read("/planning/history")
    for collection in history.values():
        for artifact in collection:
            assert (
                artifact["prompt_lineage_id"]
                and artifact["context_package_id"]
                and artifact["agent_run_id"]
            )
    metrics = d.read("/planning/metrics")
    assert metrics["planning_iterations"] == 1 and metrics["technical_retry_count"] == 0


def test_e2e_b_review_fail_creates_new_iteration(planning_driver, core_database):
    d = planning_driver
    run_one(core_database, d)
    run_one(core_database, d)
    first = d.read("/planning/plan")
    run_one(core_database, d, "QUALITY_FAIL")
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING", d.workflow
    assert d.workflow["planning_iteration_count"] == 2
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL", d.workflow
    assert d.read("/planning/plan")["plan"]["version"] == 2
    assert d.read("/planning/plan/versions/1") == first
    assert d.decide().status_code == 200
    assert d.workflow["current_state"] == "C07_WRITING"


def test_e2e_c_consequential_ambiguity_stops_before_plan(planning_driver, core_database):
    d = planning_driver
    worker = run_one(core_database, d, "NEEDS_HUMAN")
    assert d.workflow["current_state"] == "C90_BLOCKED", d.workflow
    brief = d.read("/creative-brief")
    assert brief["status"] == "NEEDS_HUMAN"
    assert brief["body"]["unresolved_ambiguities"][0]["user_decision_needed"]
    assert d.read("/planning/history")["plans"] == []
    assert worker.run_once() is False
