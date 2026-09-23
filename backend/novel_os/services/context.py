"""Context application boundary: root lock, exact run binding, immutable snapshot and audit."""

from novel_os.context.engine import ContextEngine, FreshnessValidator
from novel_os.context.profiles import (
    ContextConfigurationError,
    ContextProfile,
    ContextProfileRegistry,
)
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.agents import RunStatus, TaskStatus
from novel_os.domain.context import (
    ContextBuildResult,
    ContextRequest,
    ContextStatus,
    SourceRef,
    SourceType,
)
from novel_os.domain.core import AuditRecord
from novel_os.domain.enums import ActorType, AuditAction, ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.context_sources import ContextSourceRepository
from novel_os.repositories.core import CoreRepository
from novel_os.services.agent_results import AgentResultHandler, valid_lease
from novel_os.services.memory_query import MemoryQueryService
from novel_os.services.task_scheduling import expects_task

CONTEXT_BLOCK_ERRORS = frozenset(
    {
        "CONTEXT_MISSING",
        "CONTEXT_BUDGET_EXCEEDED",
        "CONTEXT_AUTHORITY_CONFLICT",
        "CONTEXT_RETRIEVAL_LIMIT",
        "CONTEXT_STALE",
        "CONTEXT_PROFILE_MISMATCH",
        "CONTEXT_CONFIGURATION_ERROR",
    }
)


