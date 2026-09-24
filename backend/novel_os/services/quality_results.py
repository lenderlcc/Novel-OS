"""Persist validated reviews without modifying prose, authority or human assessments."""

from dataclasses import asdict

from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.core import AuditRecord, now
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.quality import ChapterQualityReview, QualityPass, Verdict
from novel_os.quality.policy import aggregate, validate_pass
from novel_os.quality.schemas import ComplianceReview, read_review
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.services.quality_binding import QualityBindingService


class QualityResultService:
    def __init__(self, session):
        self.session = session
        self.repo = QualityRepository(session)
        self.core = CoreRepository(session)

    def validate(self, task, run, result, package, workflow):
        binding = QualityBindingService(self.session).check(task, workflow)
        if result.proposed_changes or result.memory_proposals:
            raise DomainError(
                "AUTHORITY_DENIED", "A05 reviews evidence and cannot propose mutations"
            )
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if (
            package is None
            or lineage is None
            or lineage.task_id != task.task_id
            or package.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Review requires exact Context and Prompt lineage"
            )
        if result.result.chapter_version_id != binding.chapter_version_id:
            raise DomainError("CONTEXT_STALE", "Review refers to a different Draft")
        validate_pass(result.result, package)
        return binding, lineage

    def persist(self, task, run, result, package, workflow):
        binding, lineage = self.validate(task, run, result, package, workflow)
        if result.status != ResultStatus.SUCCESS or (
            result.escalation and result.escalation.required
        ):
            return "BLOCK", {"reason": "Review requires human attention"}, TaskStatus.BLOCKED
        name = "COMPLIANCE" if task.task_type == "REVIEW_CHAPTER_COMPLIANCE" else "NARRATIVE"
        record = self.repo.add(
            QualityPass(
                binding_id=binding.id,
                pass_name=name,
                task_id=task.task_id,
                run_id=run.run_id,
                prompt_lineage_id=lineage.lineage_id,
                context_package_id=package.context_package_id,
                body=result.result.model_dump(mode="json"),
            )
        )
        self.audit(
            task,
            run,
            "Quality review pass recorded",
            {"quality_pass_id": str(record.id), "binding_id": str(binding.id), "pass_name": name},
        )
        if name == "COMPLIANCE":
            return None, {}, TaskStatus.SUCCEEDED
        first = self.repo.pass_for(binding.id, "COMPLIANCE")
        if first is None:
            raise DomainError("INVALID_STATE", "Narrative review requires its compliance pass")
        reviewed = aggregate(
            ComplianceReview.model_validate(first.body), result.result, first, record, now()
        )
        combined = self.repo.add(
            ChapterQualityReview(
                binding_id=binding.id,
                project_id=task.project_id,
                chapter_id=task.target_ref,
                chapter_version_id=binding.chapter_version_id,
                version=self.repo.next_version(task.target_ref),
                compliance_pass_id=first.id,
                narrative_pass_id=record.id,
                body=reviewed.model_dump(mode="json"),
            )
        )
        self.audit(
            task,
            run,
            "Chapter quality review aggregated",
            {
                "review_id": str(combined.id),
                "chapter_version_id": str(binding.chapter_version_id),
                "overall_verdict": reviewed.overall_verdict,
            },
        )
        return (
            "REVIEW_FAILED" if reviewed.overall_verdict == Verdict.FAIL else "REVIEW_PASSED",
            {"review_id": str(combined.id)},
            TaskStatus.SUCCEEDED,
        )

    def audit(self, task, run, reason, after):
        chapter = self.core.get_chapter(task.project_id, task.target_ref)
        self.core.add(
            AuditRecord(
                project_id=task.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=chapter.id,
                target_version=chapter.version,
                action=AuditAction.CREATE,
                actor_type=ActorType.AGENT,
                actor_id=task.agent_id.value,
                request_id=str(run.run_id),
                reason=reason,
                after=after,
            )
        )

    def check_persisted(self, workflow, review_id, run_id, event):
        from uuid import UUID

        record = self.repo.get(UUID(review_id))
        binding = self.repo.binding(workflow.id, workflow.state_version)
        if record is None or binding is None or record.binding_id != binding.id:
            raise DomainError("AUTHORITY_DENIED", "Review event has no exact persisted review")
        final_pass = self.repo.pass_for(binding.id, "NARRATIVE")
        if final_pass is None or final_pass.run_id != run_id:
            raise DomainError("AUTHORITY_DENIED", "Review event must come from its recorded run")
        reviewed = read_review(record.body)
        expected = "REVIEW_FAILED" if reviewed.overall_verdict == Verdict.FAIL else "REVIEW_PASSED"
        if event != expected:
            raise DomainError("AUTHORITY_DENIED", "Review event contradicts persisted verdict")

    def history(self, project_id, chapter_id, limit=100, offset=0):
        self.core.get_chapter(project_id, chapter_id)
        result = []
        for review in self.repo.history(project_id, chapter_id, limit, offset):
            binding = self.repo.binding_by_id(review.binding_id)
            from dataclasses import replace

            from novel_os.repositories.agent_tasks import AgentTaskRepository
            from novel_os.repositories.workflows import WorkflowRepository

            workflow = WorkflowRepository(self.session).get(binding.workflow_id)
            first = self.repo.pass_for(binding.id, "COMPLIANCE")
            task = AgentTaskRepository(self.session).get(first.task_id)
            try:
                QualityBindingService(self.session).check(
                    task,
                    replace(
                        workflow,
                        state_version=binding.state_version,
                        plan_version=binding.plan_version,
                        draft_version=binding.draft_version,
                    ),
                )
                stale = False
            except DomainError:
                stale = True
            result.append(
                {
                    **asdict(review),
                    "binding": asdict(binding),
                    "freshness": "STALE" if stale else "CURRENT",
                }
            )
        return result
