"""Workflow-side task factory. Called inside the workflow transition transaction."""

from datetime import timedelta

from novel_os.agents.registry import BUSINESS_STAGE_TASKS, STAGE_TASKS
from novel_os.domain.agents import AgentTask, RunStatus, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import WorkflowStatus
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.services.task_history import RELEASE_LEASE, TaskHistory


def expects_task(workflow, task):
    return (
        workflow.status == WorkflowStatus.WAITING_AGENT
        and workflow.current_state == task.workflow_state
        and workflow.state_version == task.workflow_state_version
        and workflow.project_id == task.project_id
        and workflow.chapter_id == task.target_ref
    )


class TaskScheduler:
    def __init__(self, session):
        self.session = session
        self.repo = AgentTaskRepository(session)
        self.history = TaskHistory(session)

    def synchronize(self, workflow, context, *, priority=0, delay_seconds=0, command=None):
        if not self.session.in_transaction():
            raise RuntimeError("Task scheduling requires the workflow transaction")
        if type(priority) is not int or not -100 <= priority <= 100 or not 0 <= delay_seconds <= 60:
            raise DomainError("VALIDATION_ERROR", "Invalid task scheduling policy")
        for task in self.repo.unstarted(workflow.id):
            if not expects_task(workflow, task):
                self.history.task(
                    task,
                    context,
                    "Workflow no longer expects task",
                    status=TaskStatus.CANCELLED,
                    completed_at=self.repo.clock(),
                    last_error_code="STALE_TASK",
                    **RELEASE_LEASE,
                )
                if task.status == TaskStatus.CLAIMED:
                    run = self.repo.attempt(task.task_id, task.attempt_count)
                    self.history.finish_run(
                        task,
                        run,
                        context,
                        RunStatus.CANCELLED,
                        disposition="STALE_IGNORED",
                        error_code="STALE_TASK",
                    )
        if workflow.status != WorkflowStatus.WAITING_AGENT:
            return None
        definition = (STAGE_TASKS if workflow.simulation else BUSINESS_STAGE_TASKS).get(
            workflow.current_state
        )
        from novel_os.agents.registry import WRITING_TASK
        from novel_os.services.writing_binding import supports_writing

        if supports_writing(workflow) and workflow.current_state == WRITING_TASK.state:
            definition = WRITING_TASK
        if definition is None:
            return None  # Deterministic controls and versioned handoff boundaries have no agent.

        existing = self.repo.logical(workflow.id, workflow.state_version, definition.task_type)
        if existing:
            return existing
        timestamp = self.repo.clock()
        objective = "Execute the mock " + definition.task_type + " contract"
        requirements = []
        if not workflow.simulation:
            from novel_os.prompts.contracts import canonical
            from novel_os.repositories.planning import PlanningRepository

            objective = (
                command.payload["raw_requirement"]
                if command and command.event_type == "CORRECT_REQUIREMENT"
                else PlanningRepository(self.session)
                .input_event(workflow.id)
                .payload["raw_requirement"]
            )
            planning = PlanningRepository(self.session)
            brief = planning.brief(workflow.id)
            gate = planning.last_human_directive(workflow.id)
            generation = planning.generation(workflow.id, gate.artifact_id) if gate else None
            if brief and brief.status == "READY" and generation and generation.brief_id == brief.id:
                requirements = [
                    canonical(
                        {
                            "type": "USER_PLANNING_DIRECTIVE",
                            "decision": gate.decision,
                            "reason": gate.reason,
                            "plan_id": str(gate.artifact_id),
                            "plan_version": gate.artifact_version,
                        }
                    )
                ]
        if definition.task_type in {"PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}:
            from novel_os.services.writing_profile_context import WritingProfileContext

            requirements.append(
                WritingProfileContext(self.session).scheduling_input(workflow.project_id)
            )
        task = self.repo.add(
            AgentTask(
                project_id=workflow.project_id,
                workflow_instance_id=workflow.id,
                workflow_state=workflow.current_state,
                workflow_state_version=workflow.state_version,
                agent_id=definition.agent_id,
                task_type=definition.task_type,
                target_ref=workflow.chapter_id,
                objective=objective,
                requirements=requirements,
                expected_output_schema=definition.result_schema,
                constraints=[
                    "Simulation only"
                    if workflow.simulation
                    else "Write from the exact approved Plan; local creativity only"
                    if definition.task_type == "WRITE_CHAPTER"
                    else "Planning only; no chapter prose",
                    "No approval, lock, canon commit or direct database access",
                ],
                capabilities=[definition.capability.value],
                created_at=timestamp,
                available_at=timestamp + timedelta(seconds=delay_seconds),
                priority=priority,
            )
        )
        if task.task_type == "WRITE_CHAPTER":
            from novel_os.services.writing_binding import WritingBindingService

            WritingBindingService(self.session).capture(task, workflow)
        self.history.audit(task, None, task, context, "Workflow scheduled agent task")
        return task