class ContextService:
    def __init__(self, session, *, registry=None, extensions=None, estimator=None):
        self.session = session
        self.repo = ContextPackageRepository(session)
        self.tasks = AgentTaskRepository(session)
        self.core = CoreRepository(session)
        self.sources = ContextSourceRepository(session)
        self.registry = registry or ContextProfileRegistry()
        self.query = MemoryQueryService(session, extensions=extensions)
        self.engine = ContextEngine(estimator)

    def _locked_run(self, lease):
        task, workflow = AgentResultHandler(self.session).lock_task(lease.task_id)
        run = self.tasks.run(lease.run_id)
        if (
            task.status != TaskStatus.RUNNING
            or run.status != RunStatus.RUNNING
            or run.task_id != task.task_id
            or run.lease_token != lease.token
            or run.worker_id != lease.worker_id
            or not valid_lease(task, lease, self.tasks.clock())
        ):
            raise DomainError("LEASE_LOST", "Context execution lease is no longer valid")
        return task, workflow, run

    def task_profile(self, task):
        if task.task_type == "WRITE_CHAPTER":
            from novel_os.repositories.writing import WritingRepository

            return ContextProfile.model_validate_json(
                WritingRepository(self.session).binding(task.task_id).profile_json
            )
        return self.registry.for_task(task.task_type)

    def check_writing(self, task, workflow):
        from novel_os.services.writing_profile_context import WritingProfileContext

        WritingProfileContext(self.session).check_scheduled(task)
        if task.task_type == "WRITE_CHAPTER":
            from novel_os.services.writing_binding import WritingBindingService

            WritingBindingService(self.session).check(task, workflow)

    def request_for_task(self, task, workflow, profile=None):
        profile = profile or self.registry.for_task(task.task_type)
        chapter = self.sources.chapter(task.project_id, task.target_ref)
        # Required plan and its dependency list use the same workflow-bound version.
        needs_plan = any(
            s.source_type == SourceType.CHAPTER_PLAN and s.required for s in profile.selectors
        )
        plan_version = workflow.plan_version if needs_plan else None
        refs, missing = [], []
        if needs_plan and plan_version is None:
            missing.append("workflow.approved_plan_version")
        plan = self.sources.artifact(
            SourceType.CHAPTER_PLAN, task.project_id, chapter.id, plan_version
        )
        if (
            plan is not None
            and plan.approved_at is not None
            and plan.status in {Status.APPROVED, Status.LOCKED}
        ):
            for dependency in plan.locked_dependencies:
                kind = dependency.get("object_type")
                if kind not in {
                    SourceType.CHAPTER_PLAN.value,
                    SourceType.CHAPTER_VERSION.value,
                    SourceType.REQUIREMENT.value,
                    SourceType.DECISION.value,
                }:
                    missing.append(f"unsupported_locked_dependency:{kind}")
                    continue
                from uuid import UUID

                target = UUID(dependency["object_id"])
                lock = self.sources.lock(task.project_id, SourceType(kind), target)
                if lock:
                    refs.append(
                        SourceRef(
                            source_type=SourceType(kind),
                            logical_id=target,
                            version=lock.target_version,
                        )
                    )
                else:
                    missing.append(f"locked_dependency:{kind}:{target}")
        if task.task_type == "WRITE_CHAPTER":
            from novel_os.agents.planning_schemas import ChapterPlanOutput
            from novel_os.repositories.planning import PlanningRepository

            generation = (
                PlanningRepository(self.session).generation(workflow.id, plan.id) if plan else None
            )
            refs = []
            if generation is None:
                missing.append("writing.plan_generation")
            else:
                for dependency in ChapterPlanOutput.model_validate(
                    generation.body
                ).locked_dependencies:
                    ref = SourceRef(
                        source_type=dependency.source_type,
                        logical_id=dependency.logical_id,
                        version=dependency.version,
                    )
                    refs.append(ref)
                    lock = self.sources.lock(task.project_id, ref.source_type, ref.logical_id)
                    if lock is None or lock.target_version != ref.version:
                        missing.append("writing.exact_locked_dependency")
        refs = tuple(sorted(set(refs), key=lambda r: (r.source_type, str(r.logical_id), r.version)))
        if task.task_type in {"PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}:
            from novel_os.services.planning_context import planning_refs

            business_refs, business_missing = planning_refs(
                self.core.session, task.task_type, workflow
            )
            refs = tuple(set(refs) | set(business_refs))
            missing.extend(business_missing)
        from novel_os.services.writing_profile_context import model_requirements

        return ContextRequest(
            project_id=task.project_id,
            task_id=task.task_id,
            task_type=task.task_type,
            chapter_id=chapter.id,
            chapter_sequence=chapter.sequence,
            workflow_id=workflow.id,
            workflow_state_version=task.workflow_state_version,
            attempt_number=task.attempt_count,
            target_version=workflow.draft_version,
            approved_plan_version=plan_version,
            missing_bindings=tuple(sorted(missing)),
            objective=task.objective,
            requirements=model_requirements(task.requirements),
            constraints=tuple(task.constraints),
            explicit_refs=refs,
            required_refs=refs,
            required_future_refs=refs,
        )

    def build_for_run(self, lease, *, prompt_overhead=0, output_reservation=0):
        with self.session.begin():
            task, workflow, run = self._locked_run(lease)
            existing = self.repo.for_run(run.run_id)
            if existing:
                return self.validate_in_transaction(existing, task, workflow)
            if not expects_task(workflow, task):
                return ContextBuildResult(status=ContextStatus.STALE, error_code="CONTEXT_STALE")
            if task.task_type in {"PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}:
                from novel_os.services.planning_freshness import (
                    PlanningContextStale,
                    PlanningFreshness,
                )

                try:
                    PlanningFreshness(self.session).check_task(workflow)
                except PlanningContextStale:
                    return ContextBuildResult(
                        status=ContextStatus.STALE, error_code="CONTEXT_STALE"
                    )
            try:
                self.check_writing(task, workflow)
            except DomainError:
                return ContextBuildResult(status=ContextStatus.STALE, error_code="CONTEXT_STALE")
            profile = self.task_profile(task)
            self.repo.check_profile(profile)
            request = self.request_for_task(task, workflow, profile)
            batch = self.query.query(request, profile, self.tasks.clock(), task.created_at)
            result = self.engine.build(
                request,
                profile,
                batch,
                prompt_overhead=prompt_overhead,
                output_reservation=output_reservation,
            )
            if result.package is not None:
                package = self.repo.add(run.run_id, result.package)
                chapter = self.core.get_chapter(task.project_id, task.target_ref)
                self.core.add(
                    AuditRecord(
                        project_id=task.project_id,
                        target_type=ObjectType.CHAPTER,
                        target_id=task.target_ref,
                        target_version=chapter.version,
                        action=AuditAction.CREATE,
                        actor_type=ActorType.SYSTEM,
                        actor_id=lease.worker_id,
                        request_id=str(run.run_id),
                        reason="Context snapshot bound to execution attempt",
                        before={},
                        after={
                            "context_package_id": str(package.context_package_id),
                            "agent_task_id": str(task.task_id),
                            "agent_run_id": str(run.run_id),
                            "profile_id": package.profile_id,
                            "profile_version": package.profile_version,
                            "package_hash": package.package_hash,
                            "build_status": package.build_status,
                            "error_code": package.error_code,
                        },
                    )
                )
            return result

    def validate_in_transaction(self, package, task, workflow):
        if (
            package.project_id,
            package.task_id,
            package.workflow_id,
            package.request.chapter_id,
        ) != (
            task.project_id,
            task.task_id,
            task.workflow_instance_id,
            task.target_ref,
        ) or not expects_task(workflow, task):
            return ContextBuildResult(
                status=ContextStatus.STALE, package=package, error_code="CONTEXT_STALE"
            )
        try:
            self.check_writing(task, workflow)
        except DomainError:
            return ContextBuildResult(
                status=ContextStatus.STALE, package=package, error_code="CONTEXT_STALE"
            )
        if package.build_status != ContextStatus.READY:
            return ContextBuildResult(
                status=package.build_status,
                package=package,
                error_code=package.error_code,
                missing_required_context=package.missing_required_items,
                authority_conflicts=package.authority_conflicts,
            )
        try:
            current = self.registry.resolve(
                package.profile_id, package.profile_version, expected_hash=package.profile_hash
            )
        except ContextConfigurationError:
            return ContextBuildResult(
                status=ContextStatus.STALE, package=package, error_code="CONTEXT_STALE"
            )
        # Replay this exact profile version. Publishing v2 cannot reinterpret a v1 snapshot.
        profile = ContextProfile.model_validate_json(package.profile_json)
        batch = self.query.query(package.request, profile, self.tasks.clock(), task.created_at)
        return FreshnessValidator().validate(
            package,
            source_snapshots=batch.snapshots,
            workflow_state_version=workflow.state_version,
            profile_hash=current.profile_hash,
        )

    def validate_before_model(self, lease, package):
        with self.session.begin():
            task, workflow, _ = self._locked_run(lease)
            persisted = self.repo.for_run(lease.run_id)
            if (
                persisted is None
                or persisted.context_package_id != package.context_package_id
                or persisted.package_hash != package.package_hash
            ):
                raise DomainError("VERSION_CONFLICT", "Run context binding mismatch")
            return self.validate_in_transaction(persisted, task, workflow)

    def inspect(self, *, package_id=None, task_id=None, run_id=None):
        with self.session.begin():
            if run_id is not None:
                run = self.tasks.run(run_id)
                package = self.repo.for_run(run.run_id)
                if package is None:
                    raise DomainError("NOT_FOUND", "This run has no context snapshot")
                task_id, package_id = run.task_id, package.context_package_id
            if task_id is None:
                package = self.repo.get(package_id)
                task_id = package.task_id
            task, workflow = AgentResultHandler(self.session).lock_task(task_id)
            package = self.repo.get(package_id) if package_id else self.repo.for_task(task_id)
            if package is None:
                raise DomainError("NOT_FOUND", "This task has no context snapshot")
            result = self.validate_in_transaction(package, task, workflow)
            return {
                "package": ContextSerializer.snapshot(package),
                "freshness": result.status,
                "error_code": result.error_code,
            }
