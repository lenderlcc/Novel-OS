"""Pure prompt/model execution shared by the Worker and isolated structured smoke demo."""

from dataclasses import replace

from novel_os.prompts.compiler import PromptCompiler, PromptCompileRequest
from novel_os.prompts.contracts import ModuleRef, PromptConfigurationError
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
        self.adapter = DefaultAdapter(self.profiles)

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
        expected_output_schema=None,
    ):
        definition = self.tasks.get(task_type, expected_output_schema)
        closed_operation_tasks = {
            "PARSE_CHAPTER_REQUIREMENT",
            "PLAN_CHAPTER",
            "REVIEW_CHAPTER_PLAN",
            "WRITE_CHAPTER",
            "REVIEW_CHAPTER_COMPLIANCE",
            "REVIEW_CHAPTER_NARRATIVE",
        }
        if task_type in closed_operation_tasks and definition is self.tasks.get(task_type):
            # Current envelopes require the aligned engineering output rule. The latest
            # templates keep character tendencies conditional on supplied Context items.
            definition = replace(
                definition,
                task_template=ModuleRef(
                    module_id=definition.task_template.module_id,
                    version=self.prompts.resolve(definition.task_template).module.version,
                ),
            )
        elif (task_type, definition.output_schema.version) in {
            ("PLAN_CHAPTER", 2),
            ("REVIEW_CHAPTER_PLAN", 2),
            ("WRITE_CHAPTER", 1),
            ("REVIEW_CHAPTER_COMPLIANCE", 1),
            ("REVIEW_CHAPTER_NARRATIVE", 2),
        }:
            # These previous envelopes selected a template from their saved ContextProfile.
            # Retain that original route; older exact pins below still bypass selection.
            definition = replace(
                definition,
                task_template=ModuleRef(module_id=definition.task_template.module_id),
            )
        if task_type == "PLAN_CHAPTER" and definition.task_template.version is None:
            # A saved ContextProfile selects the immutable prompt contract. Historical
            # tasks retain v6; exploration-enabled Planning consumes selected inference.
            # The Worker estimates overhead before Context exists. Reserve the larger
            # current template then; the exact saved profile determines the real call.
            profile_data = context_payload.get("profile", {})
            version = profile_data.get("version")
            prompt_version = 9 if not context_payload else 6
            if profile_data.get("id") == "CP-004":
                prompt_version = {6: 6, 7: 7, 8: 8, 9: 9}.get(version, 6)
            exploration = prompt_version in {7, 9}
            definition = replace(
                definition,
                task_template=ModuleRef(module_id="plan-chapter", version=prompt_version),
                skills=tuple(
                    ModuleRef(module_id=skill.module_id, version=2 if exploration else 1)
                    if skill.module_id == "creative-exploration"
                    else skill
                    for skill in definition.skills
                ),
            )
        profile_prompts = {
            "EXPLORE_CHAPTER_CONCEPTS": ("CP-004E", 2, 1, 2),
            "REVIEW_CHAPTER_PLAN": ("CP-004R", 4, 4, 5),
            "WRITE_CHAPTER": ("CP-005", 7, 4, 5),
            "REVIEW_CHAPTER_COMPLIANCE": ("CP-006", 4, 1, 2),
            "REVIEW_CHAPTER_NARRATIVE": ("CP-006", 4, 2, 3),
            "PLAN_CHAPTER_REVISION": ("CP-007", 8, 6, 7),
            "REVISE_CHAPTER": ("CP-007", 8, 7, 8),
            "INTERPRET_CHAPTER_FEEDBACK": ("CP-008", 2, 2, 3),
        }
        if task_type in profile_prompts and definition.task_template.version is None:
            profile_id, context_version, old_prompt, new_prompt = profile_prompts[task_type]
            data = context_payload.get("profile", {})
            use_character_profile = not context_payload or (
                data.get("id") == profile_id and data.get("version", 0) >= context_version
            )
            definition = replace(
                definition,
                task_template=ModuleRef(
                    module_id=definition.task_template.module_id,
                    version=new_prompt if use_character_profile else old_prompt,
                ),
            )
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
