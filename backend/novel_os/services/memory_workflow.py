"""Completion uses the established C14/C15/C16 states and user event fencing."""

from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.memory import MemoryRequest
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.services.core_base import validate_payload
from novel_os.services.memory_commit import MemoryCommitService

MEMORY_EVENTS = {"REQUEST_COMPLETION", "MEMORY_PROPOSAL_READY", "CONFIRM_MEMORY", "DISCARD_MEMORY"}


def advance_memory(runtime, workflow, command, context):
    service = MemoryCommitService(runtime.session)
    if command.event_type == "REQUEST_COMPLETION":
        runtime._check("writable", workflow)
        request = service.prepare(workflow, command, context)
        return runtime._transition(
            workflow,
            ChapterState.C14_MEMORY_PREPARATION,
            command,
            context,
            status=WorkflowStatus.WAITING_AGENT,
            memory_request_id=request.id,
            draft_version=request.draft_version,
            count_entry=False,
        )
    if not workflow.memory_request_id:
        raise DomainError("INVALID_STATE", "No active chapter completion")
    request = service.repo.get(MemoryRequest, workflow.memory_request_id)
    if command.event_type == "DISCARD_MEMORY":
        context.require_user()
        validate_payload(command.payload, {"request_id", "reason"})
        if (
            str(request.id) != command.payload["request_id"]
            or (workflow.resume_state or workflow.current_state)
            not in {ChapterState.C14_MEMORY_PREPARATION, ChapterState.C15_MEMORY_COMMIT}
            or workflow.status == WorkflowStatus.COMPLETED
        ):
            raise DomainError("INVALID_STATE", "Only pending completion can be cancelled")
        chapter = runtime.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        return runtime._transition(
            workflow,
            ChapterState(request.return_state),
            command,
            context,
            status=WorkflowStatus.WAITING_HUMAN,
            memory_request_id=None,
            draft_version=chapter.current_version,
            resume_state=None,
            resume_status=None,
            resume_new_stage=False,
            block_reason=None,
            blocked_guard=None,
            count_entry=False,
        )
    runtime._check("writable", workflow)
    service.check(request, workflow)
    if command.event_type == "MEMORY_PROPOSAL_READY":
        validate_payload(command.payload, {"proposal_id"})
        proposal = service.repo.proposal(request.id)
        if (
            context.actor_type != ActorType.AGENT
            or workflow.current_state != ChapterState.C14_MEMORY_PREPARATION
            or workflow.status != WorkflowStatus.WAITING_AGENT
            or proposal is None
            or str(proposal.id) != command.payload["proposal_id"]
            or proposal.agent_run_id != command.event_id
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Memory proposal completion requires its recorded A07 run"
            )
        return runtime._transition(
            workflow,
            ChapterState.C15_MEMORY_COMMIT,
            command,
            context,
            status=WorkflowStatus.WAITING_HUMAN,
            count_entry=False,
        )
    if (
        workflow.current_state != ChapterState.C15_MEMORY_COMMIT
        or workflow.status != WorkflowStatus.WAITING_HUMAN
    ):
        raise DomainError("INVALID_STATE", "Memory confirmation requires a pending proposal")
    service.commit(workflow, command, context)
    return runtime._transition(
        workflow,
        ChapterState.C16_COMPLETED,
        command,
        context,
        status=WorkflowStatus.COMPLETED,
        count_entry=False,
    )
