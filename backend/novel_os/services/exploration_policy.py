"""A03's bounded internal step and exact, reusable selection binding."""

import json

from novel_os.agents.planning_schemas import CreativeBriefOutput
from novel_os.domain.workflow import ChapterState, GateDecision
from novel_os.prompts.contracts import canonical
from novel_os.repositories.planning import PlanningRepository
from novel_os.services.planning_freshness import PlanningContextStale, PlanningFreshness

EXPLORATION_TASK = "EXPLORE_CHAPTER_CONCEPTS"
SELECTION_BINDING = "CREATIVE_EXPLORATION_BINDING"


def supports_exploration(workflow):
    return (
        not workflow.simulation
        and workflow.workflow_definition_id == "chapter-planning"
        and workflow.workflow_definition_version == 4
    )


def should_explore(brief):
    if brief is None:
        return False
    output = (
        brief
        if isinstance(brief, CreativeBriefOutput)
        else CreativeBriefOutput.model_validate(brief.body)
    )
    freedom = output.creative_freedom
    return freedom.level == "HIGH" or (
        freedom.level == "MEDIUM" and "LOCAL_CONFLICT" in freedom.allowed_operations
    )


class ExplorationPolicy:
    def __init__(self, session):
        self.session = session
        self.repo = PlanningRepository(session)

    def invalidated_by_user(self, artifact):
        # Approval preserves the selection and must not hide an earlier replan directive.
        directive = self.repo.last_human_directive(
            artifact.workflow_id,
            decisions={GateDecision.REJECT, GateDecision.MODIFY, GateDecision.REQUEST_ALTERNATIVE},
        )
        generation = (
            self.repo.generation(artifact.workflow_id, directive.artifact_id) if directive else None
        )
        return bool(
            directive
            and directive.decided_at
            and generation
            and generation.brief_id == artifact.brief_id
            and directive.decided_at > artifact.created_at
        )

    def needs_exploration(self, workflow, brief, *, refresh_stale=False):
        if not should_explore(brief):
            return False
        artifact = self.repo.exploration(workflow.id, brief.id)
        return (
            artifact is None
            or self.invalidated_by_user(artifact)
            or (
                refresh_stale
                and not PlanningFreshness(self.session).evidence_is_fresh(artifact, brief=True)
            )
        )

    def selected(self, workflow):
        if not supports_exploration(workflow):
            return None
        brief = PlanningFreshness(self.session).current_brief(workflow)
        if not should_explore(brief):
            return None
        artifact = self.repo.exploration(workflow.id, brief.id)
        if (
            artifact is None
            or artifact.status != "READY"
            or self.invalidated_by_user(artifact)
            or not PlanningFreshness(self.session).evidence_is_fresh(artifact, brief=True)
        ):
            raise PlanningContextStale(
                "Creative exploration is unavailable; refresh its inputs before planning",
                ChapterState.C04_CHAPTER_PLANNING,
            )
        return artifact

    def scheduling_input(self, workflow):
        artifact = self.selected(workflow)
        return canonical(
            {
                "type": SELECTION_BINDING,
                "creative_exploration_id": str(artifact.id) if artifact else None,
                "selected_candidate_id": artifact.body["selected_candidate_id"]
                if artifact
                else None,
            }
        )

    def check_scheduled(self, task, workflow):
        if task.task_type != "PLAN_CHAPTER" or not supports_exploration(workflow):
            return None
        artifact = self.selected(workflow)
        expected = {
            "type": SELECTION_BINDING,
            "creative_exploration_id": str(artifact.id) if artifact else None,
            "selected_candidate_id": artifact.body["selected_candidate_id"] if artifact else None,
        }
        pins = []
        for entry in task.requirements:
            try:
                value = json.loads(entry)
            except ValueError:
                continue
            if isinstance(value, dict) and value.get("type") == SELECTION_BINDING:
                pins.append(value)
        if pins != [expected]:
            raise PlanningContextStale(
                "The scheduled creative selection changed",
                ChapterState.C04_CHAPTER_PLANNING,
            )
        return artifact
