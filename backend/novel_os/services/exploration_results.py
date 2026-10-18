"""Validate and persist A03 diagnostics in the existing task completion transaction."""

from dataclasses import asdict

from novel_os.agents.planning_schemas import CreativeBriefOutput
from novel_os.domain.agents import TaskStatus
from novel_os.domain.context import SourceType
from novel_os.domain.core import AuditRecord, ObjectRef
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.domain.planning import (
    CreativeExploration,
    ExplorationStatus,
    exploration_required_refs,
)
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.core_base import CoreService
from novel_os.services.exploration_policy import should_explore, supports_exploration
from novel_os.services.planning_freshness import PlanningFreshness
from novel_os.services.planning_policy import denied, ref_key
from novel_os.services.planning_results import validate_sources


class ExplorationResultService:
    def __init__(self, session):
        self.session = session
        self.core = CoreService(session)
        self.repo = PlanningRepository(session)

    def validate(self, task, run, result, package, workflow):
        self.core.require_transaction(task.project_id)
        if not supports_exploration(workflow):
            denied("Exploration requires the versioned A03 planning contract")
        chapter = self.core.repo.get_chapter(task.project_id, task.target_ref)
        self.core.check_record_lock(chapter)
        self.core.check_lock(task.project_id, ObjectRef(ObjectType.CHAPTER_PLAN, task.target_ref))
        brief = PlanningFreshness(self.session).current_brief(workflow)
        if not should_explore(brief) or result.result.brief_id != brief.id:
            denied("Exploration must use the exact eligible CreativeBrief")
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if lineage is None or (
            lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            denied("Exploration requires its exact prompt lineage")
        output = result.result
        validate_sources(output, package)
        keys = {ref_key(ref) for ref in output.source_refs}
        if not {ref_key(ref) for ref in exploration_required_refs(package.items)} <= keys:
            if package.profile_id == "CP-004E" and package.profile_version >= 3:
                # Missing citations are an output contract failure, not a permission grant.
                # Actual lock, scope and authority checks above retain their denial path.
                raise ValueError("Exploration omitted required source references")
            denied("Exploration omitted locked or Canon evidence")
        if (SourceType.CREATIVE_BRIEF, workflow.id, brief.version) not in keys:
            denied("Exploration must cite its current Brief")
        level = CreativeBriefOutput.model_validate(brief.body).creative_freedom.level
        minimum, maximum = (3, 4) if level == "HIGH" else (2, 3)
        if output.mode == "DIVERGENT" and not minimum <= len(output.candidates) <= maximum:
            raise ValueError("Exploration candidate count does not match its granted freedom")

    def persist(self, task, run, result, package, workflow):
        self.core.require_transaction(task.project_id)
        # Completion's project lock serializes duplicate delivery; AgentRun uniqueness
        # additionally prevents parallel insertion of evidence for the same execution.
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        output = result.result
        blocked = output.selected_candidate_id is None
        artifact = self.repo.add(
            CreativeExploration(
                project_id=task.project_id,
                chapter_id=task.target_ref,
                workflow_id=workflow.id,
                agent_run_id=run.run_id,
                prompt_lineage_id=lineage.lineage_id,
                context_package_id=package.context_package_id,
                brief_id=output.brief_id,
                source_versions=[
                    asdict(item.ref)
                    | {"logical_id": str(item.logical_id), "source_id": str(item.source_id)}
                    for item in package.items
                ],
                body=output.model_dump(mode="json"),
                status=ExplorationStatus.BLOCKED if blocked else ExplorationStatus.READY,
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
                actor_type=ActorType.AGENT,
                actor_id=task.agent_id.value,
                request_id=str(run.run_id),
                reason="Persist bounded CreativeExploration inference",
                after={
                    "artifact_id": str(artifact.id),
                    "selected_candidate_id": output.selected_candidate_id,
                },
            )
        )
        return (
            (
                "BLOCK",
                {"reason": "No safe creative concept; clarify the chapter requirement"},
                TaskStatus.BLOCKED,
            )
            if blocked
            else (None, {}, TaskStatus.SUCCEEDED)
        )
