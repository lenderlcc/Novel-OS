"""Freeze a Draft and its approved inputs without changing Brief or Review."""

from dataclasses import replace
from uuid import UUID

from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.domain.agents import AgentId, AgentTask
from novel_os.domain.core import ObjectRef
from novel_os.domain.enums import ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.feedback import FEEDBACK_TASK, HumanFeedback
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.repositories.feedback import FeedbackRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.services.core_base import CoreService, validate_payload
from novel_os.services.quality_binding import QualityBindingService, supports_quality


class FeedbackBindingService:
    def __init__(self, session):
        self.session = session
        self.repo = FeedbackRepository(session)
        self.core = CoreService(session)

    def snapshot(self, workflow, profile, created_at):
        task = AgentTask(
            project_id=workflow.project_id,
            workflow_instance_id=workflow.id,
            workflow_state=ChapterState.C13_USER_FEEDBACK_DIAGNOSIS,
            workflow_state_version=workflow.state_version,
            agent_id=AgentId.A02_REQUIREMENT,
            task_type=FEEDBACK_TASK,
            target_ref=workflow.chapter_id,
            objective="Interpret user feedback",
            expected_output_schema="chapter-feedback-result.v1",
            created_at=created_at,
        )
        data = QualityBindingService(self.session).current(task, workflow, profile)
        data.pop("state_version")
        data["source_snapshots"] = [
            s
            for s in data["source_snapshots"]
            if s["selector_id"] not in {"human-feedback", "feedback-review"}
        ]
        if not data["profile_record_id"]:
            raise DomainError("CONTEXT_MISSING", "Feedback requires an approved Writing Profile")
        # Store the same JSON representation that will be read after persistence.
        from pydantic_core import to_jsonable_python

        return to_jsonable_python(data)

    def prepare(self, workflow, command, context):
        context.require_user()
        validate_payload(
            command.payload,
            {"raw_feedback", "source_chapter_version_id", "reply_to_feedback_id", "reason"},
        )
        if (
            not supports_quality(workflow)
            or workflow.status != WorkflowStatus.WAITING_HUMAN
            or workflow.current_state
            not in {ChapterState.C10_REVISION, ChapterState.C11_INTERNAL_PASS}
            or workflow.revision_request_id is not None
            or workflow.human_feedback_id is not None
        ):
            raise DomainError("INVALID_STATE", "Feedback requires an idle current Draft")
        raw = command.payload["raw_feedback"]
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw or len(raw) > 12000:
            raise DomainError("VALIDATION_ERROR", "Feedback must contain 1–12000 characters")
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        self.core.check_record_lock(chapter)
        self.core.check_lock(workflow.project_id, ObjectRef(ObjectType.CHAPTER_VERSION, chapter.id))
        draft = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION, workflow.project_id, chapter.id, chapter.current_version
        )
        if draft.id != UUID(command.payload["source_chapter_version_id"]):
            raise DomainError("VERSION_CONFLICT", "Feedback must target the exact current Draft")
        reply_to = command.payload.get("reply_to_feedback_id")
        if reply_to is not None:
            parent = self.repo.get(UUID(reply_to))
            latest = self.repo.history(workflow.id, 1, 0)
            interpretation = self.repo.interpretation(parent.id)
            if (
                parent.workflow_id != workflow.id
                or parent.source_chapter_version_id != draft.id
                or not latest
                or latest[0][0].id != parent.id
                or interpretation is None
                or interpretation.body["action"] != "USER_DECISION_REQUIRED"
            ):
                raise DomainError(
                    "VERSION_CONFLICT", "Reply must answer the current Draft's latest question"
                )
        reviews = QualityRepository(self.session).history(workflow.project_id, chapter.id, 100)
        review = next((r for r in reviews if r.chapter_version_id == draft.id), None)
        profile = ContextProfileRegistry().for_task(FEEDBACK_TASK)
        from novel_os.domain.core import now

        timestamp = now()
        return self.repo.add(
            HumanFeedback(
                id=command.event_id,
                project_id=workflow.project_id,
                chapter_id=chapter.id,
                workflow_id=workflow.id,
                source_chapter_version_id=draft.id,
                source_draft_version=draft.version,
                source_state_version=workflow.state_version,
                source_review_id=review.id if review else None,
                raw_feedback=raw,
                reply_to_feedback_id=UUID(reply_to) if reply_to is not None else None,
                return_state=workflow.current_state,
                profile_json=profile.model_dump_json(),
                created_at=timestamp,
                authority_snapshot=self.snapshot(
                    replace(workflow, draft_version=draft.version), profile, timestamp
                ),
            )
        )

    def check(self, feedback, workflow):
        if (feedback.project_id, feedback.chapter_id, feedback.workflow_id) != (
            workflow.project_id,
            workflow.chapter_id,
            workflow.id,
        ):
            raise DomainError("AUTHORITY_DENIED", "Feedback belongs to another workflow")
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        self.core.check_record_lock(chapter)
        self.core.check_lock(workflow.project_id, ObjectRef(ObjectType.CHAPTER_VERSION, chapter.id))
        profile = ContextProfile.model_validate_json(feedback.profile_json)
        ContextProfileRegistry().resolve(
            profile.profile_id, profile.version, expected_hash=profile.profile_hash
        )
        frozen = replace(workflow, draft_version=feedback.source_draft_version)
        if self.snapshot(frozen, profile, feedback.created_at) != feedback.authority_snapshot:
            raise DomainError(
                "CONTEXT_STALE", "Feedback Draft or approved authority inputs changed"
            )
        return feedback

    def for_task(self, task, workflow):
        if not workflow.human_feedback_id or task.task_type != FEEDBACK_TASK:
            raise DomainError("CONTEXT_STALE", "Feedback task is no longer active")
        return self.check(self.repo.get(workflow.human_feedback_id), workflow)
