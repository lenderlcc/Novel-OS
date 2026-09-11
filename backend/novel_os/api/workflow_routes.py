from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Request

from novel_os.api import workflow_schemas as dto
from novel_os.api.core_routes import Context, DbSession, Limit, Offset
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import EventCommand
from novel_os.workflow.runtime import WorkflowRuntime

router = APIRouter(tags=["chapter-workflow"])


def response(result):
    # The runtime commits the stale gate/block evidence before HTTP reports a conflict.
    if result.error_code:
        raise DomainError(
            result.error_code, "Workflow or artifact version changed; reload before a new command"
        )
    return asdict(result)


@router.post("/workflows/chapter", response_model=dto.DispatchView, status_code=201)
def create_workflow(body: dto.CreateWorkflow, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).create(
            body.project_id,
            body.chapter_id,
            body.event_id,
            context,
            body.definition_id,
            body.definition_version,
        )
    )


@router.get("/workflows/{workflow_id}", response_model=dto.WorkflowView)
def get_workflow(workflow_id: UUID, session: DbSession):
    return asdict(WorkflowRuntime(session).get(workflow_id))


@router.post("/workflows/{workflow_id}/events", response_model=dto.DispatchView)
def dispatch_event(workflow_id: UUID, body: dto.EventInput, session: DbSession, context: Context):
    command = EventCommand(
        event_id=body.event_id,
        event_type=body.event_type,
        expected_state_version=body.expected_state_version,
        payload={"reason": body.reason},
    )
    return response(WorkflowRuntime(session).dispatch_event(workflow_id, command, context))


def control(workflow_id, body, session, context, event):
    return response(
        WorkflowRuntime(session).dispatch_event(
            workflow_id,
            EventCommand(
                event_id=body.event_id,
                event_type=event,
                expected_state_version=body.expected_state_version,
                payload={"reason": body.reason},
            ),
            context,
        )
    )


@router.post("/workflows/{workflow_id}/pause", response_model=dto.DispatchView)
def pause(workflow_id: UUID, body: dto.CommandInput, session: DbSession, context: Context):
    return control(workflow_id, body, session, context, "PAUSE")


@router.post("/workflows/{workflow_id}/resume", response_model=dto.DispatchView)
def resume(workflow_id: UUID, body: dto.CommandInput, session: DbSession, context: Context):
    return control(workflow_id, body, session, context, "RESUME")


@router.post("/workflows/{workflow_id}/cancel", response_model=dto.DispatchView)
def cancel(workflow_id: UUID, body: dto.CommandInput, session: DbSession, context: Context):
    return control(workflow_id, body, session, context, "CANCEL")


@router.get("/workflows/{workflow_id}/history", response_model=list[dto.TransitionView])
def history(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [asdict(item) for item in WorkflowRuntime(session).history(workflow_id, limit, offset)]


@router.get("/workflows/{workflow_id}/human-gates", response_model=list[dto.GateView])
def gates(workflow_id: UUID, session: DbSession, limit: Limit = 100, offset: Offset = 0):
    return [asdict(item) for item in WorkflowRuntime(session).gates(workflow_id, limit, offset)]


@router.post("/human-gates/{gate_id}/decision", response_model=dto.DispatchView)
def decide(gate_id: UUID, body: dto.GateInput, session: DbSession, context: Context):
    return response(
        WorkflowRuntime(session).decide_gate(
            gate_id,
            body.event_id,
            body.expected_state_version,
            body.expected_artifact_version,
            body.decision,
            body.reason,
            context,
        )
    )


@router.post("/workflows/{workflow_id}/fake-execute", response_model=dto.DispatchView)
def fake_execute(
    workflow_id: UUID, body: dto.FakeInput, request: Request, session: DbSession, context: Context
):
    if not request.app.state.settings.workflow_fake_executor_enabled:
        raise DomainError("NOT_FOUND", "Fake executor is disabled")
    actor = CommandContext(context.request_id, "fake-executor", ActorType.AGENT)
    return response(
        WorkflowRuntime(session).simulate(
            workflow_id,
            body.event_id,
            body.expected_state_version,
            body.origin_state,
            body.outcome,
            actor,
        )
    )
