"""Pure execution/validation layer. No service, repository, session or workflow writer."""

from dataclasses import dataclass

from pydantic import ValidationError

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.provider import ModelProvider
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.schemas import AgentResult
from novel_os.domain.agents import AgentId, AgentTask, Capability, ResultStatus
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import PromptConfigurationError
from novel_os.prompts.output import OutputFormatError
from novel_os.prompts.runtime import PromptRuntime
from novel_os.providers.base import ERROR_RETRYABLE, ModelRequest, ProviderError

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

    @property
    def retryable(self):
        return self.error_code in TECHNICAL_ERRORS


def execution_failure(exc):
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

    def prepare(self, task: AgentTask) -> ModelRequest | ExecutionResult:
        try:
            mapping = self.authority.validate(task)
            definition = self.prompts.tasks.get(task.task_type)
            if definition.output_schema.schema_id + ".v" + str(
                definition.output_schema.version
            ) != task.expected_output_schema or definition.capabilities != {mapping.capability}:
                raise PromptConfigurationError("Task output/capability contract mismatch")
            return self.prompts.prepare(
                task_id=task.task_id,
                task_type=task.task_type,
                agent_id=task.agent_id,
                attempt=task.attempt_count,
                target_ref=task.target_ref,
                output_kind=mapping.output_kind,
                capabilities=task.capabilities,
                constraints=task.constraints,
                context_payload={"objective": task.objective, "requirements": task.requirements},
            )
        except Exception as exc:
            return execution_failure(exc)

    def execute(self, task: AgentTask, prepared: ModelRequest | None = None) -> ExecutionResult:
        request = prepared if prepared is not None else self.prepare(task)
        if isinstance(request, ExecutionResult):
            return request
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
            response = self.prompts.generate(request)
            result = request.prompt.output.parse(response.content)
            if result.status == ResultStatus.SUCCESS and (
                result.result is None or result.result.kind != mapping.output_kind
            ):
                return ExecutionResult(
                    error_code="SCHEMA_PARSE_ERROR", model_metadata=response.safe_summary()
                )
            self.authority.validate(task, result)
            return ExecutionResult(result=result, model_metadata=response.safe_summary())
        except Exception as exc:
            failure = execution_failure(exc)
            return ExecutionResult(
                error_code=failure.error_code,
                model_metadata=response.safe_summary() if response else None,
            )

    def execute_smoke(self, user_text: str) -> ExecutionResult:
        """Isolated A02 demo. No AgentTask persistence, scheduling, result handler or workflow."""
        from uuid import uuid4

        task_id = uuid4()
        try:
            request = self.prompts.prepare(
                task_id=task_id,
                task_type="INTERNAL_SMOKE_TEST",
                agent_id=AgentId.A02_REQUIREMENT,
                attempt=1,
                target_ref=task_id,
                output_kind="requirement_demo",
                capabilities=[Capability.REPORT_RESULT],
                constraints=[],
                context_payload={"user_text": user_text},
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
