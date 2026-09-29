"""A02 interpretation persistence within the existing result transaction."""

from dataclasses import asdict

from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.domain.feedback import HumanFeedbackInterpretation
from novel_os.feedback.policy import validate_interpretation
from novel_os.repositories.feedback import FeedbackRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.feedback_binding import FeedbackBindingService
from novel_os.services.quality_results import QualityResultService


class FeedbackResultService:
    def __init__(self, session):
        self.session = session
        self.repo = FeedbackRepository(session)

    def validate(self, task, run, result, package, workflow):
        feedback = FeedbackBindingService(self.session).for_task(task, workflow)
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if (
            package is None
            or lineage is None
            or package.task_id != task.task_id
            or lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            raise DomainError(
                "AUTHORITY_DENIED", "Feedback requires exact Context and Prompt lineage"
            )
        review = (
            QualityRepository(self.session).get(feedback.source_review_id)
            if feedback.source_review_id
            else None
        )
        validate_interpretation(result.result, feedback, package, review)
        return feedback, lineage

    def persist(self, task, run, result, package, workflow):
        feedback, lineage = self.validate(task, run, result, package, workflow)
        if (
            result.status != ResultStatus.SUCCESS
            or min(result.confidence, result.result.confidence) < 0.6
            or (result.escalation and result.escalation.required)
        ):
            return (
                "BLOCK",
                {"reason": "Feedback interpretation requires attention"},
                TaskStatus.BLOCKED,
            )
        record = self.repo.add(
            HumanFeedbackInterpretation(
                feedback_id=feedback.id,
                task_id=task.task_id,
                run_id=run.run_id,
                prompt_lineage_id=lineage.lineage_id,
                context_package_id=package.context_package_id,
                body=result.result.model_dump(mode="json"),
            )
        )
        QualityResultService(self.session).audit(
            task,
            run,
            "Human feedback interpreted",
            {
                "feedback_id": str(feedback.id),
                "interpretation_id": str(record.id),
                "action": result.result.action,
            },
        )
        return "FEEDBACK_READY", {"interpretation_id": str(record.id)}, TaskStatus.SUCCEEDED

    def history(self, workflow_id, limit=100, offset=0):
        WorkflowRepository(self.session).get(workflow_id)
        return [
            {
                "feedback": asdict(feedback),
                "interpretation": asdict(interpretation) if interpretation else None,
            }
            for feedback, interpretation in self.repo.history(workflow_id, limit, offset)
        ]
