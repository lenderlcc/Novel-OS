"""Flush-only persistence of immutable business evidence and bounded history queries."""

from dataclasses import asdict

from sqlalchemy import select

from novel_os.domain import planning as domain
from novel_os.domain.errors import DomainError
from novel_os.models import planning as orm
from novel_os.models.workflow import WorkflowEventModel
from novel_os.repositories.core import to_domain

MAPPINGS = {
    domain.CreativeBrief: orm.CreativeBriefModel,
    domain.PlanGeneration: orm.PlanGenerationModel,
    domain.PlanReviewReport: orm.PlanReviewReportModel,
}


class PlanningRepository:
    def __init__(self, session):
        self.session = session

    def add(self, entity):
        self.session.add(MAPPINGS[type(entity)](**asdict(entity)))
        self.session.flush()
        return entity

    def metrics(self, workflow):
        from collections import Counter

        from sqlalchemy import func

        from novel_os.models.agents import AgentRunModel, AgentTaskModel
        from novel_os.models.workflow import HumanGateModel

        briefs = list(
            self.session.scalars(
                select(orm.CreativeBriefModel.body).where(
                    orm.CreativeBriefModel.workflow_id == workflow.id
                )
            )
        )
        reports = list(
            self.session.scalars(
                select(orm.PlanReviewReportModel)
                .where(orm.PlanReviewReportModel.workflow_id == workflow.id)
                .order_by(orm.PlanReviewReportModel.created_at)
            )
        )
        gates = list(
            self.session.scalars(
                select(HumanGateModel)
                .where(HumanGateModel.workflow_id == workflow.id)
                .order_by(HumanGateModel.opened_state_version)
            )
        )
        decisions = [gate for gate in gates if gate.decision is not None]
        needs = sum(
            any(
                a["impact"] == "HIGH" and a["confidence"] < 0.6 and not a["can_safely_infer"]
                for a in body["unresolved_ambiguities"]
            )
            for body in briefs
        )
        retries = self.session.scalar(
            select(func.count())
            .select_from(AgentRunModel)
            .join(AgentTaskModel, AgentRunModel.task_id == AgentTaskModel.task_id)
            .where(
                AgentTaskModel.workflow_instance_id == workflow.id, AgentRunModel.attempt_number > 1
            )
        )
        corrections = self.session.scalar(
            select(func.count())
            .select_from(WorkflowEventModel)
            .where(
                WorkflowEventModel.workflow_id == workflow.id,
                WorkflowEventModel.event_type == "CORRECT_REQUIREMENT",
            )
        )
        successful_intakes = self.session.scalar(
            select(func.count())
            .select_from(AgentTaskModel)
            .where(
                AgentTaskModel.workflow_instance_id == workflow.id,
                AgentTaskModel.task_type == "PARSE_CHAPTER_REQUIREMENT",
                AgentTaskModel.status == "SUCCEEDED",
            )
        )
        total_intakes = self.session.scalar(
            select(func.count())
            .select_from(AgentTaskModel)
            .where(
                AgentTaskModel.workflow_instance_id == workflow.id,
                AgentTaskModel.task_type == "PARSE_CHAPTER_REQUIREMENT",
                AgentTaskModel.status.in_(["SUCCEEDED", "FAILED", "BLOCKED"]),
            )
        )
        return {
            "workflow_id": str(workflow.id),
            "requirement_success_rate": successful_intakes / total_intakes
            if total_intakes
            else None,
            "requirement_needs_human_rate": needs / total_intakes if total_intakes else None,
            "requirement_correction_count": corrections,
            "requirement_correction_rate": corrections / len(briefs) if briefs else None,
            "confidence_distribution": dict(
                Counter(
                    "LOW"
                    if b["confidence"] < 0.6
                    else "MEDIUM"
                    if b["confidence"] < 0.85
                    else "HIGH"
                    for b in briefs
                )
            ),
            "planning_first_pass": reports[0].verdict != "FAIL" if reports else None,
            "planning_iterations": workflow.planning_iteration_count,
            "human_first_pass_approval": decisions[0].decision == "APPROVE" if decisions else None,
            "human_rejection_count": sum(
                g.decision in {"REJECT", "MODIFY", "REQUEST_ALTERNATIVE"} for g in decisions
            ),
            "hard_gate_distribution": dict(
                Counter(issue["code"] for r in reports for issue in r.body["hard_gate_issues"])
            ),
            "technical_retry_count": retries,
        }

    def supersede(self, brief):
        model = self.session.get(orm.CreativeBriefModel, brief.id)
        model.status = domain.BriefStatus.SUPERSEDED
        self.session.flush()

    def brief(self, workflow_id, version=None):
        statement = select(orm.CreativeBriefModel).where(
            orm.CreativeBriefModel.workflow_id == workflow_id
        )
        if version is not None:
            statement = statement.where(orm.CreativeBriefModel.version == version)
        model = self.session.scalar(
            statement.order_by(orm.CreativeBriefModel.version.desc()).limit(1)
        )
        return to_domain(model, domain.CreativeBrief) if model else None

    def automatic_plan_count(self, workflow_id, brief_id, after=None):
        from sqlalchemy import func

        statement = (
            select(func.count())
            .select_from(orm.PlanGenerationModel)
            .where(
                orm.PlanGenerationModel.workflow_id == workflow_id,
                orm.PlanGenerationModel.brief_id == brief_id,
            )
        )
        if after is not None:
            statement = statement.where(orm.PlanGenerationModel.created_at > after)
        return self.session.scalar(statement)

    def generation(self, workflow_id, plan_id):
        model = self.session.scalar(
            select(orm.PlanGenerationModel).where(
                orm.PlanGenerationModel.workflow_id == workflow_id,
                orm.PlanGenerationModel.plan_id == plan_id,
            )
        )
        return to_domain(model, domain.PlanGeneration) if model else None

    def generation_for_plan(self, plan_id):
        model = self.session.scalar(
            select(orm.PlanGenerationModel).where(orm.PlanGenerationModel.plan_id == plan_id)
        )
        return to_domain(model, domain.PlanGeneration) if model else None

    def review(self, workflow_id, plan_id):
        model = self.session.scalar(
            select(orm.PlanReviewReportModel)
            .where(
                orm.PlanReviewReportModel.workflow_id == workflow_id,
                orm.PlanReviewReportModel.plan_id == plan_id,
            )
            .order_by(orm.PlanReviewReportModel.created_at.desc(), orm.PlanReviewReportModel.id)
            .limit(1)
        )
        return to_domain(model, domain.PlanReviewReport) if model else None

    def input_event(self, workflow_id):
        from novel_os.domain.workflow import WorkflowEvent

        model = self.session.scalar(
            select(WorkflowEventModel)
            .where(
                WorkflowEventModel.workflow_id == workflow_id,
                WorkflowEventModel.event_type.in_(["CREATE", "CORRECT_REQUIREMENT"]),
            )
            .order_by(WorkflowEventModel.expected_state_version.desc())
            .limit(1)
        )
        if model is None or not model.payload.get("raw_requirement"):
            raise DomainError("CONTEXT_MISSING", "Workflow has no chapter requirement input")
        return to_domain(model, WorkflowEvent)

    def reports_by_ids(self, workflow_id, report_ids):
        return [
            to_domain(row, domain.PlanReviewReport)
            for row in self.session.scalars(
                select(orm.PlanReviewReportModel).where(
                    orm.PlanReviewReportModel.workflow_id == workflow_id,
                    orm.PlanReviewReportModel.id.in_(report_ids),
                )
            )
        ]

    def last_human_directive(self, workflow_id):
        from novel_os.domain.workflow import HumanGate
        from novel_os.models.workflow import HumanGateModel

        row = self.session.scalar(
            select(HumanGateModel)
            .where(HumanGateModel.workflow_id == workflow_id, HumanGateModel.decision.is_not(None))
            .order_by(HumanGateModel.opened_state_version.desc())
            .limit(1)
        )
        return to_domain(row, HumanGate) if row else None

    def history(self, entity_type, workflow_id, limit=100, offset=0):
        model = MAPPINGS[entity_type]
        return [
            to_domain(row, entity_type)
            for row in self.session.scalars(
                select(model)
                .where(model.workflow_id == workflow_id)
                .order_by(model.created_at, model.id)
                .limit(limit)
                .offset(offset)
            )
        ]
