"""Pure prompt/model execution shared by the Worker and isolated structured smoke demo."""

from novel_os.prompts.compiler import PromptCompiler, PromptCompileRequest
from novel_os.prompts.contracts import PromptConfigurationError
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import DefaultAdapter, ModelRequest, ModelResponse, ProviderError
from novel_os.providers.profiles import ModelProfileRegistry


class PromptRuntime:
    def __init__(self, provider, *, tasks=None, prompts=None, profiles=None):
        self.provider = provider
        self.tasks = tasks or TaskDefinitionRegistry()
        self.prompts = prompts or PromptRegistry()
        self.profiles = profiles or ModelProfileRegistry()
        self.compiler = PromptCompiler()
        self.adapter = DefaultAdapter()

    def prepare(
        self,
        *,
        task_id,
        task_type,
        agent_id,
        attempt,
        target_ref,
        output_kind,
        capabilities,
        constraints,
        context_payload,
    ):
        definition = self.tasks.get(task_type)
        if definition.agent_id != agent_id or not definition.capabilities <= set(capabilities):
            raise PromptConfigurationError("Task definition does not match execution scope")
        profile = self.profiles.get(definition.model_profile)
        prompt = self.compiler.compile(
            PromptCompileRequest(
                agent_id=agent_id.value,
                task_type=task_type,
                modules=definition.resolve(self.prompts),
                authority={
                    "task_id": str(task_id),
                    "target_ref": str(target_ref),
                    "capabilities": sorted(definition.capabilities),
                    "output_kind": output_kind,
                },
                constraints=tuple(constraints),
                context_payload=context_payload,
                output=definition.output_schema,
            )
        )
        return ModelRequest(task_id, task_type, attempt, target_ref, output_kind, prompt, profile)

    def generate(self, request):
        response = self.adapter.generate(self.provider, request)
        if not isinstance(response, ModelResponse):
            raise ProviderError("MODEL_OUTPUT_INVALID")
        return response
