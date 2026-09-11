"""Application use cases: the sole authority for workflow transitions and transactions."""

from dataclasses import asdict, replace
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novel_os.domain.core import CommandContext, VersionToken, now
from novel_os.domain.enums import ActorType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import (
    GATE_STATES,
    TERMINAL_STATES,
    DispatchResult,
    EventCommand,
    GateDecision,
    GateStatus,
    GateType,
    GuardFailure,
    HumanGate,
    WorkflowEvent,
    WorkflowInstance,
)
from novel_os.domain.workflow import (
    ChapterState as State,
)
from novel_os.domain.workflow import (
    WorkflowStatus as RunStatus,
)
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.core_base import CoreService, validate_payload
from novel_os.services.task_scheduling import TaskScheduler
from novel_os.services.versioning import ChapterVersionService, PlanningService
from novel_os.workflow.audit import TransitionAudit, snapshot
from novel_os.workflow.definitions import (
    CONTROL_EVENTS,
    EventDispatcher,
    WorkflowDefinitionRegistry,
    digest,
)
from novel_os.workflow.fake_executor import FakeExecutor
from novel_os.workflow.guards import GuardRegistry


class Blocked(Exception):
    def __init__(self, failure: GuardFailure):
        self.failure = failure


def state_status(state: State) -> RunStatus:
    return {
        State.C00_CREATED: RunStatus.CREATED,
        State.C06_PLAN_APPROVAL: RunStatus.WAITING_HUMAN,
        State.C12_USER_REVIEW: RunStatus.WAITING_HUMAN,
        State.C16_COMPLETED: RunStatus.COMPLETED,
        State.C90_BLOCKED: RunStatus.BLOCKED,
        State.C91_FAILED: RunStatus.FAILED,
        State.C92_CANCELLED: RunStatus.CANCELLED,
    }.get(state, RunStatus.WAITING_AGENT)


