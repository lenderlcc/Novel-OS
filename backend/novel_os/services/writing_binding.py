"""Freeze Writing inputs at scheduling; recheck them before every external call and write."""

from dataclasses import asdict

from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.domain.core import ObjectRef
from novel_os.domain.enums import ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.writing import WritingTaskBinding
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.writing import WritingRepository
from novel_os.services.core_base import CoreService
from novel_os.services.memory_query import MemoryQueryService


def supports_writing(workflow):
    return (
        not workflow.simulation
        and workflow.workflow_definition_id == "chapter-planning"
        and workflow.workflow_definition_version == 2
    )


class WritingBindingService:
    def __init__(self, session):
        self.session = session
        self.repo = WritingRepository(session)
        self.core = CoreService(session)

    def approved_plan(self, workflow):
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        if not supports_writing(workflow) or workflow.plan_version is None:
            raise DomainError("CONTEXT_MISSING", "Writing requires an approved Plan binding")
        plan = self.core.repo.get_version(
            ObjectType.CHAPTER_PLAN, workflow.project_id, workflow.chapter_id, workflow.plan_version
        )
        if (
            chapter.approved_plan_version != plan.version
            or plan.approved_at is None
            or plan.status not in {Status.APPROVED, Status.LOCKED}
        ):
            raise DomainError("CONTEXT_STALE", "The exact Writing Plan is no longer approved")
        return chapter, plan

    def inputs(self, task, workflow, profile):
        from novel_os.services.context import ContextService

        request = ContextService(self.session).request_for_task(task, workflow, profile)
        batch = MemoryQueryService(self.session).query(
            request, profile, AgentTaskRepository(self.session).clock(), task.created_at
        )
        return request, batch

    def capture(self, task, workflow):
        self.core.require_transaction(task.project_id)
        chapter, plan = self.approved_plan(workflow)
        profile = ContextProfileRegistry().for_task(task.task_type)
        _, batch = self.inputs(task, workflow, profile)
        return self.repo.add(
            WritingTaskBinding(
                task_id=task.task_id,
                project_id=task.project_id,
                chapter_id=task.target_ref,
                workflow_id=workflow.id,
                plan_id=plan.id,
                plan_version=plan.version,
                expected_draft_version=chapter.current_version or 0,
                profile_json=profile.model_dump_json(),
                source_snapshots=[asdict(s) for s in batch.snapshots],
            )
        )

    def check(self, task, workflow):
        self.core.require_transaction(task.project_id)
        binding = self.repo.binding(task.task_id)
        chapter, plan = self.approved_plan(workflow)
        if (
            binding.project_id,
            binding.chapter_id,
            binding.workflow_id,
            binding.plan_id,
            binding.plan_version,
            binding.expected_draft_version,
        ) != (
            task.project_id,
            task.target_ref,
            workflow.id,
            plan.id,
            plan.version,
            chapter.current_version or 0,
        ):
            raise DomainError("CONTEXT_STALE", "Writing input or target version changed")
        self.core.check_record_lock(chapter)
        self.core.check_lock(
            task.project_id, ObjectRef(ObjectType.CHAPTER_VERSION, task.target_ref)
        )
        from novel_os.services.planning_freshness import PlanningFreshness

        brief = PlanningFreshness(self.session).current_brief(workflow)
        generation = PlanningRepository(self.session).generation(workflow.id, plan.id)
        if generation is None or generation.brief_id != brief.id:
            raise DomainError("CONTEXT_STALE", "Writing Plan has no matching current Brief")
        profile = ContextProfile.model_validate_json(binding.profile_json)
        ContextProfileRegistry().resolve(
            profile.profile_id, profile.version, expected_hash=profile.profile_hash
        )
        request, batch = self.inputs(task, workflow, profile)
        if (
            request.missing_bindings
            or [asdict(s) for s in batch.snapshots] != binding.source_snapshots
        ):
            raise DomainError("CONTEXT_STALE", "Approved Writing inputs changed after scheduling")
        return binding, plan, generation

    def recovery_failure(self, workflow):
        from novel_os.domain.workflow import ChapterState, GuardFailure
        from novel_os.services.planning_freshness import PlanningContextStale, PlanningFreshness

        if not supports_writing(workflow) or workflow.current_state not in {
            ChapterState.C07_WRITING,
            ChapterState.C08_DETERMINISTIC_CHECK,
        }:
            return None
        try:
            PlanningFreshness(self.session).current_brief(workflow)
        except PlanningContextStale as exc:
            return exc.failure
        try:
            self.approved_plan(workflow)
            if workflow.current_state == ChapterState.C08_DETERMINISTIC_CHECK:
                # The completed run's snapshot predates its own Draft. Replaying that
                # pending-write version check would invalidate every successful C08.
                return None
            binding = self.repo.latest_binding(workflow.id)
            if binding is None:
                return None
            task = AgentTaskRepository(self.session).get(binding.task_id)
            self.check(task, workflow)
            return None
        except DomainError as exc:
            if exc.code == "LOCKED_OBJECT":
                return None  # Resume remains guarded until the user releases the write lock.
        return GuardFailure(
            "CONTEXT_STALE",
            "Writing Plan or its exact dependencies require replanning",
            "writable",
            ChapterState.C04_CHAPTER_PLANNING,
        )
