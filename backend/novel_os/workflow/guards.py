"""Guards resolve actual domain records under the application's project lock."""

from novel_os.domain.core import ObjectRef
from novel_os.domain.enums import ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState, GuardFailure, WorkflowInstance
from novel_os.services.core_base import CoreService
from novel_os.services.versioning import PlanningService


class GuardRegistry:
    def __init__(self, core: CoreService):
        self.core = core
        self.checks = {
            "writable": self.writable,
            "plan_current": lambda w: self.artifact(w, plan=True, approved=False),
            "plan_approved": lambda w: self.artifact(w, plan=True, approved=True),
            "draft_current": lambda w: self.draft(w, approved=False),
            "draft_approved": lambda w: self.draft(w, approved=True),
        }

    def check(self, name: str, instance: WorkflowInstance) -> GuardFailure | None:
        if name not in self.checks:
            raise DomainError("INVALID_DEFINITION", "Unknown workflow guard")
        try:
            return self.checks[name](instance)
        except DomainError as exc:
            return GuardFailure(exc.code, exc.message, name)

    def writable(self, instance: WorkflowInstance) -> None:
        self.core.require_transaction(instance.project_id)
        chapter = self.core.repo.get_chapter(instance.project_id, instance.chapter_id)
        if chapter.status in {Status.ARCHIVED, Status.CANCELLED, Status.DEPRECATED}:
            raise DomainError("INVALID_STATE", "Chapter is not writable")
        self.core.check_record_lock(chapter)

    def draft(self, instance: WorkflowInstance, *, approved: bool):
        # A current/approved body is usable only while its bound plan remains approved.
        failure = self.check("plan_approved", instance)
        if failure:
            return failure
        return self.artifact(instance, plan=False, approved=approved)

    def artifact(self, instance: WorkflowInstance, *, plan: bool, approved: bool):
        chapter = self.core.repo.get_chapter(instance.project_id, instance.chapter_id)
        bound = instance.plan_version if plan else instance.draft_version
        current = chapter.current_plan_version if plan else chapter.current_version
        approved_version = chapter.approved_plan_version if plan else chapter.approved_version
        kind = ObjectType.CHAPTER_PLAN if plan else ObjectType.CHAPTER_VERSION
        name = ("plan" if plan else "draft") + ("_approved" if approved else "_current")
        recovery = (
            ChapterState.C04_CHAPTER_PLANNING if plan else ChapterState.C08_DETERMINISTIC_CHECK
        )
        if bound is None or current != bound:
            return GuardFailure(
                "VERSION_CONFLICT", "The workflow artifact is no longer current", name, recovery
            )
        record = self.core.repo.get_version(kind, instance.project_id, instance.chapter_id, bound)
        if approved and (
            approved_version != bound
            or record.approved_at is None
            or record.status not in {Status.APPROVED, Status.LOCKED}
        ):
            return GuardFailure("APPROVAL_REQUIRED", "The bound artifact needs user approval", name)
        # A locked approved plan can be read to write a draft; it cannot be replaced.
        if plan:
            PlanningService(self.core.session).validate(
                instance.project_id,
                {field: getattr(record, field) for field in PlanningService.allowed},
                record,
            )
        if not approved:
            self.core.check_lock(instance.project_id, ObjectRef(kind, instance.chapter_id))
        return None
