"""Bound automatic repair per Brief and human directive; never force a passing verdict."""

from novel_os.domain.workflow import GuardFailure
from novel_os.repositories.planning import PlanningRepository

MAX_AUTOMATIC_PLANS = 2


def planning_budget_failure(session, workflow):
    if workflow.simulation:
        return None
    repo = PlanningRepository(session)
    brief = repo.brief(workflow.id)
    if brief is None:
        return None
    directive = repo.last_human_directive(workflow.id)
    count = repo.automatic_plan_count(
        workflow.id, brief.id, after=directive.decided_at if directive else None
    )
    if count >= MAX_AUTOMATIC_PLANS:
        return GuardFailure(
            "PLANNING_ITERATION_LIMIT",
            "Two automatic Plans exhausted; inspect the Review and clarify the requirement "
            "before continuing",
            "planning_budget",
        )
    return None
