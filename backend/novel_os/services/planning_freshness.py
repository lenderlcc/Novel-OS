"""Validate derived planning evidence across stages, without reusing an execution lease."""

from novel_os.context.engine import FreshnessValidator
from novel_os.context.profiles import (
    ContextConfigurationError,
    ContextProfile,
    ContextProfileRegistry,
)
from novel_os.domain.context import ContextStatus, SourceType
from novel_os.domain.errors import DomainError
from novel_os.domain.planning import BriefStatus
from novel_os.domain.workflow import ChapterState, GuardFailure
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.planning import PlanningRepository
from novel_os.services.memory_query import MemoryQueryService


class PlanningContextStale(DomainError):
    def __init__(self, message, recovery_state):
        super().__init__("CONTEXT_STALE", message)
        self.failure = GuardFailure(self.code, message, "writable", recovery_state)


class PlanningFreshness:
    def __init__(self, session):
        self.session = session
        self.repo = PlanningRepository(session)

    def evidence_is_fresh(self, artifact, *, brief=False):
        package = ContextPackageRepository(self.session).get(artifact.context_package_id)
        tasks = AgentTaskRepository(self.session)
        task = tasks.get(package.task_id)
        try:
            current = ContextProfileRegistry().resolve(
                package.profile_id, package.profile_version, expected_hash=package.profile_hash
            )
        except ContextConfigurationError:
            return False
        profile = ContextProfile.model_validate_json(package.profile_json)
        batch = MemoryQueryService(self.session).query(
            package.request, profile, tasks.clock(), task.created_at
        )
        snapshots = batch.snapshots
        if brief:
            # Creating/approving a Plan increments Chapter's version and pointers. Those
            # are outputs of this Brief, not changes to its input title/sequence/authority.
            def chapter_input(items):
                return [
                    (i.logical_id, i.structured_payload, i.status, i.authority_level, i.locked)
                    for i in items
                    if i.source_type == SourceType.CHAPTER
                ]

            if chapter_input(package.items) != chapter_input(batch.items):
                return False
            chapter_selectors = {
                s.selector_id for s in profile.selectors if s.source_type == SourceType.CHAPTER
            }
            original = {s.selector_id: s for s in package.source_snapshots}
            snapshots = tuple(
                original[s.selector_id] if s.selector_id in chapter_selectors else s
                for s in snapshots
            )
        # Artifact validity outlives its run's workflow state. Replay all source selectors
        # (including empty sets to detect additions) using the immutable original request.
        result = FreshnessValidator().validate(
            package,
            source_snapshots=snapshots,
            workflow_state_version=package.request.workflow_state_version,
            profile_hash=current.profile_hash,
        )
        return result.status == ContextStatus.READY

    def current_brief(self, workflow):
        brief = self.repo.brief(workflow.id)
        if (
            brief is None
            or brief.status != BriefStatus.READY
            or brief.input_event_id != self.repo.input_event(workflow.id).event_id
            or not self.evidence_is_fresh(brief, brief=True)
        ):
            raise PlanningContextStale(
                "CreativeBrief inputs changed; interpret the requirement again",
                ChapterState.C01_REQUIREMENT_INTAKE,
            )
        return brief

    def check_task(self, workflow):
        self.current_brief(workflow)
        chapter = CoreRepository(self.session).get_chapter(workflow.project_id, workflow.chapter_id)
        if chapter.current_plan_version != workflow.plan_version:
            raise PlanningContextStale(
                "The workflow Plan is no longer current; replan against the current version",
                ChapterState.C04_CHAPTER_PLANNING,
            )
        if workflow.current_state == ChapterState.C05_PLAN_REVIEW:
            from novel_os.services.planning_context import planning_refs

            # Resolve against the bound generation, never substitute a new locked version.
            _, missing = planning_refs(self.session, "REVIEW_CHAPTER_PLAN", workflow)
            if missing:
                raise PlanningContextStale(
                    "The Plan's exact dependencies changed; replan with current context",
                    ChapterState.C04_CHAPTER_PLANNING,
                )

    def check_review(self, report):
        if not self.evidence_is_fresh(report):
            raise PlanningContextStale(
                "PlanReview sources changed; create and review a new Plan",
                ChapterState.C04_CHAPTER_PLANNING,
            )

    def recovery_failure(self, workflow):
        if workflow.current_state not in {
            ChapterState.C04_CHAPTER_PLANNING,
            ChapterState.C05_PLAN_REVIEW,
        }:
            return None
        try:
            self.check_task(workflow)
        except PlanningContextStale as exc:
            return exc.failure
        return None
