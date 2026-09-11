import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.domain.agents import AgentId, AgentTask, Capability
from novel_os.domain.workflow import ChapterState
from novel_os.prompts.registry import PromptRegistry


@pytest.fixture
def prompt_task():
    return AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=ChapterState.C04_CHAPTER_PLANNING,
        workflow_state_version=5,
        agent_id=AgentId.A03_PLANNING,
        task_type="MOCK_PLAN",
        objective="Simulation",
        target_ref=uuid4(),
        capabilities=[Capability.PROPOSE_PLAN],
        attempt_count=1,
    )


@pytest.fixture
def prepared(prompt_task):
    return AgentRuntime(MockModelProvider()).prepare(prompt_task)


@pytest.fixture
def library(tmp_path):
    import novel_os.prompts

    root = tmp_path / "prompts"
    shutil.copytree(Path(novel_os.prompts.__file__).parent / "library", root)
    return root


@pytest.fixture
def role_manifest(library):
    return library / "agents/simulation-role/v1/manifest.json"


@pytest.fixture
def registry(library):
    return PromptRegistry(library)
