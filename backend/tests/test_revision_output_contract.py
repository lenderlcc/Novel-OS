import json
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.planning_schemas import result_model
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.runtime import AgentRuntime, execution_failure
from novel_os.domain.agents import AgentTask
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.openai import native_schema
from novel_os.revision.contracts import LEGACY_CONTRACTS, READ_ONLY_CONTRACTS, RevisionPlanV3
from tests.planning_support import RecordedProvider

pytest_plugins = ["tests.test_revision_fidelity"]


def envelope(body):
    return dict(
        task_id=str(uuid4()),
        status="SUCCESS",
        result=body,
        confidence=0.8,
        assumptions=[],
        issues=[],
        proposed_changes=[],
        memory_proposals=[],
        escalation=None,
    )


@pytest.fixture
def outputs(fidelity_outputs):
    _, _, _, candidate, plan, fidelity = deepcopy(fidelity_outputs)
    plan["unresolved_issue_ids"] = []
    revision = {k: v for k, v in candidate.body.items() if k != "content_hash"}
    return {
        "PLAN_CHAPTER_REVISION": envelope(plan),
        "REVISE_CHAPTER": envelope(revision),
        "VALIDATE_REVISION_FIDELITY": envelope(fidelity),
    }


@pytest.mark.parametrize(
    "task_type", ["PLAN_CHAPTER_REVISION", "REVISE_CHAPTER", "VALIDATE_REVISION_FIDELITY"]
)
@pytest.mark.parametrize("absent", [False, True])
def test_revision_accepts_empty_or_absent_proposals(outputs, task_type, absent):
    body = outputs[task_type]
    if absent:
        body.pop("proposed_changes")
        body.pop("memory_proposals")
    definition = TaskDefinitionRegistry().get(task_type)
    parsed = definition.output_schema.parse(json.dumps(body))
    assert parsed.proposed_changes == parsed.memory_proposals == []
    assert definition.output_schema.model is result_model(task_type)
    assert AgentRegistry().task(task_type).result_schema == (
        definition.output_schema.schema_id + ".v" + str(definition.output_schema.version)
    )
    for schema in [
        json.loads(definition.output_schema.schema_json),
        native_schema(json.loads(definition.output_schema.schema_json)),
    ]:
        for field in ["proposed_changes", "memory_proposals"]:
            assert schema["properties"][field]["maxItems"] == 0


@pytest.mark.parametrize(
    "task_type", ["PLAN_CHAPTER_REVISION", "REVISE_CHAPTER", "VALIDATE_REVISION_FIDELITY"]
)
@pytest.mark.parametrize("field", ["proposed_changes", "memory_proposals"])
def test_nonempty_proposals_fail_at_output_contract(outputs, task_type, field):
    outputs[task_type][field] = [dict(capability="PROPOSE_DRAFT", target_ref=str(uuid4()))]
    with pytest.raises(ValidationError) as error:
        TaskDefinitionRegistry().get(task_type).output_schema.parse(json.dumps(outputs[task_type]))
    assert execution_failure(error.value).error_code == "SCHEMA_PARSE_ERROR"


def test_unsupported_major_change_is_unresolved_not_proposed(outputs):
    body = outputs["PLAN_CHAPTER_REVISION"]
    plan = body["result"]
    plan["revision_targets"] = []
    plan["revision_zones"] = []
    plan["unresolved_issue_ids"] = plan["target_issue_ids"]
    plan["blocked_reasons"] = [
        dict(issue_id=id, reason="需要改变已批准的结局，超出局部修改权限。")
        for id in plan["target_issue_ids"]
    ]
    parsed = (
        TaskDefinitionRegistry().get("PLAN_CHAPTER_REVISION").output_schema.parse(json.dumps(body))
    )
    assert not parsed.proposed_changes
    assert not parsed.result.revision_targets
    assert set(parsed.result.unresolved_issue_ids) == {
        b.issue_id for b in parsed.result.blocked_reasons
    }
    plan["unresolved_issue_ids"] = []
    with pytest.raises(ValidationError, match="Unresolved issues"):
        RevisionPlanV3.model_validate(plan)


def test_new_prompts_and_legacy_contracts_are_separate():
    registry, prompts = TaskDefinitionRegistry(), PromptRegistry()
    for task_type in ["PLAN_CHAPTER_REVISION", "REVISE_CHAPTER", "VALIDATE_REVISION_FIDELITY"]:
        current = registry.get(task_type)
        template = prompts.resolve(current.task_template)
        assert "proposed_changes=[]" in template.content
        assert "memory_proposals=[]" in template.content
    for (task_type, schema), (model, template_version, _) in LEGACY_CONTRACTS.items():
        historical = registry.get(task_type, schema)
        assert historical.output_schema.model is model is result_model(task_type, schema)
        assert prompts.resolve(historical.task_template).module.version == template_version
        assert (
            historical.output_schema.schema_hash
            != registry.get(task_type).output_schema.schema_hash
        )


@pytest.mark.parametrize("task_type,schema", list(READ_ONLY_CONTRACTS))
def test_legacy_revision_contract_is_readable_but_cannot_call_provider(task_type, schema):
    mapping = AgentRegistry().task(task_type)
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=mapping.state,
        workflow_state_version=1,
        agent_id=mapping.agent_id,
        task_type=task_type,
        objective="historical task",
        target_ref=uuid4(),
        capabilities=[mapping.capability],
        expected_output_schema=schema,
        attempt_count=1,
    )
    provider = RecordedProvider()
    runtime = AgentRuntime(provider)
    assert runtime.prepare(task).error_code == "PROMPT_CONFIGURATION_ERROR"
    # A precompiled historical prompt cannot bypass the network guard either.
    request = runtime.prompts.prepare(
        task_id=task.task_id,
        task_type=task.task_type,
        agent_id=task.agent_id,
        attempt=1,
        target_ref=task.target_ref,
        output_kind=mapping.output_kind,
        capabilities=task.capabilities,
        constraints=[],
        context_payload={},
        expected_output_schema=schema,
    )
    assert runtime.execute(task, request).error_code == "PROMPT_CONFIGURATION_ERROR"
    assert provider.requests == []


@pytest.mark.parametrize(
    "task_type,schema",
    [key for key in LEGACY_CONTRACTS if key not in READ_ONLY_CONTRACTS],
)
def test_previous_safe_revision_contract_keeps_historical_prompt_and_can_prepare(
    outputs, task_type, schema
):
    from novel_os.providers.base import ModelRequest

    mapping = AgentRegistry().task(task_type)
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=mapping.state,
        workflow_state_version=1,
        agent_id=mapping.agent_id,
        task_type=task_type,
        objective="previous safe revision",
        target_ref=uuid4(),
        capabilities=[mapping.capability],
        expected_output_schema=schema,
        attempt_count=1,
    )
    runtime = AgentRuntime(RecordedProvider())
    prepared = runtime.prepare(task)
    assert isinstance(prepared, ModelRequest)
    assert prepared.prompt.output.model is LEGACY_CONTRACTS[task_type, schema][0]
    prepared.prompt.output.parse(json.dumps(outputs[task_type]))
    definition = runtime.prompts.tasks.get(task_type, schema)
    assert definition.task_template.version == LEGACY_CONTRACTS[task_type, schema][1]
