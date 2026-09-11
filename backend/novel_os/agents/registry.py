"""Fixed prototype identities and task contracts; no prompt or business agent implementation."""

from dataclasses import dataclass

from novel_os.domain.agents import AgentDefinition, AgentId, Capability
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState as State


@dataclass(frozen=True)
class TaskDefinition:
    task_type: str
    state: State
    agent_id: AgentId
    output_kind: str
    capability: Capability
    success_event: str
    quality_failure_event: str | None = None


# System-owned mappings. Provider requests/results never contain these event names.
_TASKS = (
    (
        State.C01_REQUIREMENT_INTAKE,
        AgentId.A02_REQUIREMENT,
        "INTAKE",
        "ack",
        "AGENT_SUCCEEDED",
        None,
    ),
    (State.C02_CONTEXT_ASSEMBLY, AgentId.A07_MEMORY, "CONTEXT", "ack", "CONTEXT_READY", None),
    (
        State.C03_REQUIREMENT_READY,
        AgentId.A01_ORCHESTRATOR,
        "READY",
        "ack",
        "AGENT_SUCCEEDED",
        None,
    ),
    (State.C04_CHAPTER_PLANNING, AgentId.A03_PLANNING, "PLAN", "plan", "PLAN_READY", None),
    (
        State.C05_PLAN_REVIEW,
        AgentId.A05_REVIEW,
        "PLAN_REVIEW",
        "review",
        "PLAN_REVIEW_PASSED",
        "PLAN_REVIEW_FAILED",
    ),
    (State.C07_WRITING, AgentId.A04_WRITING, "WRITE", "draft", "DRAFT_READY", None),
    (
        State.C08_DETERMINISTIC_CHECK,
        AgentId.A05_REVIEW,
        "CHECK",
        "review",
        "DETERMINISTIC_CHECK_PASSED",
        "DETERMINISTIC_CHECK_FAILED",
    ),
    (
        State.C09_INTERNAL_REVIEW,
        AgentId.A05_REVIEW,
        "REVIEW",
        "review",
        "REVIEW_PASSED",
        "REVIEW_FAILED",
    ),
    (State.C10_REVISION, AgentId.A06_REVISION, "REVISE", "draft", "REVISION_READY", None),
    (State.C11_INTERNAL_PASS, AgentId.A01_ORCHESTRATOR, "HANDOFF", "ack", "READY_FOR_USER", None),
    (
        State.C13_USER_FEEDBACK_DIAGNOSIS,
        AgentId.A02_REQUIREMENT,
        "FEEDBACK",
        "ack",
        "LOCAL_CHANGE",
        None,
    ),
    (
        State.C14_MEMORY_PREPARATION,
        AgentId.A07_MEMORY,
        "MEMORY_PREPARE",
        "ack",
        "MEMORY_CHANGESET_READY",
        None,
    ),
    (
        State.C15_MEMORY_COMMIT,
        AgentId.A01_ORCHESTRATOR,
        "COMPLETION",
        "ack",
        "MEMORY_COMMITTED",
        None,
    ),
)
KIND_CAPABILITY = {
    "ack": Capability.REPORT_RESULT,
    "plan": Capability.PROPOSE_PLAN,
    "draft": Capability.PROPOSE_DRAFT,
    "review": Capability.REVIEW,
}
TASKS = {
    "MOCK_" + name: TaskDefinition(
        "MOCK_" + name, state, agent, kind, KIND_CAPABILITY[kind], success, failure
    )
    for state, agent, name, kind, success, failure in _TASKS
}
STAGE_TASKS = {definition.state: definition for definition in TASKS.values()}


class AgentRegistry:
    def __init__(self):
        self.definitions = {
            agent: AgentDefinition(
                agent_id=agent,
                name=agent.value[4:].title(),
                mission="Execute validated mock tasks within scope; never approve or commit canon.",
                accepted_task_types=tuple(
                    t.task_type for t in TASKS.values() if t.agent_id == agent
                ),
                default_capabilities=frozenset(
                    t.capability for t in TASKS.values() if t.agent_id == agent
                ),
            )
            for agent in AgentId
        }

    def get(self, agent_id: AgentId) -> AgentDefinition:
        try:
            return self.definitions[agent_id]
        except KeyError:
            raise DomainError("AUTHORITY_DENIED", "Unknown agent") from None

    def task(self, task_type: str) -> TaskDefinition:
        try:
            return TASKS[task_type]
        except KeyError:
            raise DomainError("AUTHORITY_DENIED", "Unsupported task type") from None
