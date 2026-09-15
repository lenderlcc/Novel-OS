"""Explicit opt-in only. Uses an isolated test schema and the configured real provider."""

import pytest

from novel_os.agents.runtime import AgentRuntime
from novel_os.core.config import Settings
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.openai import OpenAIModelProvider
from novel_os.worker import AgentWorker

pytestmark = [pytest.mark.integration, pytest.mark.live_model]


def test_real_provider_planning_vertical_slice(request, planning_driver, core_database):
    if not request.config.getoption("--live-model"):
        pytest.skip("Paid planning E2E is opt-in; pass --live-model explicitly")
    settings = Settings.from_file()
    if settings.openai_api_key is None:
        pytest.skip("Configure the real provider credential in config.toml")
    runtime = AgentRuntime(
        OpenAIModelProvider(settings.openai_api_key),
        tasks=TaskDefinitionRegistry(model_profile="openai-structured"),
    )
    worker = AgentWorker(core_database, runtime, retry_seconds=0)
    driver = planning_driver
    # At most seven provider attempts in this explicitly opted-in smoke test.
    for _ in range(7):
        assert worker.run_once()
        driver.refresh()
        if driver.workflow["current_state"] == "C06_PLAN_APPROVAL":
            break
        assert driver.workflow["current_state"] not in {"C90_BLOCKED", "C91_FAILED"}
    assert driver.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert driver.decide().status_code == 200
    assert driver.workflow["current_state"] == "C07_WRITING"
    assert driver.workflow["draft_version"] is None
    history = driver.read("/planning/history")
    assert history["briefs"] and history["plans"] and history["reviews"]
    for records in history.values():
        assert all(row["prompt_lineage_id"] and row["context_package_id"] for row in records)
