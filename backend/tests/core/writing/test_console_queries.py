from uuid import uuid4

from tests.core.workflow.test_planning_vertical_slice import run_one


def test_chapter_workflow_discovery_scoped_paginated_read_only(writing_driver):
    d = writing_driver
    path = d.chapter_api + "/workflows"
    before = d.read("/history")
    assert [w["id"] for w in d.client.get(path).json()] == [d.workflow["id"]]
    assert d.client.get(path + "?limit=1&offset=1").json() == []
    foreign = d.client.post("/api/v1/projects", json={"name": "Other"}).json()["id"]
    assert d.client.get(path.replace(d.workflow["project_id"], foreign)).status_code == 404
    assert d.client.get(path.replace(d.workflow["chapter_id"], str(uuid4()))).status_code == 404
    assert d.client.get(path + "?limit=201").status_code == 422
    assert d.read("/history") == before
    assert d.client.post(path, json={"actor": "SYSTEM"}).status_code == 405


def test_run_context_preserves_exact_retry_attempt(ready_writer, core_database):
    d = ready_writer
    run_one(core_database, d, "FORMAT_ERROR_ONCE")
    task = d.read("/agent-tasks")[-1]
    run_one(core_database, d)
    runs = d.client.get(f"/api/v1/agent-tasks/{task['task_id']}/runs").json()
    assert len(runs) == 2
    snapshots = []
    before = d.read("/history")
    for index, run in enumerate(runs, 1):
        response = d.client.get(f"/api/v1/agent-runs/{run['run_id']}/context")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["package"]["request"]["attempt_number"] == index
        assert data["package"]["task_id"] == task["task_id"]
        snapshots.append(data["package"]["context_package_id"])
        assert "openai_api_key" not in response.text and "lease_token" not in response.text
    assert len(set(snapshots)) == 2
    assert d.read("/history") == before
    assert d.client.get(f"/api/v1/agent-runs/{uuid4()}/context").status_code == 404


def test_run_without_context_returns_not_found(ready_writer, core_database):
    from novel_os.services.agent_queue import AgentQueue

    with core_database.session() as session:
        lease = AgentQueue(session).claim("console-test")
    response = ready_writer.client.get(f"/api/v1/agent-runs/{lease.run_id}/context")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
