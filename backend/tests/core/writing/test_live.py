"""Optional paid smoke against an isolated test project; never part of default execution."""

import pytest

from novel_os.agents.runtime import AgentRuntime
from novel_os.core.config import Settings
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.openai import OpenAIModelProvider
from novel_os.worker import AgentWorker

pytestmark = [pytest.mark.integration, pytest.mark.live_model]


def test_real_provider_writes_from_approved_test_plan(request, ready_writer, core_database):
    if not request.config.getoption("--live-model"):
        pytest.skip("Paid Writing smoke requires explicit --live-model")
    settings = Settings.from_file()
    if settings.openai_api_key is None:
        pytest.skip("Configure the real provider credential in config.toml")
    runtime = AgentRuntime(
        OpenAIModelProvider(settings.openai_api_key),
        tasks=TaskDefinitionRegistry(model_profile="openai-structured"),
    )
    worker = AgentWorker(core_database, runtime, retry_seconds=0)
    for _ in range(3):
        assert worker.run_once()
        if ready_writer.refresh()["current_state"] != "C07_WRITING":
            break
    assert ready_writer.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    record = ready_writer.read("/writing/history")[0]
    assert record["provider"] == "openai" and record["check_status"] == "PASS"
    assert (
        record["chapter_version_id"]
        and record["prompt_lineage_id"]
        and record["context_package_id"]
    )