class WorkflowRuntime:
    def __init__(self, session: Session, registry: WorkflowDefinitionRegistry | None = None):
        self.session = session
        self.repo = WorkflowRepository(session)
        self.core = CoreService(session)
        self.registry = registry
        self.guards = GuardRegistry(self.core)
        self.audit = TransitionAudit(self.core.repo, self.repo)
        self.tasks = TaskScheduler(session)

    def create(
        self,
        project_id: UUID,
        chapter_id: UUID,
        event_id: UUID,
        context: CommandContext,
        definition_id: str = "chapter-production",
        definition_version: int = 1,
    ) -> DispatchResult:
        context.require_user()
        command = EventCommand(
            event_id=event_id,
            event_type="CREATE",
            expected_state_version=0,
            payload={
                "project_id": str(project_id),
                "chapter_id": str(chapter_id),
                "definition_id": definition_id,
                "definition_version": definition_version,
            },
        )
        try:
            with self.session.begin():
                self.core.repo.get_project(project_id, for_update=True)
                duplicate = self._duplicate(command, context)
                if duplicate:
                    return duplicate
                self.core.require_transaction(project_id)
                chapter = self.core.repo.get_chapter(project_id, chapter_id)
                self.core.check_record_lock(chapter)
                registry = (
                    self.registry if self.registry is not None else WorkflowDefinitionRegistry()
                )
                definition = registry.get(definition_id, definition_version)
                self.repo.ensure_definition(definition)
                workflow = WorkflowInstance(
                    project_id=project_id,
                    chapter_id=chapter_id,
                    workflow_definition_id=definition.id,
                    workflow_definition_version=definition.version,
                    created_by=context.actor_id,
                    plan_version=chapter.current_plan_version,
                    draft_version=chapter.current_version,
                )
                failure = self.guards.check("writable", workflow)
                if failure:
                    raise DomainError(failure.code, failure.message)
                self.repo.add(workflow)
                self.audit.record(
                    None, workflow, command, context, ["writable"], "Create chapter workflow"
                )
                return self._remember(workflow, command, context)
        except IntegrityError as exc:
            raise DomainError("VERSION_CONFLICT", "A workflow or event already exists") from exc

    def simulate(
        self, workflow_id, event_id, expected_state_version, origin_state, outcome, context
    ):
        return self.dispatch_event(
            workflow_id,
            EventCommand(
                event_id=event_id,
                event_type="FAKE_EXECUTE",
                expected_state_version=expected_state_version,
                origin_state=origin_state,
                payload={"outcome": outcome},
            ),
            context,
        )

    def get(self, workflow_id: UUID):
        return self.repo.get(workflow_id)

    def history(self, workflow_id: UUID, limit: int = 100, offset: int = 0):
        self.repo.get(workflow_id)
        return self.repo.list_history(workflow_id, limit, offset)

    def gates(self, workflow_id: UUID, limit: int = 100, offset: int = 0):
        self.repo.get(workflow_id)
        return self.repo.list_gates(workflow_id, limit, offset)

    def decide_gate(
        self,
        gate_id: UUID,
        event_id: UUID,
        expected_state_version: int,
        expected_artifact_version: int,
        decision: GateDecision,
        reason: str,
        context: CommandContext,
    ):
        context.require_user()
        # Gate lookup and dispatch share one transaction; no pre-read autobegin leaks.
        try:
            with self.session.begin():
                gate = self.repo.gate(gate_id)
                command = EventCommand(
                    event_id=event_id,
                    event_type={
                        GateDecision.APPROVE: "USER_APPROVED",
                        GateDecision.CANCEL: "CANCEL",
                    }.get(decision, "USER_REJECTED"),
                    expected_state_version=expected_state_version,
                    payload={
                        "gate_id": str(gate_id),
                        "expected_artifact_version": expected_artifact_version,
                        "decision": decision.value,
                        "reason": reason,
                    },
                )
                return self._dispatch(gate.workflow_id, command, context, gate_id=gate_id)
        except IntegrityError as exc:
            raise DomainError(
                "VERSION_CONFLICT", "A concurrent or conflicting gate write was rejected"
            ) from exc

    def dispatch_event(self, workflow_id: UUID, command: EventCommand, context: CommandContext):
        try:
            with self.session.begin():
                return self._dispatch(workflow_id, command, context)
        except IntegrityError as exc:
            raise DomainError(
                "VERSION_CONFLICT", "A concurrent or conflicting workflow write was rejected"
            ) from exc

    def dispatch_in_transaction(self, workflow_id, command, context):
        """Compose a validated execution result with its task/run updates atomically."""
        if not self.session.in_transaction():
            raise RuntimeError("An application transaction is required")
        return self._dispatch(workflow_id, command, context)

    def _dispatch(self, workflow_id, command, context, *, gate_id=None):
        initial = self.repo.get(workflow_id)
        # Match NOVEL-002 lock ordering before reading any mutable artifact or gate.
        self.core.repo.get_project(initial.project_id, for_update=True)
        workflow = self.repo.get(workflow_id, for_update=True)
        duplicate = self._duplicate(command, context, workflow_id)
        if duplicate:
            return duplicate
        if context.actor_type != ActorType.USER:
            if context.actor_type != ActorType.AGENT or command.origin_state is None:
                raise DomainError(
                    "AUTHORITY_DENIED", "Executor events require a trusted origin token"
                )
            if (
                workflow.current_state in TERMINAL_STATES
                or command.origin_state != workflow.current_state
                or command.expected_state_version != workflow.state_version
            ):
                return self._remember(
                    workflow,
                    command,
                    context,
                    outcome="STALE_IGNORED",
                    error_code="VERSION_CONFLICT",
                )
        VersionToken(command.expected_state_version).check(workflow.state_version)
        if workflow.current_state in TERMINAL_STATES:
            raise DomainError("TERMINAL_WORKFLOW", "Terminal workflows cannot be advanced")
        if command.event_type in {"USER_APPROVED", "USER_REJECTED"} and gate_id is None:
            raise DomainError(
                "HUMAN_GATE_REQUIRED", "Submit the decision through the bound human gate"
            )
        suspended = workflow.status in {RunStatus.PAUSED, RunStatus.BLOCKED}
        corrupt = (
            (not suspended and workflow.status != state_status(workflow.current_state))
            or (suspended and (workflow.resume_state is None or workflow.resume_status is None))
            or (not suspended and workflow.resume_state is not None)
        )
        if corrupt:
            failed = self._transition(
                workflow,
                State.C91_FAILED,
                command,
                context,
                reason="Corrupted workflow state/status binding",
            )
            return self._remember(failed, command, context)
        try:
            dispatcher = EventDispatcher(
                self.repo.definition(
                    workflow.workflow_definition_id, workflow.workflow_definition_version
                )
            )
        except DomainError as exc:
            if exc.code != "INVALID_DEFINITION":
                raise
            failed = self._transition(
                workflow, State.C91_FAILED, command, context, reason="Invalid bound definition"
            )
            return self._remember(failed, command, context)
        execution_command = command
        if command.event_type == "FAKE_EXECUTE":
            if context.actor_type != ActorType.AGENT:
                raise DomainError("AUTHORITY_DENIED", "Simulation requires the fake executor")
            validate_payload(command.payload, {"outcome"})
            execution_command = FakeExecutor().execute(
                workflow,
                event_id=command.event_id,
                outcome=command.payload.get("outcome", "success"),
            )
        try:
            # A blocked guard rolls back approvals/artifacts before recording BLOCKED.
            with self.session.begin_nested():
                if gate_id is not None:
                    self._prepare_gate(workflow, gate_id, command, context)
                updated = self._advance(workflow, execution_command, context, dispatcher)
        except Blocked as exc:
            updated = self._block(workflow, command, context, exc.failure)
            error = (
                "VERSION_CONFLICT" if gate_id and exc.failure.code == "VERSION_CONFLICT" else None
            )
            return self._remember(updated, command, context, outcome="BLOCKED", error_code=error)
        return self._remember(updated, command, context)

    def _advance(self, workflow, command, context, dispatcher):
        event = command.event_type
        if event in CONTROL_EVENTS:
            return self._control(workflow, command, context, dispatcher)
        if workflow.status in {RunStatus.PAUSED, RunStatus.BLOCKED}:
            raise DomainError("INVALID_STATE", "Resume the workflow before dispatching work")
        rule = dispatcher.resolve(workflow.current_state, event)
        if context.actor_type != rule.actor:
            raise DomainError("AUTHORITY_DENIED", "This actor cannot dispatch this event")
        guards = ("writable", *rule.guards)
        # Revision consumes an existing draft, including failure edges in persisted v1 graphs.
        if rule.target == State.C10_REVISION and "draft_current" not in guards:
            guards += ("draft_current",)
        for guard in guards:
            self._check(guard, workflow)
        changes = self._effect(workflow, rule.effect, command, context)
        return self._transition(workflow, rule.target, command, context, guards=guards, **changes)

    def _effect(self, workflow, effect, command, context):
        if effect is None:
            allowed = (
                {"gate_id", "decision", "expected_artifact_version", "reason"}
                if command.event_type.startswith("USER_")
                else {"reason"}
            )
            validate_payload(command.payload, allowed)
            return {}
        service = (
            PlanningService(self.session)
            if effect == "create_plan"
            else ChapterVersionService(self.session)
        )
        expected = workflow.plan_version if effect == "create_plan" else workflow.draft_version
        try:
            record = service.create_version_in_transaction(
                workflow.project_id,
                workflow.chapter_id,
                command.payload,
                expected or 0,
                context,
                "Workflow " + command.event_type,
            )
        except DomainError as exc:
            if exc.code in {"LOCKED_OBJECT", "VERSION_CONFLICT", "NOT_FOUND", "INVALID_STATE"}:
                recovery = (
                    State.C04_CHAPTER_PLANNING
                    if effect == "create_plan"
                    else State.C08_DETERMINISTIC_CHECK
                )
                raise Blocked(
                    GuardFailure(
                        exc.code,
                        exc.message,
                        "writable",
                        recovery if exc.code == "VERSION_CONFLICT" else None,
                    )
                ) from exc
            raise
        return {"plan_version" if effect == "create_plan" else "draft_version": record.version}

    def _control(self, workflow, command, context, dispatcher):
        event = command.event_type
        if event in {"PAUSE", "RESUME", "CANCEL"}:
            context.require_user()
        elif event in {"EXECUTOR_FAILED", "FATAL_ERROR"} and context.actor_type != ActorType.AGENT:
            raise DomainError("AUTHORITY_DENIED", "Only an executor can report execution failure")
        if "gate_id" not in command.payload:
            validate_payload(command.payload, {"reason"})
        reason = command.payload.get("reason", event)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise DomainError(
                "VALIDATION_ERROR", "A nonempty reason of at most 2000 characters is required"
            )
        if event == "CANCEL":
            return self._transition(workflow, State.C92_CANCELLED, command, context, reason=reason)
        if event == "RESUME":
            if (
                workflow.status not in {RunStatus.PAUSED, RunStatus.BLOCKED}
                or workflow.resume_state is None
            ):
                raise DomainError("INVALID_STATE", "Only paused or blocked workflows can resume")
            self._check("writable", workflow)
            if workflow.blocked_guard:
                self._check(workflow.blocked_guard, workflow)
            changes = {}
            chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
            if workflow.resume_state == State.C04_CHAPTER_PLANNING:
                changes["plan_version"] = chapter.current_plan_version
            elif workflow.resume_state == State.C08_DETERMINISTIC_CHECK:
                changes["draft_version"] = chapter.current_version
            return self._transition(
                workflow,
                workflow.resume_state,
                command,
                context,
                status=workflow.resume_status,
                guards=["writable"],
                reason=reason,
                resume_state=None,
                resume_status=None,
                resume_new_stage=False,
                block_reason=None,
                blocked_guard=None,
                count_entry=workflow.resume_new_stage,
                **changes,
            )
        if workflow.status in {RunStatus.PAUSED, RunStatus.BLOCKED}:
            raise DomainError("INVALID_STATE", "Only resume or cancel is allowed while suspended")
        if event == "PAUSE":
            return self._transition(
                workflow,
                workflow.current_state,
                command,
                context,
                status=RunStatus.PAUSED,
                reason=reason,
                resume_state=workflow.current_state,
                resume_status=workflow.status,
            )
        if event == "BLOCK":
            raise Blocked(GuardFailure("EXTERNAL_CONDITION", reason, "writable"))
        if workflow.status != RunStatus.WAITING_AGENT:
            raise DomainError("ILLEGAL_TRANSITION", "This state has no executor task")
        if (
            event == "FATAL_ERROR"
            or workflow.state_retry_count >= dispatcher.definition.max_technical_retries
        ):
            return self._transition(
                workflow,
                State.C91_FAILED,
                command,
                context,
                reason=reason,
                retry_count=workflow.retry_count + (event == "EXECUTOR_FAILED"),
            )
        return self._transition(
            workflow,
            workflow.current_state,
            command,
            context,
            reason=reason,
            retry_count=workflow.retry_count + 1,
            state_retry_count=workflow.state_retry_count + 1,
        )

    def _check(self, name, workflow):
        failure = self.guards.check(name, workflow)
        if failure:
            raise Blocked(failure)

    def _prepare_gate(self, workflow, gate_id, command, context):
        context.require_user()
        gate = self.repo.gate(gate_id)
        if gate.workflow_id != workflow.id or gate.status != GateStatus.WAITING:
            raise DomainError("INVALID_STATE", "Human gate is no longer waiting")
        if (
            workflow.status != RunStatus.WAITING_HUMAN
            or GATE_STATES.get(workflow.current_state) != gate.gate_type
        ):
            raise DomainError("INVALID_STATE", "Workflow is not waiting at this human gate")
        VersionToken(command.payload["expected_artifact_version"]).check(gate.artifact_version)
        plan = gate.gate_type == GateType.PLAN_APPROVAL
        self._check("writable", workflow)
        self._check("plan_current" if plan else "draft_current", workflow)
        decision = GateDecision(command.payload["decision"])
        if decision == GateDecision.APPROVE:
            service = PlanningService(self.session) if plan else ChapterVersionService(self.session)
            artifact = service.get(workflow.project_id, workflow.chapter_id, gate.artifact_version)
            if artifact.id != gate.artifact_id:
                raise Blocked(
                    GuardFailure(
                        "VERSION_CONFLICT",
                        "Bound gate artifact changed",
                        "plan_current" if plan else "draft_current",
                    )
                )
            if artifact.status != Status.APPROVED or artifact.approved_at is None:
                service.approve_in_transaction(
                    workflow.project_id,
                    workflow.chapter_id,
                    gate.artifact_version,
                    context,
                    command.payload["reason"],
                )
        status = {
            GateDecision.APPROVE: GateStatus.APPROVED,
            GateDecision.REJECT: GateStatus.REJECTED,
            GateDecision.MODIFY: GateStatus.MODIFIED,
            GateDecision.REQUEST_ALTERNATIVE: GateStatus.MODIFIED,
            GateDecision.CANCEL: GateStatus.CANCELLED,
        }[decision]
        updated = self.repo.save(
            replace(
                gate,
                status=status,
                decision_event_id=command.event_id,
                decided_by=context.actor_id,
                decided_at=now(),
                decision=decision,
                reason=command.payload["reason"],
            )
        )
        self.audit.gate(workflow, gate, updated, context)

    def _block(self, workflow, command, context, failure):
        resume_state = failure.recovery_state or workflow.resume_state or workflow.current_state
        resume_status = (
            state_status(resume_state)
            if failure.recovery_state
            else (workflow.resume_status or workflow.status)
        )
        # A stale artifact restarts its review/planning phase; never reuses that gate.
        if failure.recovery_state:
            self._close_gate(workflow, GateStatus.STALE, context, command, failure.message)
        return self._transition(
            workflow,
            State.C90_BLOCKED,
            command,
            context,
            reason=failure.message,
            guards=[failure.guard],
            resume_state=resume_state,
            resume_status=resume_status,
            block_reason=failure.code,
            blocked_guard=None if failure.recovery_state else failure.guard,
            resume_new_stage=workflow.resume_new_stage or failure.recovery_state is not None,
        )

    def _transition(
        self,
        before,
        target,
        command,
        context,
        *,
        status=None,
        guards=(),
        reason=None,
        count_entry=True,
        **changes,
    ):
        """The only mutation of workflow state; all callers already validated the event."""
        entering = target != before.current_state
        if entering and count_entry:
            if target == State.C04_CHAPTER_PLANNING:
                changes["planning_iteration_count"] = before.planning_iteration_count + 1
            if target == State.C10_REVISION:
                changes["revision_count"] = before.revision_count + 1
        resuming_same_stage = (
            before.current_state == State.C90_BLOCKED and not before.resume_new_stage
        )
        if entering and target != State.C90_BLOCKED and not resuming_same_stage:
            changes.setdefault("state_retry_count", 0)
        if target in TERMINAL_STATES:
            self._close_gate(
                before, GateStatus.CANCELLED, context, command, reason or command.event_type
            )
            changes.update(
                resume_state=None,
                resume_status=None,
                resume_new_stage=False,
                blocked_guard=None,
                block_reason=None,
            )
        after = self.repo.save(
            replace(
                before,
                current_state=target,
                status=status or state_status(target),
                state_version=before.state_version + 1,
                updated_at=now(),
                **changes,
            )
        )
        if target in GATE_STATES and after.status == RunStatus.WAITING_HUMAN:
            self._open_gate(after, context)
        self.audit.record(before, after, command, context, guards, reason or command.event_type)
        self.tasks.synchronize(after, context)
        return after

    def _open_gate(self, workflow, context):
        if self.repo.waiting_gate(workflow.id):
            return
        plan = workflow.current_state == State.C06_PLAN_APPROVAL
        service = PlanningService(self.session) if plan else ChapterVersionService(self.session)
        version = workflow.plan_version if plan else workflow.draft_version
        artifact = service.get(workflow.project_id, workflow.chapter_id, version)
        gate = self.repo.add(
            HumanGate(
                workflow_id=workflow.id,
                gate_type=GATE_STATES[workflow.current_state],
                artifact_id=artifact.id,
                artifact_version=artifact.version,
                opened_state_version=workflow.state_version,
            )
        )
        self.audit.gate(workflow, None, gate, context)

    def _close_gate(self, workflow, status, context, command, reason):
        gate = self.repo.waiting_gate(workflow.id)
        if gate:
            closed = self.repo.save(
                replace(
                    gate,
                    status=status,
                    decision_event_id=command.event_id,
                    decided_at=now(),
                    reason=reason,
                )
            )
            self.audit.gate(workflow, gate, closed, context)

    def _fingerprint(self, command, context):
        return digest(
            {
                **snapshot(command),
                "actor_type": context.actor_type.value,
                "actor_id": context.actor_id,
            }
        )

    def _duplicate(self, command, context, workflow_id=None):
        event = self.repo.event(command.event_id)
        if event is None:
            return None
        if event.fingerprint != self._fingerprint(command, context) or (
            workflow_id and event.workflow_id != workflow_id
        ):
            raise DomainError(
                "IDEMPOTENCY_CONFLICT", "Event ID was already used for another command"
            )
        return DispatchResult(**{**event.result, "duplicate": True})

    def _remember(self, workflow, command, context, *, outcome="APPLIED", error_code=None):
        result = DispatchResult(snapshot(workflow), outcome, error_code=error_code)
        self.repo.add(
            WorkflowEvent(
                event_id=command.event_id,
                workflow_id=workflow.id,
                event_type=command.event_type,
                expected_state_version=command.expected_state_version,
                origin_state=command.origin_state,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                fingerprint=self._fingerprint(command, context),
                payload=command.payload,
                result=asdict(result),
            )
        )
        return result
