"""Pure execution/validation layer. No service, repository, session or workflow writer."""

from dataclasses import dataclass, replace
from uuid import UUID

from pydantic import ValidationError

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.provider import ModelProvider
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.schemas import AgentResult
from novel_os.context.profiles import ContextConfigurationError, ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.agents import AgentId, AgentTask, Capability, ResultStatus
from novel_os.domain.context import ContextStatus
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import PromptConfigurationError, canonical
from novel_os.prompts.output import OutputFormatError
from novel_os.prompts.runtime import PromptRuntime
from novel_os.providers.base import ERROR_RETRYABLE, ModelRequest, ProviderError
from novel_os.providers.tokens import prompt_overhead

TECHNICAL_ERRORS = frozenset(
    {
        "MODEL_TIMEOUT",
        "MODEL_UNAVAILABLE",
        "TEMPORARY_PROVIDER_FAILURE",
        "FORMAT_ERROR",
        "SCHEMA_PARSE_ERROR",
        "TRANSIENT_INFRASTRUCTURE_ERROR",
        "LEASE_EXPIRED",
    }
    | {code for code, retryable in ERROR_RETRYABLE.items() if retryable}
)


@dataclass(frozen=True)
class ExecutionResult:
    result: AgentResult | None = None
    error_code: str | None = None
    model_metadata: dict | None = None
    context_package_id: UUID | None = None
    context_package_hash: str | None = None

    @property
    def retryable(self):
        return self.error_code in TECHNICAL_ERRORS


def execution_failure(exc):
    if isinstance(exc, ContextConfigurationError):
        return ExecutionResult(error_code="CONTEXT_CONFIGURATION_ERROR")
    if isinstance(exc, ProviderError):
        return ExecutionResult(error_code=exc.code)
    if isinstance(exc, OutputFormatError):
        return ExecutionResult(error_code="FORMAT_ERROR")
    if isinstance(exc, ValidationError):
        return ExecutionResult(error_code="SCHEMA_PARSE_ERROR")
    if isinstance(exc, PromptConfigurationError):
        return ExecutionResult(error_code="PROMPT_CONFIGURATION_ERROR")
    if isinstance(exc, DomainError):
        return ExecutionResult(error_code="AUTHORITY_DENIED")
    # Never include exception strings, raw provider output or validation inputs.
    return ExecutionResult(error_code="TRANSIENT_INFRASTRUCTURE_ERROR")


