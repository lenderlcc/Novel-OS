"""Explicit controls on the existing C10 → C08 → C09 path, never an automatic loop."""

from novel_os.domain.agents import TaskStatus
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.revision import RevisionResult
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.services.core_base import validate_payload
from novel_os.services.revision_binding import RevisionBindingService
from novel_os.services.revision_results import RevisionResultService

REVISION_EVENTS = {"REQUEST_REVISION", "REVISION_PLAN_READY", "REVISION_READY"}


def advance_revision(runtime, workflow, command, context):
    runtime._check("writable", workflow)
    if command.event_type == "REQUEST_REVISION":
        request = RevisionBindingService(runtime.session).prepare(workflow, command, context)
        return runtime._transition(
            workflow,
            ChapterState.C10_REVISION,
            command,
            context,
            status=WorkflowStatus.WAITING_AGENT,
            revision_request_id=request.id,
            revision_count=workflow.revision_count + 1,
            count_entry=False,
        )
    if (
        context.actor_type != ActorType.AGENT
        or workflow.current_state != ChapterState.C10_REVISION
        or workflow.status != WorkflowStatus.WAITING_AGENT
        or workflow.revision_request_id is None
    ):
        raise DomainError("AUTHORITY_DENIED", "Revision completion requires an active owned task")
    validate_payload(command.payload, {"revision_artifact_id"})
    version = RevisionResultService(runtime.session).check_persisted(
        workflow, command.payload["revision_artifact_id"], command.event_id, command.event_type
    )
    return runtime._transition(
        workflow,
        ChapterState.C08_DETERMINISTIC_CHECK if version else ChapterState.C10_REVISION,
        command,
        context,
        status=WorkflowStatus.WAITING_AGENT,
        count_entry=False,
        **({"draft_version": version.version} if version else {}),
    )


def check_resume(session, workflow):
    if workflow.revision_request_id is None or workflow.resume_state != ChapterState.C10_REVISION:
        return
    service = RevisionBindingService(session)
    request = service.repo.get(workflow.revision_request_id)
    service.check_source(request, workflow)
    plan = RevisionRepository(session).evidence(request.id)
    result = service.repo.evidence(request.id, RevisionResult)
    blocked_plan = plan and (
        not plan.body["revision_targets"]
        or AgentTaskRepository(session).get(plan.task_id).status == TaskStatus.BLOCKED
    )
    if result or blocked_plan:
        raise DomainError(
            "INVALID_STATE",
            "Blocked Revision needs new source evidence and an explicit new request",
        )
