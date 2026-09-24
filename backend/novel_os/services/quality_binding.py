"""Freeze both review passes to one authority snapshot before any model call."""

from dataclasses import asdict

from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.domain.context import SourceType
from novel_os.domain.enums import ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.quality import QualityBinding
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.services.writing_binding import WritingBindingService


def supports_quality(workflow):
    return not workflow.simulation and (
        workflow.workflow_definition_id,
        workflow.workflow_definition_version,
    ) == ("chapter-planning", 3)


class QualityBindingService(WritingBindingService):
    def __init__(self, session):
        super().__init__(session)
        self.repo = QualityRepository(session)

    def current(self, task, workflow, profile):
        chapter, plan = self.approved_plan(workflow)
        if (
            not supports_quality(workflow)
            or not workflow.draft_version
            or chapter.current_version != workflow.draft_version
        ):
            raise DomainError("CONTEXT_STALE", "Review requires the exact current Draft")
        draft = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION, task.project_id, task.target_ref, workflow.draft_version
        )
        from novel_os.services.planning_freshness import PlanningFreshness

        brief = PlanningFreshness(self.session).current_brief(workflow)
        generation = PlanningRepository(self.session).generation(workflow.id, plan.id)
        if generation is None or generation.brief_id != brief.id:
            raise DomainError("CONTEXT_STALE", "Review Plan and Brief no longer match")
        request, batch = self.inputs(task, workflow, profile)
        if request.missing_bindings:
            raise DomainError("CONTEXT_MISSING", "Review source binding is incomplete")
        preference = next(
            (i for i in batch.items if i.source_type == SourceType.PROJECT_WRITING_PROFILE), None
        )
        return dict(
            project_id=task.project_id,
            chapter_id=task.target_ref,
            workflow_id=workflow.id,
            state_version=workflow.state_version,
            chapter_version_id=draft.id,
            draft_version=draft.version,
            plan_id=plan.id,
            plan_version=plan.version,
            brief_id=brief.id,
            profile_record_id=preference.source_id if preference else None,
            profile_version=preference.source_version if preference else None,
            profile_hash=preference.structured_payload["writing_profile_hash"]
            if preference
            else None,
            profile_json=profile.model_dump_json(),
            source_snapshots=[asdict(s) for s in batch.snapshots if s.selector_id != "task-input"],
        )

    def capture(self, task, workflow):
        self.core.require_transaction(task.project_id)
        existing = self.repo.binding(workflow.id, workflow.state_version)
        if existing:
            self.check(task, workflow)
            return existing
        profile = ContextProfileRegistry().for_task(task.task_type)
        return self.repo.add(QualityBinding(**self.current(task, workflow, profile)))

    def check(self, task, workflow):
        self.core.require_transaction(task.project_id)
        binding = self.repo.binding(workflow.id, task.workflow_state_version)
        if binding is None:
            raise DomainError("CONTEXT_MISSING", "Review task has no frozen source binding")
        profile = ContextProfile.model_validate_json(binding.profile_json)
        ContextProfileRegistry().resolve(
            profile.profile_id, profile.version, expected_hash=profile.profile_hash
        )
        expected = asdict(binding)
        expected.pop("id")
        expected.pop("created_at")
        if expected != self.current(task, workflow, profile):
            raise DomainError(
                "CONTEXT_STALE", "Draft, Brief, Plan, Profile or review source changed"
            )
        return binding