class AgentRuntime:
    def __init__(
        self,
        provider: ModelProvider,
        registry: AgentRegistry | None = None,
        *,
        tasks=None,
        prompts=None,
        profiles=None,
    ):
        self.provider = provider
        self.registry = registry or AgentRegistry()
        self.authority = AuthorityValidator(self.registry)
        self.prompts = PromptRuntime(provider, tasks=tasks, prompts=prompts, profiles=profiles)

    def profile_for_task(self, task_type):
        return self.prompts.profiles.get(self.prompts.tasks.get(task_type).model_profile)

    def prepare(self, task: AgentTask, context_package=None) -> ModelRequest | ExecutionResult:
        try:
            mapping = self.authority.validate(task)
            definition = self.prompts.tasks.get(task.task_type)
            if definition.output_schema.schema_id + ".v" + str(
                definition.output_schema.version
            ) != task.expected_output_schema or definition.capabilities != {mapping.capability}:
                raise PromptConfigurationError("Task output/capability contract mismatch")
            if context_package is not None:
                profile = ContextProfileRegistry().for_task(task.task_type)
                if (
                    context_package.build_status != ContextStatus.READY
                    or context_package.task_id != task.task_id
                    or context_package.project_id != task.project_id
                    or context_package.request.chapter_id != task.target_ref
                    or context_package.workflow_id != task.workflow_instance_id
                    or context_package.request.workflow_state_version != task.workflow_state_version
                    or context_package.request.attempt_number != task.attempt_count
                    or context_package.profile_id != profile.profile_id
                    or ContextSerializer.hash(context_package) != context_package.package_hash
                ):
                    return ExecutionResult(error_code="CONTEXT_STALE")
            request = self.prompts.prepare(
                task_id=task.task_id,
                task_type=task.task_type,
                agent_id=task.agent_id,
                attempt=task.attempt_count,
                target_ref=task.target_ref,
                output_kind=mapping.output_kind,
                capabilities=task.capabilities,
                constraints=task.constraints,
                context_payload=ContextSerializer.serialize(context_package)
                if context_package
                else {},
            )
            return replace(request, context_package=context_package)
        except Exception as exc:
            return execution_failure(exc)

    def execute(self, task: AgentTask, prepared: ModelRequest | None = None) -> ExecutionResult:
        request = prepared if prepared is not None else self.prepare(task)
        if isinstance(request, ExecutionResult):
            return request

        def finished(**values):
            package = request.context_package
            return ExecutionResult(
                **values,
                context_package_id=package.context_package_id if package else None,
                context_package_hash=package.package_hash if package else None,
            )

        response = None
        try:
            mapping = self.authority.validate(task)
            if (request.task_id, request.task_type, request.attempt_number, request.target_ref) != (
                task.task_id,
                task.task_type,
                task.attempt_count,
                task.target_ref,
            ):
                raise PromptConfigurationError("Prepared execution binding mismatch")
            if request.context_package is None:
                return finished(error_code="CONTEXT_MISSING")
            package = request.context_package
            if (
                package.build_status != ContextStatus.READY
                or (
                    package.task_id,
                    package.project_id,
                    package.workflow_id,
                    package.request.chapter_id,
                    package.request.workflow_state_version,
                )
                != (
                    task.task_id,
                    task.project_id,
                    task.workflow_instance_id,
                    task.target_ref,
                    task.workflow_state_version,
                )
                or package.request.attempt_number != task.attempt_count
                or ContextSerializer.hash(package) != package.package_hash
            ):
                return finished(error_code="CONTEXT_STALE")
            profile = ContextProfileRegistry().resolve(
                package.profile_id, package.profile_version, expected_hash=package.profile_hash
            )
            if task.task_type not in profile.allowed_task_types:
                return finished(error_code="CONTEXT_PROFILE_MISMATCH")
            data = canonical(
                {"trust": "UNTRUSTED_DATA_ONLY", "data": ContextSerializer.serialize(package)}
            )
            if [
                message.content
                for message in request.prompt.messages
                if message.layer == "CONTEXT_DATA"
            ] != [data]:
                raise PromptConfigurationError("Context/prompt binding mismatch")
            response = self.prompts.generate(request)
            result = request.prompt.output.parse(response.content)
            if result.status == ResultStatus.SUCCESS and (
                result.result is None or result.result.kind != mapping.output_kind
            ):
                return finished(
                    error_code="SCHEMA_PARSE_ERROR", model_metadata=response.safe_summary()
                )
            self.authority.validate(task, result)
            return finished(result=result, model_metadata=response.safe_summary())
        except Exception as exc:
            failure = execution_failure(exc)
            return finished(
                error_code=failure.error_code,
                model_metadata=response.safe_summary() if response else None,
            )

    def execute_smoke(self, user_text: str) -> ExecutionResult:
        """Isolated A02 demo. No AgentTask persistence, scheduling, result handler or workflow."""
        from uuid import uuid4

        task_id = uuid4()
        try:
            from novel_os.context.engine import ContextEngine
            from novel_os.context.inputs import task_item
            from novel_os.domain.context import CandidateBatch, ContextRequest
            from novel_os.domain.core import now

            profile = ContextProfileRegistry().resolve("CP-000")
            context_request = ContextRequest(
                project_id=task_id,
                task_id=task_id,
                task_type="INTERNAL_SMOKE_TEST",
                chapter_id=task_id,
                objective=user_text,
            )

            def compile_context(payload):
                return self.prompts.prepare(
                    task_id=task_id,
                    task_type="INTERNAL_SMOKE_TEST",
                    agent_id=AgentId.A02_REQUIREMENT,
                    attempt=1,
                    target_ref=task_id,
                    output_kind="requirement_demo",
                    capabilities=[Capability.REPORT_RESULT],
                    constraints=[],
                    context_payload=payload,
                )

            skeleton = compile_context({})
            built = ContextEngine().build(
                context_request,
                profile,
                CandidateBatch((task_item(context_request, profile.selectors[0], now()),)),
                prompt_overhead=prompt_overhead(skeleton),
                output_reservation=skeleton.profile.max_output_tokens,
            )
            if built.status != ContextStatus.READY:
                return ExecutionResult(error_code=built.error_code)
            request = replace(
                compile_context(ContextSerializer.serialize(built.package)),
                context_package=built.package,
            )
            response = self.prompts.generate(request)
            result = request.prompt.output.parse(response.content)
            if result.task_id != task_id or result.proposed_changes or result.memory_proposals:
                raise DomainError("AUTHORITY_DENIED", "Smoke tasks may only report results")
            if result.status == ResultStatus.SUCCESS and result.result is None:
                return ExecutionResult(error_code="SCHEMA_PARSE_ERROR")
            return ExecutionResult(result=result, model_metadata=response.safe_summary())
        except Exception as exc:
            return execution_failure(exc)
