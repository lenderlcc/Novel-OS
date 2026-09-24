"""Quality workflow controls. No revision agent or automatic rewriting."""

from dataclasses import replace
from uuid import uuid5

from novel_os.domain.core import CommandContext, VersionToken
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState, EventCommand, WorkflowStatus
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.core_base import CoreService, validate_payload
from novel_os.services.quality_binding import supports_quality
from novel_os.services.writing_binding import WritingBindingService


class QualityReviewControl:
    """Explicit user rebinds; never reuse stale passes or silently adopt a new Draft."""

    def __init__(self, session):
        self.session = session

    def can_resume(self, workflow):
        if not supports_quality(workflow) or workflow.status not in {
            WorkflowStatus.PAUSED,
            WorkflowStatus.BLOCKED,
        }:
            return False
        if workflow.resume_state == ChapterState.C09_INTERNAL_REVIEW:
            return True
        # Recover instances blocked by the old draft_current guard during re-review.
        # A Writing-only C08 handoff must still preserve its checked Draft binding.
        return (
            workflow.resume_state == ChapterState.C08_DETERMINISTIC_CHECK
            and QualityRepository(self.session).latest_binding(workflow.id) is not None
        )

    def prepare(self, workflow, command, context):
        context.require_user()
        validate_payload(command.payload, {"reason", "expected_draft_version"})
        ready = workflow.status == WorkflowStatus.WAITING_HUMAN and workflow.current_state in {
            ChapterState.C10_REVISION,
            ChapterState.C11_INTERNAL_PASS,
        }
        if not supports_quality(workflow) or not (ready or self.can_resume(workflow)):
            raise DomainError("INVALID_STATE", "Review requires a completed or suspended review")
        expected = command.payload.get("expected_draft_version")
        if command.event_type == "RESUME" and expected is None:
            # Backward-compatible resume is safe only while the bound Draft is current.
            expected = workflow.draft_version
        chapter = CoreService(self.session).repo.get_chapter(
            workflow.project_id, workflow.chapter_id
        )
        VersionToken(expected).check(chapter.current_version or 0)
        if not expected:
            raise DomainError("CONTEXT_MISSING", "Review requires an existing Draft")
        return replace(
            workflow, current_state=ChapterState.C09_INTERNAL_REVIEW, draft_version=expected
        )

    def recovery_failure(self, workflow):
        # Reuse the existing Brief/approved Plan recovery policy before scheduling.
        # A changed Plan or Brief requires replanning/intake, not a new review snapshot.
        return WritingBindingService(self.session).recovery_failure(
            replace(workflow, current_state=ChapterState.C08_DETERMINISTIC_CHECK)
        )


def advance_quality_check(session, workflow_id, run_id):
    from novel_os.workflow.runtime import WorkflowRuntime

    workflow = WorkflowRepository(session).get(workflow_id)
    if (
        not supports_quality(workflow)
        or workflow.current_state != ChapterState.C08_DETERMINISTIC_CHECK
    ):
        return
    # Writing completion has already checked persisted body, schema and exact Plan.
    # All review input bindings are captured transactionally by the C09 task factory.
    WorkflowRuntime(session).dispatch_in_transaction(
        workflow_id,
        EventCommand(
            event_id=uuid5(run_id, "quality-check"),
            event_type="DETERMINISTIC_CHECK_PASSED",
            expected_state_version=workflow.state_version,
            origin_state=workflow.current_state,
            payload={},
        ),
        CommandContext(str(run_id), "quality-control", ActorType.SYSTEM),
    )
