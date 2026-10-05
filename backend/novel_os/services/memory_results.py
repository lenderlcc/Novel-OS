"""A07 can append a proposal only, inside the existing result transaction."""

from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.memory import MemoryCommitProposal
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.memory_commit import MemoryCommitService
from novel_os.services.quality_results import QualityResultService


class MemoryResultService:
    def __init__(self, session):
        self.session = session
        self.service = MemoryCommitService(session)

    def validate(self, task, run, result, package, workflow):
        request = self.service.for_task(task, workflow)
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if (
            package is None
            or lineage is None
            or package.task_id != task.task_id
            or lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            raise ValueError("Memory extraction requires exact Context and Prompt lineage")
        return request, lineage, self.service.normalize(result.result, request, package)

    def persist(self, task, run, result, package, workflow):
        request, lineage, candidates = self.validate(task, run, result, package, workflow)
        if (
            result.status != ResultStatus.SUCCESS
            or result.confidence < 0.6
            or (result.escalation and result.escalation.required)
        ):
            return "BLOCK", {"reason": "Memory extraction requires attention"}, TaskStatus.BLOCKED
        proposal = self.service.repo.add(
            MemoryCommitProposal(
                request_id=request.id,
                task_id=task.task_id,
                agent_run_id=run.run_id,
                prompt_lineage_id=lineage.lineage_id,
                context_package_id=package.context_package_id,
                raw_output=result.result.model_dump(mode="json"),
                candidates=candidates,
            )
        )
        QualityResultService(self.session).audit(
            task,
            run,
            "Memory proposal extracted",
            {
                "proposal_id": str(proposal.id),
                "request_id": str(request.id),
                "chapter_version_id": str(request.chapter_version_id),
                "candidate_count": len(candidates),
            },
        )
        return "MEMORY_PROPOSAL_READY", {"proposal_id": str(proposal.id)}, TaskStatus.SUCCEEDED
