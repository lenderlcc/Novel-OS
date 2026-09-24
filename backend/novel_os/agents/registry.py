"""Fixed prototype identities and task contracts; no prompt or business agent implementation."""

from dataclasses import dataclass

from novel_os.domain.agents import AgentDefinition, AgentId, Capability
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState as State


@dataclass(frozen=True)
class StageTaskMapping:
    task_type: str
    state: State
    agent_id: AgentId
    output_kind: str
    capability: Capability
    success_event: str
    quality_failure_event: str | None = None
    result_schema: str = "mock-agent-result.v1"
    legacy_result_schema: str | None = None


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
    "MOCK_" + name: StageTaskMapping(
        "MOCK_" + name, state, agent, kind, KIND_CAPABILITY[kind], success, failure
    )
    for state, agent, name, kind, success, failure in _TASKS
}
STAGE_TASKS = {definition.state: definition for definition in TASKS.values()}

BUSINESS_STAGE_TASKS = {
    State.C01_REQUIREMENT_INTAKE: StageTaskMapping(
        "PARSE_CHAPTER_REQUIREMENT",
        State.C01_REQUIREMENT_INTAKE,
        AgentId.A02_REQUIREMENT,
        "creative_brief",
        Capability.REPORT_RESULT,
        "AGENT_SUCCEEDED",
        result_schema="chapter-requirement-result.v1",
    ),
    State.C04_CHAPTER_PLANNING: StageTaskMapping(
        "PLAN_CHAPTER",
        State.C04_CHAPTER_PLANNING,
        AgentId.A03_PLANNING,
        "chapter_plan",
        Capability.PROPOSE_PLAN,
        "PLAN_READY",
        result_schema="chapter-planning-result.v1",
    ),
    State.C05_PLAN_REVIEW: StageTaskMapping(
        "REVIEW_CHAPTER_PLAN",
        State.C05_PLAN_REVIEW,
        AgentId.A05_REVIEW,
        "plan_review",
        Capability.REVIEW,
        "PLAN_REVIEW_PASSED",
        "PLAN_REVIEW_FAILED",
        "chapter-plan-review-result.v2",
    ),
}
WRITING_TASK = StageTaskMapping(
    "WRITE_CHAPTER",
    State.C07_WRITING,
    AgentId.A04_WRITING,
    "writing_result",
    Capability.PROPOSE_DRAFT,
    "DRAFT_READY",
    result_schema="chapter-writing-result.v1",
)
QUALITY_STAGE_TASKS = {
    task: StageTaskMapping(
        task,
        State.C09_INTERNAL_REVIEW,
        AgentId.A05_REVIEW,
        kind,
        Capability.REVIEW,
        "REVIEW_PASSED",
        "REVIEW_FAILED",
        schema,
        "chapter-narrative-review.v1" if task == "REVIEW_CHAPTER_NARRATIVE" else None,
    )
    for task, kind, schema in (
        ("REVIEW_CHAPTER_COMPLIANCE", "chapter_compliance_review", "chapter-compliance-review.v1"),
        ("REVIEW_CHAPTER_NARRATIVE", "chapter_narrative_review", "chapter-narrative-review.v2"),
    )
}
TASKS.update(QUALITY_STAGE_TASKS)
TASKS[WRITING_TASK.task_type] = WRITING_TASK
TASKS.update({mapping.task_type: mapping for mapping in BUSINESS_STAGE_TASKS.values()})


class AgentRegistry:
    def __init__(self):
        self.definitions = {
            agent: AgentDefinition(
                agent_id=agent,
                name=agent.value[4:].title(),
                mission=(
                    "Write a complete Draft within the exact approved Plan; local creativity only, "
                    "major changes require escalation; never approve or commit canon."
                    if agent == AgentId.A04_WRITING
                    else "Execute validated mock tasks within scope; never approve or commit canon."
                ),
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

    def task(self, task_type: str) -> StageTaskMapping:
        try:
            return TASKS[task_type]
        except KeyError:
            raise DomainError("AUTHORITY_DENIED", "Unsupported task type") from None
