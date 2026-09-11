"""Application result handling; deterministic mapping and workflow composition live here."""

from datetime import timedelta

from pydantic import ValidationError

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.runtime import TECHNICAL_ERRORS, ExecutionResult
from novel_os.agents.schemas import AgentResult, ReviewOutput
from novel_os.domain.agents import ResultStatus, RunStatus, TaskStatus
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import EventCommand
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.task_history import RELEASE_LEASE, TaskHistory, worker_context
from novel_os.services.task_scheduling import expects_task
from novel_os.workflow.runtime import WorkflowRuntime


def valid_lease(task, lease, timestamp):
    return (
        task.status in {TaskStatus.CLAIMED, TaskStatus.RUNNING}
        and task.lease_owner == lease.worker_id
        and task.lease_token == lease.token
        and task.attempt_count == lease.attempt_number
        and task.lease_expires_at is not None
        and task.lease_expires_at > timestamp
    )


class AgentResultHandler:
    def __init__(self, session, *, retry_seconds=1.0):
        self.session = session
        self.repo = AgentTaskRepository(session)
        self.core = CoreRepository(session)
        self.workflows = WorkflowRepository(session)
        self.history = TaskHistory(session)
        self.retry_seconds = retry_seconds
        self.authority = AuthorityValidator(AgentRegistry())

    def lock_task(self, task_id):
        initial = self.repo.get(task_id)
        self.core.get_project(initial.project_id, for_update=True)
        workflow = self.workflows.get(initial.workflow_instance_id, for_update=True)
        return self.repo.get(task_id, for_update=True), workflow

    def emit(self, task, run, event, payload):
        # A run ID is also the delivery idempotency key, allocated before model execution.
        return WorkflowRuntime(self.session).dispatch_in_transaction(
            task.workflow_instance_id,
            EventCommand(
                event_id=run.run_id,
                event_type=event,
                expected_state_version=task.workflow_state_version,
                origin_state=task.workflow_state,
                payload=payload,
            ),
            CommandContext(str(run.run_id), task.agent_id.value, ActorType.AGENT),
        )

    def map_result(self, task, result):
        definition = self.authority.validate(task, result)
        if (
            result.status != ResultStatus.SUCCESS
            or result.confidence < 0.6
            or (result.escalation and result.escalation.required)
        ):
            return "BLOCK", {"reason": "Agent result requires human attention"}, TaskStatus.BLOCKED
        if result.result is None or result.result.kind != definition.output_kind:
            raise DomainError("VALIDATION_ERROR", "Result does not match the task output contract")
        event = definition.success_event
        if isinstance(result.result, ReviewOutput) and result.result.verdict == "FAIL":
            event = definition.quality_failure_event
        payload = (
            result.result.model_dump(exclude={"kind"})
            if definition.output_kind in {"plan", "draft"}
            else {}
        )
        return event, payload, TaskStatus.SUCCEEDED

    def complete(self, lease, execution: ExecutionResult):
        if not isinstance(execution, ExecutionResult):
            raise DomainError("VALIDATION_ERROR", "A validated execution result is required")
        with self.session.begin():
            task, workflow = self.lock_task(lease.task_id)
            run = self.repo.run(lease.run_id)
            if (
                run.task_id != task.task_id
                or run.lease_token != lease.token
                or run.worker_id != lease.worker_id
            ):
                raise DomainError("LEASE_LOST", "Execution lease no longer belongs to this worker")
            if run.finished_at is not None:
                return "LEASE_LOST" if run.status == RunStatus.ABANDONED else "DUPLICATE"
            if not valid_lease(task, lease, self.repo.clock()):
                return "LEASE_LOST"
            if task.status != TaskStatus.RUNNING or run.status != RunStatus.RUNNING:
                raise DomainError("INVALID_STATE", "Start the claimed attempt before completion")
            context = worker_context(lease.worker_id, run.run_id)
            result, error = execution.result, execution.error_code
            if error is None:
                try:
                    if not isinstance(result, AgentResult):
                        raise ValueError
                    result = AgentResult.model_validate(result.model_dump())
                    self.authority.validate(task, result)
                    event, payload, terminal = self.map_result(task, result)
                except (ValidationError, ValueError):
                    error = "SCHEMA_PARSE_ERROR"
                except DomainError:
                    error = "AUTHORITY_DENIED"
            elif error not in TECHNICAL_ERRORS | {"AUTHORITY_DENIED"}:
                error = "TRANSIENT_INFRASTRUCTURE_ERROR"
            metadata = (
                {
                    "result_status": result.status.value,
                    "confidence": result.confidence,
                    "kind": result.result.kind if result.result else None,
                    "verdict": result.result.verdict
                    if isinstance(result.result, ReviewOutput)
                    else None,
                    "escalation_required": bool(result.escalation and result.escalation.required)
                    or result.confidence < 0.6
                    or result.status != ResultStatus.SUCCESS,
                }
                if result is not None and error is None
                else {}
            )
            # Never save raw provider output, validation input, issue text or exception messages.
            if not expects_task(workflow, task):
                self.history.finish_run(
                    task,
                    run,
                    context,
                    RunStatus.SUCCEEDED if error is None else RunStatus.FAILED,
                    result_status=result.status if error is None else None,
                    output_metadata=metadata,
                    error_code=error,
                    disposition="STALE_IGNORED",
                )
                self.history.task(
                    task,
                    context,
                    "Stale execution result ignored",
                    status=TaskStatus.CANCELLED,
                    result_ref=run.run_id,
                    result_metadata={**metadata, "disposition": "STALE_IGNORED"},
                    completed_at=self.repo.clock(),
                    last_error_code="STALE_TASK",
                    **RELEASE_LEASE,
                )
                return "STALE_IGNORED"
            if error:
                authority_block = error == "AUTHORITY_DENIED"
                retry = error in TECHNICAL_ERRORS and task.attempt_count < task.max_attempts
                if authority_block:
                    disposition, terminal = "BLOCKED", TaskStatus.BLOCKED
                elif retry:
                    disposition, terminal = "RETRY_SCHEDULED", TaskStatus.PENDING
                else:
                    disposition, terminal = "REJECTED", TaskStatus.FAILED
                self.history.finish_run(
                    task,
                    run,
                    context,
                    RunStatus.FAILED,
                    error_code=error,
                    error_message="Agent execution or validation failed",
                    disposition=disposition,
                )
                self.history.task(
                    task,
                    context,
                    disposition,
                    status=terminal,
                    available_at=self.repo.clock()
                    + timedelta(
                        seconds=min(60, self.retry_seconds * 2 ** (task.attempt_count - 1))
                    ),
                    completed_at=None if retry else self.repo.clock(),
                    last_error_code=error,
                    last_error_message="Agent execution or validation failed",
                    result_ref=run.run_id,
                    result_metadata={
                        "disposition": disposition,
                        "escalation_required": authority_block,
                    },
                    **RELEASE_LEASE,
                )
                if authority_block:
                    self.emit(
                        task,
                        run,
                        "BLOCK",
                        {"reason": "Agent authority validation requires human attention"},
                    )
                elif not retry:
                    self.emit(
                        task,
                        run,
                        "FATAL_ERROR",
                        {"reason": "Agent technical retry budget exhausted"},
                    )
                return disposition
            self.history.task(
                task,
                context,
                "Validated agent result",
                status=terminal,
                result_ref=run.run_id,
                result_metadata=metadata,
                completed_at=self.repo.clock(),
                last_error_code=None,
                last_error_message=None,
                **RELEASE_LEASE,
            )
            dispatched = self.emit(task, run, event, payload)
            disposition = (
                "BLOCKED"
                if dispatched.outcome == "BLOCKED" or terminal == TaskStatus.BLOCKED
                else "APPLIED"
            )
            self.history.finish_run(
                task,
                run,
                context,
                RunStatus.SUCCEEDED,
                result_status=result.status,
                output_metadata=metadata,
                disposition=disposition,
            )
            return disposition
