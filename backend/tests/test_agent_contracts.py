import json
from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.provider import MockModelProvider, ModelProvider, ModelResponse
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import AgentId, AgentTask, Capability
from novel_os.domain.workflow import ChapterState


@pytest.fixture
def task():
    return AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=ChapterState.C04_CHAPTER_PLANNING,
        workflow_state_version=5,
        agent_id=AgentId.A03_PLANNING,
        task_type="MOCK_PLAN",
        objective="Mock planning",
        target_ref=uuid4(),
        capabilities=[Capability.PROPOSE_PLAN],
        attempt_count=1,
    )


class RawProvider(ModelProvider):
    def __init__(self, raw):
        self.raw = raw

    def generate(self, request):
        return ModelResponse(self.raw)


@pytest.mark.parametrize("raw", ["not json", '{"status":1,"status":2}', "x" * 150_001, {}])
def test_ambiguous_or_unbounded_provider_output_is_rejected(task, raw):
    result = AgentRuntime(RawProvider(raw)).execute(task)
    assert result.result is None
    assert result.error_code == "FORMAT_ERROR"
    assert result.retryable


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -0.1, 1.1])
def test_confidence_must_be_finite_and_bounded(task, confidence):
    valid = AgentRuntime(MockModelProvider()).execute(task).result.model_dump(mode="json")
    valid["confidence"] = confidence
    result = AgentRuntime(RawProvider(json.dumps(valid))).execute(task)
    assert result.error_code == "SCHEMA_PARSE_ERROR"


@pytest.mark.parametrize("scenario", ["FORMAT_ERROR_ONCE", "MODEL_ERROR_ONCE"])
def test_mock_retry_scenario_uses_persisted_attempt_number(task, scenario):
    first = AgentRuntime(MockModelProvider(scenario)).execute(task)
    second = AgentRuntime(MockModelProvider(scenario)).execute(replace(task, attempt_count=2))
    assert first.retryable
    assert second.error_code is None
    assert second.result.task_id == task.task_id


def test_invalid_scope_is_rejected_before_provider_execution(task):
    class MustNotExecute(ModelProvider):
        called = False

        def generate(self, request):
            self.called = True
            return "{}"

    provider = MustNotExecute()
    result = AgentRuntime(provider).execute(replace(task, capabilities=[Capability.APPROVE]))
    assert not provider.called
    assert result.error_code == "AUTHORITY_DENIED"
    assert not result.retryable


def test_valid_artifact_text_preserves_whitespace_and_unicode(task):
    value = "  开场\n\n保留正文排版。🌙\n"
    body = AgentRuntime(MockModelProvider()).execute(task).result.model_dump(mode="json")
    body["result"]["objective"] = value
    execution = AgentRuntime(RawProvider(json.dumps(body))).execute(task)
    assert execution.error_code is None
    assert execution.result.result.objective == value


@pytest.mark.parametrize("heartbeat", [30, 31, 0, -1])
def test_worker_configuration_rejects_invalid_heartbeat(settings, heartbeat):
    with pytest.raises(ValidationError):
        type(settings)(
            **(
                settings.model_dump()
                | {"agent_lease_seconds": 30, "agent_heartbeat_seconds": heartbeat}
            )
        )
