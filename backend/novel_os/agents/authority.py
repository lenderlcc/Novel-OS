from novel_os.agents.registry import STAGE_TASKS, AgentRegistry
from novel_os.agents.schemas import AgentResult
from novel_os.domain.agents import FORBIDDEN_CAPABILITIES, AgentTask, Capability
from novel_os.domain.errors import DomainError


class AuthorityValidator:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def validate(self, task: AgentTask, result: AgentResult | None = None):
        agent = self.registry.get(task.agent_id)
        definition = self.registry.task(task.task_type)
        try:
            scope = frozenset(Capability(value) for value in task.capabilities)
        except ValueError:
            raise DomainError("AUTHORITY_DENIED", "Unknown task capability") from None
        if (
            not agent.enabled
            or task.task_type not in agent.accepted_task_types
            or definition.agent_id != task.agent_id
            or STAGE_TASKS.get(task.workflow_state) != definition
            or task.expected_output_schema != agent.result_schema
            or scope & FORBIDDEN_CAPABILITIES
        ):
            raise DomainError("AUTHORITY_DENIED", "Task identity, state or capability is invalid")
        allowed = agent.default_capabilities & {definition.capability} & scope
        if definition.capability not in allowed:
            raise DomainError("AUTHORITY_DENIED", "Task does not grant the required capability")
        if result is not None:
            if result.task_id != task.task_id or result.memory_proposals:
                raise DomainError("AUTHORITY_DENIED", "Result is outside this task scope")
            for proposal in result.proposed_changes:
                if proposal.capability not in allowed or proposal.target_ref != task.target_ref:
                    raise DomainError(
                        "AUTHORITY_DENIED", "Proposed operation exceeds task authority"
                    )
        return definition
