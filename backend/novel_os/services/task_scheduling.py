"""Workflow-side task factory. Called inside the workflow transition transaction."""

from datetime import timedelta

from novel_os.agents.registry import STAGE_TASKS
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

    def synchronize(self, workflow, context, *, priority=0, delay_seconds=0):
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
        definition = STAGE_TASKS[workflow.current_state]
        existing = self.repo.logical(workflow.id, workflow.state_version, definition.task_type)
        if existing:
            return existing
        timestamp = self.repo.clock()
        task = self.repo.add(
            AgentTask(
                project_id=workflow.project_id,
                workflow_instance_id=workflow.id,
                workflow_state=workflow.current_state,
                workflow_state_version=workflow.state_version,
                agent_id=definition.agent_id,
                task_type=definition.task_type,
                target_ref=workflow.chapter_id,
                objective="Execute the mock " + definition.task_type + " contract",
                constraints=[
                    "Simulation only",
                    "No approval, lock, canon commit or direct database access",
                ],
                capabilities=[definition.capability.value],
                created_at=timestamp,
                available_at=timestamp + timedelta(seconds=delay_seconds),
                priority=priority,
            )
        )
        self.history.audit(task, None, task, context, "Workflow scheduled agent task")
        return task
