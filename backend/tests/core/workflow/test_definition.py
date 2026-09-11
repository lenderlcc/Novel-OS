from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from novel_os.domain.errors import DomainError
from novel_os.workflow.definitions import WorkflowDefinitionLoader, WorkflowDefinitionRegistry
from novel_os.workflow.runtime import WorkflowRuntime


def test_loader_immutable_version_registry_and_packaged_yaml():
    definition = WorkflowDefinitionLoader().load()
    registry = WorkflowDefinitionRegistry([definition])
    with pytest.raises(FrozenInstanceError):
        definition.version = 2
    changed = deepcopy(definition.body)
    changed["max_technical_retries"] = 0
    with pytest.raises(DomainError):
        registry.register(WorkflowDefinitionLoader().from_body(changed))
    changed["version"] = 2
    registry.register(WorkflowDefinitionLoader().from_body(changed))
    assert registry.get("chapter-production", 1).body["max_technical_retries"] == 2
    assert registry.get("chapter-production", 2).body["max_technical_retries"] == 0
    copy = registry.get("chapter-production", 1)
    copy.body["max_technical_retries"] = 9
    assert registry.get("chapter-production", 1).body["max_technical_retries"] == 2


@pytest.mark.parametrize(
    "content",
    [
        "id: chapter-production\nid: replacement",
        "!!python/object/apply:os.system ['echo forbidden']",
        "id: unknown",
        "[]",
        "1: value",
        "x: &self {x: *self}",
    ],
)
def test_invalid_yaml_is_rejected(tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content)
    with pytest.raises(DomainError) as error:
        WorkflowDefinitionLoader().load(path)
    assert error.value.code == "INVALID_DEFINITION"


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate",
        "unguarded",
        "unknown_guard",
        "terminal_outgoing",
        "agent_approval",
        "unknown_effect",
        "unreachable",
    ],
)
def test_invalid_transition_tables_fail_closed(corruption):
    loader = WorkflowDefinitionLoader()
    body = deepcopy(loader.load().body)
    if corruption == "duplicate":
        body["transitions"].append(body["transitions"][0])
    elif corruption == "unguarded":
        next(r for r in body["transitions"] if r["target"] == "C07_WRITING")["guards"] = []
    elif corruption == "unknown_guard":
        body["transitions"][0]["guards"] = ["eval_payload"]
    elif corruption == "terminal_outgoing":
        body["transitions"][0]["source"] = "C16_COMPLETED"
    elif corruption == "agent_approval":
        next(r for r in body["transitions"] if r["source"] == "C06_PLAN_APPROVAL")["actor"] = (
            "AGENT"
        )
    elif corruption == "unknown_effect":
        body["transitions"][0]["effect"] = "commit_canon"
    else:
        body["transitions"] = body["transitions"][:-1]
    with pytest.raises(DomainError):
        loader.from_body(body)


@pytest.mark.integration
def test_running_instance_uses_persisted_definition_not_current_registry(driver, core_database):
    driver.advance_to("C04_CHAPTER_PLANNING")
    loader = WorkflowDefinitionLoader()
    changed = deepcopy(loader.load().body)
    changed["version"] = 2
    changed["max_technical_retries"] = 0
    registry = WorkflowDefinitionRegistry([loader.from_body(changed)])
    from uuid import uuid4

    from novel_os.domain.core import CommandContext
    from novel_os.domain.enums import ActorType
    from novel_os.domain.workflow import ChapterState

    with core_database.session() as session:
        result = WorkflowRuntime(session, registry).simulate(
            UUID(driver.workflow["id"]),
            uuid4(),
            driver.workflow["state_version"],
            ChapterState.C04_CHAPTER_PLANNING,
            "technical_failure",
            CommandContext("v2-registry", "fake", ActorType.AGENT),
        )
    assert result.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert result.workflow["workflow_definition_version"] == 1
    assert result.workflow["retry_count"] == 1


def test_domain_has_no_framework_dependencies():
    import ast

    path = Path(__file__).parents[3] / "novel_os/domain/workflow.py"
    tree = ast.parse(path.read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all(
        not (name or "").startswith(("fastapi", "sqlalchemy", "pydantic")) for name in imports
    )
