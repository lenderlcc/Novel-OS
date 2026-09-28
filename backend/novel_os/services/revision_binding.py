"""Pin the review's proven authority snapshot and reject changed inputs before work."""

from dataclasses import replace

from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.domain.core import ObjectRef, VersionToken
from novel_os.domain.enums import ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.revision import RevisionRequest
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.revision.policy import contract_for
from novel_os.services.core_base import CoreService, validate_payload
from novel_os.services.quality_binding import QualityBindingService, supports_quality


class RevisionBindingService:
    def __init__(self, session):
        self.session = session
        self.repo = RevisionRepository(session)
        self.quality = QualityRepository(session)
        self.core = CoreService(session)

    def check_source(self, request, workflow):
        if (request.project_id, request.chapter_id, request.workflow_id) != (
            workflow.project_id,
            workflow.chapter_id,
            workflow.id,
        ):
            raise DomainError("AUTHORITY_DENIED", "Revision belongs to another workflow")
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        self.core.check_record_lock(chapter)
        self.core.check_lock(workflow.project_id, ObjectRef(ObjectType.CHAPTER_VERSION, chapter.id))
        latest = self.quality.history(workflow.project_id, chapter.id, 1)
        binding = self.quality.binding_by_id(request.source_binding_id)
        if not all((binding.profile_record_id, binding.profile_version, binding.profile_hash)):
            raise DomainError(
                "CONTEXT_MISSING",
                "Revision requires an approved Writing Profile in its source Review; "
                "approve a Profile and re-review first",
            )
        latest_binding = self.quality.latest_binding(workflow.id)
        if (
            not latest
            or latest[0].id != request.source_review_id
            or latest_binding is None
            or latest_binding.id != binding.id
        ):
            raise DomainError("CONTEXT_STALE", "Source Review has been replaced")
        first = self.quality.pass_for(binding.id, "COMPLIANCE")
        task = AgentTaskRepository(self.session).get(first.task_id)
        QualityBindingService(self.session).check(
            task,
            replace(
                workflow,
                state_version=binding.state_version,
                draft_version=binding.draft_version,
                plan_version=binding.plan_version,
            ),
        )
        profile = ContextProfile.model_validate_json(request.profile_json)
        ContextProfileRegistry().resolve(
            profile.profile_id, profile.version, expected_hash=profile.profile_hash
        )
        return request

    def prepare(self, workflow, command, context):
        context.require_user()
        validate_payload(command.payload, {"source_review_id", "expected_draft_version", "reason"})
        if (
            not supports_quality(workflow)
            or workflow.status != WorkflowStatus.WAITING_HUMAN
            or workflow.current_state
            not in {ChapterState.C10_REVISION, ChapterState.C11_INTERNAL_PASS}
            or workflow.revision_request_id is not None
        ):
            raise DomainError(
                "INVALID_STATE", "Revision requires a completed Review and explicit user trigger"
            )
        from uuid import UUID

        review = self.quality.get(UUID(command.payload["source_review_id"]))
        if review is None or (review.project_id, review.chapter_id) != (
            workflow.project_id,
            workflow.chapter_id,
        ):
            raise DomainError("VERSION_CONFLICT", "Source Review does not belong to this Draft")
        if review.body["overall_verdict"] == "PASS":
            raise DomainError("INVALID_STATE", "A passing Review has no revision targets")
        binding = self.quality.binding_by_id(review.binding_id)
        VersionToken(command.payload["expected_draft_version"]).check(binding.draft_version)
        if binding.workflow_id != workflow.id or workflow.draft_version != binding.draft_version:
            raise DomainError("CONTEXT_STALE", "Review workflow or Draft mismatch")
        final = self.quality.pass_for(binding.id, "NARRATIVE")
        package = ContextPackageRepository(self.session).get(final.context_package_id)
        request = RevisionRequest(
            id=command.event_id,
            project_id=workflow.project_id,
            chapter_id=workflow.chapter_id,
            workflow_id=workflow.id,
            source_chapter_version_id=review.chapter_version_id,
            source_review_id=review.id,
            source_binding_id=binding.id,
            source_context_package_id=package.context_package_id,
            profile_json=ContextProfileRegistry()
            .for_task("PLAN_CHAPTER_REVISION")
            .model_dump_json(),
            contract=contract_for(review, package),
        )
        self.check_source(request, workflow)
        return self.repo.add(request)

    def check(self, task, workflow):
        if workflow.revision_request_id is None:
            raise DomainError("CONTEXT_STALE", "Revision is no longer active")
        request = self.repo.get(workflow.revision_request_id)
        if task.workflow_instance_id != workflow.id or task.target_ref != request.chapter_id:
            raise DomainError("AUTHORITY_DENIED", "Revision task scope mismatch")
        return self.check_source(request, workflow)
