"""Execution configuration only. Workflow event mapping remains in agents.registry."""

from dataclasses import dataclass

from novel_os.agents.demo_schema import SmokeAgentResult
from novel_os.agents.registry import TASKS
from novel_os.agents.schemas import AgentResult
from novel_os.domain.agents import AgentId, Capability
from novel_os.prompts.contracts import ModuleRef, ModuleType, PromptConfigurationError
from novel_os.prompts.output import OutputContract, OutputContractGenerator


@dataclass(frozen=True)
class TaskDefinition:
    task_type: str
    agent_id: AgentId
    system_policy: ModuleRef
    agent_role: ModuleRef
    task_template: ModuleRef
    skills: tuple[ModuleRef, ...]
    quality_profile: ModuleRef
    output_schema: OutputContract
    model_profile: str
    capabilities: frozenset[Capability]
    retry_policy: str = "agent-task-attempt-budget.v1"

    def resolve(self, registry):
        layers = [
            (self.system_policy, ModuleType.SYSTEM_POLICY),
            (self.agent_role, ModuleType.AGENT_ROLE),
            (self.task_template, ModuleType.TASK_TEMPLATE),
            *((ref, ModuleType.SKILL) for ref in self.skills),
            (self.quality_profile, ModuleType.QUALITY_PROFILE),
        ]
        resolved = []
        for ref, kind in layers:
            module = registry.resolve(ref)
            if module.module.module_type != kind:
                raise PromptConfigurationError("Task references the wrong prompt layer")
            resolved.append(module)
        return tuple(resolved)


def ref(module_id):
    return ModuleRef(module_id=module_id)


class TaskDefinitionRegistry:
    def __init__(self, *, model_profile="mock-default"):
        output = OutputContractGenerator.generate("mock-agent-result", 1, AgentResult)
        self._definitions = {}
        for mapping in TASKS.values():
            self.register(
                TaskDefinition(
                    mapping.task_type,
                    mapping.agent_id,
                    ref("novel-os-core"),
                    ref("simulation-role"),
                    ref("simulation-" + mapping.output_kind),
                    (ref("structured-reporting"),),
                    ref("runtime-quality"),
                    output,
                    model_profile,
                    frozenset({mapping.capability}),
                )
            )
        self.register(
            TaskDefinition(
                "INTERNAL_SMOKE_TEST",
                AgentId.A02_REQUIREMENT,
                ref("novel-os-core"),
                ref("requirement-demo-role"),
                ref("requirement-demo"),
                (ref("structured-reporting"),),
                ref("runtime-quality"),
                OutputContractGenerator.generate("requirement-smoke-result", 1, SmokeAgentResult),
                model_profile,
                frozenset({Capability.REPORT_RESULT}),
            )
        )

    def register(self, definition):
        if definition.task_type in self._definitions:
            raise PromptConfigurationError("Conflicting task definition")
        self._definitions[definition.task_type] = definition

    def get(self, task_type):
        try:
            return self._definitions[task_type]
        except KeyError:
            raise PromptConfigurationError("Unknown prompt task definition") from None
