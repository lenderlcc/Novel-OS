"""Explicit human feedback controls on the existing C13 / C10 workflow states."""

from uuid import uuid5

from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.feedback import FeedbackAction
from novel_os.domain.revision import RevisionRequest
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.feedback.policy import directed_contract
from novel_os.feedback.schemas import FeedbackInterpretationOutput
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.feedback import FeedbackRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.services.core_base import validate_payload
from novel_os.services.feedback_binding import FeedbackBindingService

FEEDBACK_EVENTS = {"REQUEST_FEEDBACK", "FEEDBACK_READY", "DISCARD_FEEDBACK"}


def advance_feedback(runtime, workflow, command, context):
    service = FeedbackBindingService(runtime.session)
    if command.event_type == "DISCARD_FEEDBACK":
        context.require_user()
        validate_payload(command.payload, {"feedback_id", "reason"})
        stage = workflow.resume_state or workflow.current_state
        if (
            stage != ChapterState.C13_USER_FEEDBACK_DIAGNOSIS
            or workflow.status
            not in {WorkflowStatus.WAITING_AGENT, WorkflowStatus.PAUSED, WorkflowStatus.BLOCKED}
            or not workflow.human_feedback_id
            or str(workflow.human_feedback_id) != command.payload["feedback_id"]
            or workflow.revision_request_id is not None
        ):
            raise DomainError(
                "INVALID_STATE", "Only the active feedback interpretation can be discarded"
            )
        feedback = service.repo.get(workflow.human_feedback_id)
        chapter = runtime.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        # Discarding does not accept stale input or mutate prose/authority. The next
        # explicit submission captures fresh inputs through the normal prepare path.
        return runtime._transition(
            workflow,
            ChapterState(feedback.return_state),
            command,
            context,
            status=WorkflowStatus.WAITING_HUMAN,
            human_feedback_id=None,
            draft_version=chapter.current_version,
            resume_state=None,
            resume_status=None,
            resume_new_stage=False,
            block_reason=None,
            blocked_guard=None,
            count_entry=False,
        )
    runtime._check("writable", workflow)
    if command.event_type == "REQUEST_FEEDBACK":
        feedback = service.prepare(workflow, command, context)
        return runtime._transition(
            workflow,
            ChapterState.C13_USER_FEEDBACK_DIAGNOSIS,
            command,
            context,
            status=WorkflowStatus.WAITING_AGENT,
            human_feedback_id=feedback.id,
            draft_version=feedback.source_draft_version,
            count_entry=False,
        )
    if (
        context.actor_type != ActorType.AGENT
        or workflow.current_state != ChapterState.C13_USER_FEEDBACK_DIAGNOSIS
        or workflow.status != WorkflowStatus.WAITING_AGENT
        or not workflow.human_feedback_id
    ):
        raise DomainError("AUTHORITY_DENIED", "Feedback completion requires its active A02 task")
    validate_payload(command.payload, {"interpretation_id"})
    feedback = service.check(service.repo.get(workflow.human_feedback_id), workflow)
    record = service.repo.interpretation(feedback.id)
    if (
        record is None
        or str(record.id) != command.payload["interpretation_id"]
        or record.run_id != command.event_id
    ):
        raise DomainError("AUTHORITY_DENIED", "Feedback completion requires its recorded run")
    output = FeedbackInterpretationOutput.model_validate(record.body)
    if output.action != FeedbackAction.REVISION:
        return runtime._transition(
            workflow,
            ChapterState(feedback.return_state),
            command,
            context,
            status=WorkflowStatus.WAITING_HUMAN,
            human_feedback_id=None,
            count_entry=False,
        )
    package = ContextPackageRepository(runtime.session).get(record.context_package_id)
    request = RevisionRepository(runtime.session).add(
        RevisionRequest(
            id=uuid5(feedback.id, "directed-revision"),
            project_id=feedback.project_id,
            chapter_id=feedback.chapter_id,
            workflow_id=workflow.id,
            source_chapter_version_id=feedback.source_chapter_version_id,
            source_feedback_id=feedback.id,
            source_review_id=feedback.source_review_id
            if output.supporting_review_issue_ids
            else None,
            source_binding_id=None,
            source_context_package_id=package.context_package_id,
            profile_json=ContextProfileRegistry()
            .for_task("PLAN_CHAPTER_REVISION")
            .model_dump_json(),
            contract=directed_contract(feedback, output, package),
        )
    )
    return runtime._transition(
        workflow,
        ChapterState.C10_REVISION,
        command,
        context,
        status=WorkflowStatus.WAITING_AGENT,
        revision_request_id=request.id,
        human_feedback_id=None,
        revision_count=workflow.revision_count + 1,
        count_entry=False,
    )


def check_resume(session, workflow):
    if (
        workflow.resume_state != ChapterState.C13_USER_FEEDBACK_DIAGNOSIS
        or not workflow.human_feedback_id
    ):
        return
    service = FeedbackBindingService(session)
    service.check(service.repo.get(workflow.human_feedback_id), workflow)
    if FeedbackRepository(session).interpretation(workflow.human_feedback_id):
        raise DomainError(
            "INVALID_STATE", "Interpreted feedback needs an explicit new user decision"
        )
