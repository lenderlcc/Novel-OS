import json
from uuid import UUID

import pytest
from agent_test_support import claim, complete, pending_task, runs, start, task_record
from sqlalchemy import text

from novel_os.agents.provider import MockModelProvider, ModelProvider, ModelResponse
from novel_os.agents.runtime import AgentRuntime, ExecutionResult
from novel_os.domain.agents import RunStatus, TaskStatus
from novel_os.worker import AgentWorker

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("same_project", [False, True])
@pytest.mark.parametrize("locked_count", [1, 2])
def test_claim_skips_locked_heads_and_takes_next_available_task(
    driver, core_database, same_project, locked_count
):
    assert driver.event("USER_SUBMITTED").status_code == 200
    task_ids = [UUID(pending_task(driver)["task_id"])]
    for sequence in range(2, locked_count + 3):
        if same_project:
            project_id = driver.workflow["project_id"]
        else:
            response = driver.client.post("/api/v1/projects", json={"name": "Queue review"})
            assert response.status_code == 201
            project_id = response.json()["id"]
        chapters_url = f"/api/v1/projects/{project_id}/chapters"
        response = driver.client.post(chapters_url, json={"sequence": sequence, "title": "Next"})
        assert response.status_code == 201
        another = type(driver)(driver.client, chapters_url + "/" + response.json()["id"])
        assert another.event("USER_SUBMITTED").status_code == 200
        task_ids.append(UUID(pending_task(another)["task_id"]))

    locked = task_ids[:locked_count]
    with core_database.engine.begin() as connection:
        for task_id in locked:
            connection.execute(
                text("SELECT task_id FROM agent_tasks WHERE task_id=:id FOR UPDATE"),
                {"id": task_id},
            )
        # No project lock is held by the other transaction, as in the heartbeat path.
        first = claim(core_database)
        assert first is not None
        assert first.task_id == task_ids[locked_count]
        assert claim(core_database).task_id == task_ids[locked_count + 1]
        assert claim(core_database) is None
        for task_id in locked:
            assert task_record(core_database, task_id).status == TaskStatus.PENDING
            assert runs(core_database, task_id) == []
    assert claim(core_database).task_id == locked[0]


@pytest.mark.parametrize(
    "stage,field,collection",
    [
        ("C04_CHAPTER_PLANNING", "objective", "plans"),
        ("C04_CHAPTER_PLANNING", "required_outcome", "plans"),
        ("C07_WRITING", "content", "versions"),
        ("C07_WRITING", "change_reason", "versions"),
    ],
)
@pytest.mark.parametrize("invalid_text", [" \t\n", "text\x00value"])
def test_invalid_artifact_output_records_schema_failure_then_retries(
    driver, core_database, stage, field, collection, invalid_text
):
    class InvalidTextOnce(ModelProvider):
        def generate(self, request):
            output = json.loads(MockModelProvider().generate(request).content)
            if request.attempt_number == 1:
                output["result"][field] = invalid_text
            return ModelResponse(json.dumps(output))

    driver.advance_to(stage)
    before = driver.workflow.copy()
    task_id = UUID(pending_task(driver)["task_id"])
    worker = AgentWorker(core_database, AgentRuntime(InvalidTextOnce()), retry_seconds=0)
    assert worker.run_once()
    failed = runs(core_database, task_id)[0]
    assert failed.status == RunStatus.FAILED
    assert failed.error_code == "SCHEMA_PARSE_ERROR"
    assert failed.finished_at is not None
    task = task_record(core_database, task_id)
    assert task.status == TaskStatus.PENDING
    assert task.attempt_count == 1
    assert task.lease_owner is task.lease_token is None
    assert driver.refresh() == before
    assert driver.client.get(driver.chapter_api + "/" + collection).json() == []

    assert worker.run_once()
    history = runs(core_database, task_id)
    assert len(history) == 2
    assert history[0] == failed
    assert history[1].status == RunStatus.SUCCEEDED
    assert task_record(core_database, task_id).status == TaskStatus.SUCCEEDED
    assert len(driver.client.get(driver.chapter_api + "/" + collection).json()) == 1


def test_handler_revalidates_artifact_text_in_copied_result(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)
    result = AgentRuntime(MockModelProvider()).execute(task).result
    # model_copy does not validate updates; the application boundary must do so again.
    copied = result.model_copy(
        update={"result": result.result.model_copy(update={"objective": "   "})}
    )
    assert complete(core_database, lease, ExecutionResult(result=copied)) == "RETRY_SCHEDULED"
    assert runs(core_database, task.task_id)[0].error_code == "SCHEMA_PARSE_ERROR"
    assert task_record(core_database, task.task_id).status == TaskStatus.PENDING
