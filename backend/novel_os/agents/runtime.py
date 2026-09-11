"""Pure execution/validation layer. No service, repository, session or workflow writer."""

import json
from dataclasses import dataclass

from pydantic import ValidationError

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.provider import ModelProvider, ModelRequest, ProviderError
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.schemas import AgentResult
from novel_os.domain.agents import AgentTask, ResultStatus
from novel_os.domain.errors import DomainError

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
)


@dataclass(frozen=True)
class ExecutionResult:
    result: AgentResult | None = None
    error_code: str | None = None

    @property
    def retryable(self):
        return self.error_code in TECHNICAL_ERRORS


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class AgentRuntime:
    def __init__(self, provider: ModelProvider, registry: AgentRegistry | None = None):
        self.provider = provider
        self.registry = registry or AgentRegistry()
        self.authority = AuthorityValidator(self.registry)

    def execute(self, task: AgentTask) -> ExecutionResult:
        try:
            definition = self.authority.validate(task)
            raw = self.provider.generate(
                ModelRequest(
                    task.task_id,
                    task.task_type,
                    task.attempt_count,
                    task.target_ref,
                    definition.output_kind,
                )
            )
            if not isinstance(raw, str) or len(raw) > 150_000:
                return ExecutionResult(error_code="FORMAT_ERROR")
            try:
                body = json.loads(raw, object_pairs_hook=unique_object)
            except (ValueError, RecursionError):
                return ExecutionResult(error_code="FORMAT_ERROR")
            result = AgentResult.model_validate(body)
            if result.status == ResultStatus.SUCCESS and (
                result.result is None or result.result.kind != definition.output_kind
            ):
                return ExecutionResult(error_code="SCHEMA_PARSE_ERROR")
            self.authority.validate(task, result)
            return ExecutionResult(result=result)
        except ProviderError as exc:
            return ExecutionResult(
                error_code=exc.code if exc.code in TECHNICAL_ERRORS else "MODEL_UNAVAILABLE"
            )
        except ValidationError:
            return ExecutionResult(error_code="SCHEMA_PARSE_ERROR")
        except DomainError:
            return ExecutionResult(error_code="AUTHORITY_DENIED")
        except Exception:
            # Provider exceptions can contain credentials/request text: never persist str(exc).
            return ExecutionResult(error_code="TRANSIENT_INFRASTRUCTURE_ERROR")
