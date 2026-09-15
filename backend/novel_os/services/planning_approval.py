"""Generated Plans can gain authority only through their exact reviewed HumanGate."""

from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState, GateStatus, GateType, WorkflowStatus
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.workflows import WorkflowRepository


def validate_generated_plan_approval(session, plan, gate_id):
    generation = PlanningRepository(session).generation_for_plan(plan.id)
    if generation is None:
        return  # Preserve NOVEL-002 approval of manually created Plans.
    if gate_id is None:
        raise DomainError("AUTHORITY_DENIED", "Generated Plans require their reviewed HumanGate")
    workflows = WorkflowRepository(session)
    workflow = workflows.get(generation.workflow_id, for_update=True)
    gate = workflows.gate(gate_id)
    if (
        gate.workflow_id != workflow.id
        or gate.status != GateStatus.WAITING
        or gate.gate_type != GateType.PLAN_APPROVAL
        or gate.artifact_id != plan.id
        or gate.artifact_version != plan.version
        or workflow.plan_version != plan.version
        or workflow.current_state != ChapterState.C06_PLAN_APPROVAL
        or workflow.status != WorkflowStatus.WAITING_HUMAN
    ):
        raise DomainError("AUTHORITY_DENIED", "Approval requires the exact waiting planning Gate")
    from novel_os.services.planning_results import PlanningResultService

    PlanningResultService(session).check_transition(workflow, ChapterState.C06_PLAN_APPROVAL)
