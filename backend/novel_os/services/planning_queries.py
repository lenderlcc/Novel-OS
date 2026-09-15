from dataclasses import asdict

from novel_os.domain.enums import ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.planning import CreativeBrief, PlanGeneration, PlanReviewReport
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.workflows import WorkflowRepository


class PlanningQueries:
    def __init__(self, session):
        self.repo = PlanningRepository(session)
        self.workflows = WorkflowRepository(session)
        self.core = CoreRepository(session)

    def workflow(self, workflow_id):
        workflow = self.workflows.get(workflow_id)
        if workflow.simulation:
            raise DomainError("INVALID_STATE", "Planning evidence requires a business workflow")
        return workflow

    def brief(self, workflow_id, version=None):
        self.workflow(workflow_id)
        result = self.repo.brief(workflow_id, version)
        if result is None:
            raise DomainError("NOT_FOUND", "CreativeBrief is not available")
        return asdict(result)

    def plan(self, workflow_id, version=None):
        workflow = self.workflow(workflow_id)
        version = workflow.plan_version if version is None else version
        if version is None:
            raise DomainError("NOT_FOUND", "Workflow has no Plan")
        plan = self.core.get_version(
            ObjectType.CHAPTER_PLAN, workflow.project_id, workflow.chapter_id, version
        )
        generation = self.repo.generation(workflow_id, plan.id)
        if generation is None:
            raise DomainError("NOT_FOUND", "Plan does not belong to this workflow")
        return {
            "plan": {**asdict(plan), "object_type": plan.object_type},
            "generation": asdict(generation),
        }

    def review(self, workflow_id, version=None):
        plan = self.plan(workflow_id, version)
        report = self.repo.review(workflow_id, plan["plan"]["id"])
        if report is None:
            raise DomainError("NOT_FOUND", "Plan review is not available")
        return asdict(report)

    def history(self, workflow_id, limit=100, offset=0):
        self.workflow(workflow_id)
        return {
            name: [asdict(item) for item in self.repo.history(kind, workflow_id, limit, offset)]
            for name, kind in (
                ("briefs", CreativeBrief),
                ("plans", PlanGeneration),
                ("reviews", PlanReviewReport),
            )
        }

    def metrics(self, workflow_id):
        workflow = self.workflow(workflow_id)
        return self.repo.metrics(workflow)
