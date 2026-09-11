import ast
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from agent_test_support import claim, pending_task, runs, start, task_record

from novel_os.agents.provider import MockModelProvider, ModelProvider, ModelResponse
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import AgentId, Capability, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.services.agent_results import AgentResultHandler
from novel_os.worker import AgentWorker

pytestmark = pytest.mark.integration


class ModifiedProvider(ModelProvider):
    def __init__(self, change):
        self.change = change

    def generate(self, request):
        output = json.loads(MockModelProvider().generate(request).content)
        self.change(output)
        return ModelResponse(json.dumps(output))


@pytest.mark.parametrize(
    "capability",
    ["APPROVE", "LOCK", "UNLOCK", "COMMIT_CANON", "SET_WORKFLOW_STATE", "DIRECT_DATABASE_WRITE"],
)
def test_forbidden_agent_operation_is_rejected_without_privileged_mutation(
    driver, core_database, capability
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])

    def forge(output):
        output["proposed_changes"] = [
            {"capability": capability, "target_ref": driver.workflow["chapter_id"]}
        ]

    assert AgentWorker(core_database, AgentRuntime(ModifiedProvider(forge))).run_once()
    assert driver.refresh()["current_state"] == "C90_BLOCKED"
    assert driver.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert task_record(core_database, task_id).status == TaskStatus.BLOCKED
    run = runs(core_database, task_id)[0]
    assert run.error_code == "AUTHORITY_DENIED"
    assert run.disposition == "BLOCKED"
    assert driver.client.get(driver.chapter_api).json()["approved_plan_version"] is None


@pytest.mark.parametrize(
    "level,field,value",
    [
        ("top", "next_state", "C16_COMPLETED"),
        ("top", "next_event", "PLAN_READY"),
        ("result", "next_state", "C16_COMPLETED"),
        ("result", "next_event", "PLAN_READY"),
        ("top", "status", "APPROVED"),
        ("result", "authority_level", "A1_USER_LOCKED"),
    ],
)
def test_untrusted_output_cannot_select_state_event_or_authority(
    driver, core_database, level, field, value
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    before = driver.workflow.copy()

    def forge(output):
        (output if level == "top" else output["result"])[field] = value

    assert AgentWorker(core_database, AgentRuntime(ModifiedProvider(forge))).run_once()
    assert driver.refresh() == before
    assert runs(core_database, task_id)[0].error_code == "SCHEMA_PARSE_ERROR"
    assert task_record(core_database, task_id).status == TaskStatus.PENDING


@pytest.mark.parametrize("wrong_scope", ["task", "target", "memory"])
def test_result_is_bound_to_task_and_target_scope(driver, core_database, wrong_scope):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    task = start(core_database, lease)

    def forge(output):
        if wrong_scope == "task":
            output["task_id"] = str(uuid4())
        else:
            key = "memory_proposals" if wrong_scope == "memory" else "proposed_changes"
            output[key] = [{"capability": "PROPOSE_PLAN", "target_ref": str(uuid4())}]

    result = AgentRuntime(ModifiedProvider(forge)).execute(task)
    assert result.error_code == "AUTHORITY_DENIED"


@pytest.mark.parametrize(
    "mismatch", ["agent", "task_type", "state", "scope", "definition", "disabled"]
)
def test_capability_requires_identity_task_state_and_scope(driver, core_database, mismatch):
    from novel_os.domain.workflow import ChapterState

    driver.advance_to("C04_CHAPTER_PLANNING")
    task = start(core_database, claim(core_database))
    registry = AgentRegistry()
    if mismatch == "agent":
        task = replace(task, agent_id=AgentId.A04_WRITING)
    elif mismatch == "task_type":
        task = replace(task, task_type="MOCK_REVIEW")
    elif mismatch == "state":
        task = replace(task, workflow_state=ChapterState.C07_WRITING)
    elif mismatch == "scope":
        task = replace(task, capabilities=[])
    else:
        definition = registry.get(task.agent_id)
        registry.definitions[task.agent_id] = replace(
            definition,
            default_capabilities=frozenset()
            if mismatch == "definition"
            else definition.default_capabilities,
            enabled=mismatch != "disabled",
        )
    assert (
        AgentRuntime(MockModelProvider(), registry).execute(task).error_code == "AUTHORITY_DENIED"
    )


def test_mock_authority_violation_uses_normal_validation_chain(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    assert AgentWorker(
        core_database, AgentRuntime(MockModelProvider("AUTHORITY_VIOLATION"))
    ).run_once()
    assert runs(core_database, task_id)[0].error_code == "AUTHORITY_DENIED"
    assert driver.refresh()["current_state"] == "C90_BLOCKED"
    assert driver.workflow["resume_state"] == "C04_CHAPTER_PLANNING"


def test_arbitrary_dict_cannot_be_handled_as_validated_result(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    lease = claim(core_database)
    start(core_database, lease)
    with core_database.session() as session, pytest.raises(DomainError) as exc:
        AgentResultHandler(session).complete(lease, {"status": "SUCCESS"})
    assert exc.value.code == "VALIDATION_ERROR"
    assert task_record(core_database, lease.task_id).status == TaskStatus.RUNNING


def test_provider_secrets_are_not_persisted_or_logged(driver, core_database, caplog):
    secret = "sk-sensitive-provider-credential-for-negative-test"

    class FailingProvider(ModelProvider):
        def generate(self, request):
            raise RuntimeError(secret)

    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    assert AgentWorker(core_database, AgentRuntime(FailingProvider())).run_once()
    assert secret not in repr(task_record(core_database, task_id))
    assert secret not in repr(runs(core_database, task_id))
    assert secret not in caplog.text
    assert runs(core_database, task_id)[0].error_code == "TRANSIENT_INFRASTRUCTURE_ERROR"


def test_agent_implementation_has_no_persistence_or_workflow_writer_imports():
    import novel_os.agents

    forbidden = (
        "novel_os.repositories",
        "novel_os.services",
        "novel_os.models",
        "novel_os.workflow",
        "sqlalchemy",
        "fastapi",
    )
    for path in Path(novel_os.agents.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden), path.name
            elif isinstance(node, ast.Import):
                assert not any(alias.name.startswith(forbidden) for alias in node.names), path.name
    assert Capability.APPROVE not in AgentRegistry().get(AgentId.A03_PLANNING).default_capabilities
