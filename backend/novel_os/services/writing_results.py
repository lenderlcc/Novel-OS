"""Application-owned Draft production and deterministic checks, without literary review."""

from dataclasses import asdict

from novel_os.agents.writing_schemas import WritingMetadata
from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.core import AuditRecord, CommandContext
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.writing import DraftCheckStatus, WritingGeneration
from novel_os.prompts.contracts import digest
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.repositories.writing import WritingRepository
from novel_os.services.core_base import CoreService
from novel_os.services.versioning import ChapterVersionService
from novel_os.services.writing_binding import WritingBindingService


def check_output(result, plan):
    """Inspect explicit structured evidence, not a writer-provided quality verdict."""
    output = result.result
    codes = set()
    if result.status != ResultStatus.SUCCESS or min(result.confidence, output.confidence) < 0.6:
        codes.add("WRITING_NEEDS_HUMAN")
    if result.escalation and result.escalation.required:
        codes.add("WRITING_NEEDS_HUMAN")
    major_types = {
        "REQUIRED_OUTCOME",
        "ENDING_DIRECTION",
        "MAJOR_DIRECTION",
        "LOCKED_DECISION",
        "CORE_CHARACTER",
        "WORLD_RULE",
        "FUTURE_STRUCTURE",
        "FORBIDDEN_CONSTRAINT",
    }
    for deviation in output.plan_deviations:
        if (
            deviation.severity == "MAJOR"
            or deviation.requires_replan
            or deviation.type in major_types
        ):
            codes.add("MAJOR_PLAN_DEVIATION")
        if deviation.type == "FORBIDDEN_CONSTRAINT":
            codes.add("FORBIDDEN_CONSTRAINT")
    if any(p.importance == "MAJOR" for p in output.proposed_new_facts) or any(
        e.scope == "MAJOR" for e in output.introduced_elements
    ):
        codes.add("MAJOR_NEW_FACT")
    if any(r.confirmed_leak for r in output.knowledge_risk_flags):
        codes.add("CHARACTER_KNOWLEDGE_LEAK")
    expected = {scene["id"]: scene["purpose"] for scene in plan.body["scenes"]}
    observed = {scene.scene_id for scene in output.scene_execution}
    if set(expected) != observed or any(
        not scene.function_completed or scene.planned_function != expected.get(scene.scene_id)
        for scene in output.scene_execution
    ):
        codes.add("SCENE_FUNCTION_INCOMPLETE")
    return sorted(codes)


class WritingResultService:
    def __init__(self, session):
        self.session = session
        self.repo = WritingRepository(session)
        self.core = CoreService(session)

    def validate(self, task, run, result, package, workflow):
        binding, _, generation = WritingBindingService(self.session).check(task, workflow)
        output = result.result
        if (output.chapter_id, output.plan_id, output.plan_version) != (
            binding.chapter_id,
            binding.plan_id,
            binding.plan_version,
        ):
            raise DomainError("CONTEXT_STALE", "Writer returned a different Plan or Chapter")
        if result.proposed_changes or result.memory_proposals:
            raise DomainError("AUTHORITY_DENIED", "Writing proposals must remain typed metadata")
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if (
            lineage is None
            or lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
            or package is None
            or package.task_id != task.task_id
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Writing requires exact Prompt and Context lineage"
            )
        return binding, generation, lineage

    def persist(self, task, run, result, package, workflow):
        binding, plan_generation, lineage = self.validate(task, run, result, package, workflow)
        output = result.result
        metadata = WritingMetadata.model_validate(
            output.model_dump(exclude={"content"})
        ).model_dump(mode="json")
        codes = check_output(result, plan_generation)
        context = CommandContext(str(run.run_id), task.agent_id.value, ActorType.AGENT)
        version = None
        if not codes:
            version = ChapterVersionService(self.session).create_version_in_transaction(
                task.project_id,
                task.target_ref,
                {
                    "content": output.content,
                    "change_reason": "Writing from approved Plan v" + str(binding.plan_version),
                },
                binding.expected_draft_version,
                context,
                "Writing created an immutable Draft",
            )
        record = self.repo.add(
            WritingGeneration(
                project_id=task.project_id,
                chapter_id=task.target_ref,
                workflow_id=workflow.id,
                agent_task_id=task.task_id,
                agent_run_id=run.run_id,
                prompt_lineage_id=lineage.lineage_id,
                context_package_id=package.context_package_id,
                plan_id=binding.plan_id,
                plan_version=binding.plan_version,
                brief_id=plan_generation.brief_id,
                chapter_version_id=version.id if version else None,
                model_profile=lineage.model_profile_id,
                provider=lineage.model_profile["provider"],
                model=lineage.model_profile["model"],
                content_hash=digest(output.content),
                metadata=metadata,
                check_status=DraftCheckStatus.BLOCKED if codes else DraftCheckStatus.PASS,
                check_codes=codes,
            )
        )
        chapter = self.core.repo.get_chapter(task.project_id, task.target_ref)
        self.core.repo.add(
            AuditRecord(
                project_id=task.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=task.target_ref,
                target_version=chapter.version,
                action=AuditAction.VERSION_CREATE,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason="Writing result and deterministic check recorded",
                after={
                    "generation_id": str(record.id),
                    "check_status": record.check_status,
                    "check_codes": codes,
                    "agent_task_id": str(task.task_id),
                    "agent_run_id": str(run.run_id),
                    "chapter_version_id": str(version.id) if version else None,
                },
            )
        )
        if codes:
            return (
                "BLOCK",
                {"reason": "Writing requires attention: " + ", ".join(codes)},
                TaskStatus.BLOCKED,
            )
        return "DRAFT_READY", {"generation_id": str(record.id)}, TaskStatus.SUCCEEDED

    def check_persisted(self, workflow, generation_id, run_id):
        """Recheck the actual persisted relation before WorkflowRuntime can enter C08."""
        from uuid import UUID

        record = self.repo.generation(UUID(generation_id))
        if (
            record.workflow_id,
            record.project_id,
            record.chapter_id,
            record.plan_version,
            record.agent_run_id,
            record.check_status,
        ) != (
            workflow.id,
            workflow.project_id,
            workflow.chapter_id,
            workflow.plan_version,
            run_id,
            DraftCheckStatus.PASS,
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Draft completion has no exact successful generation"
            )
        chapter, plan = WritingBindingService(self.session).approved_plan(workflow)
        version = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION,
            workflow.project_id,
            workflow.chapter_id,
            chapter.current_version,
        )
        if (
            record.plan_id != plan.id
            or version.id != record.chapter_version_id
            or not version.content.strip()
            or digest(version.content) != record.content_hash
        ):
            raise DomainError("VERSION_CONFLICT", "Generated Draft relation or body changed")
        WritingMetadata.model_validate(record.metadata)
        return version

    def history(self, workflow_id, limit=100, offset=0):
        from novel_os.repositories.workflows import WorkflowRepository

        WorkflowRepository(self.session).get(workflow_id)
        return [asdict(record) for record in self.repo.history(workflow_id, limit, offset)]
