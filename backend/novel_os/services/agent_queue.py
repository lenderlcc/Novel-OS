"""Short application transactions for claim, fencing, heartbeat and crash recovery."""

import re
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

from novel_os.domain.agents import AgentRun, RunStatus, TaskLease, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.agent_results import AgentResultHandler, valid_lease
from novel_os.services.task_history import RELEASE_LEASE, TaskHistory, worker_context
from novel_os.services.task_scheduling import TaskScheduler, expects_task


class AgentQueue:
    def __init__(self, session, *, lease_seconds=30):
        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive")
        self.session = session
        self.repo = AgentTaskRepository(session)
        self.history = TaskHistory(session)
        self.lease_seconds = lease_seconds

    def claim(self, worker_id: str, *, profile_for_task=None) -> TaskLease | None:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", worker_id):
            raise DomainError("VALIDATION_ERROR", "Invalid worker identity")
        with self.session.begin():
            task = self.repo.next_claimable()
            if task is None:
                workflow_id = self.repo.unscheduled_workflow()
                if workflow_id is None:
                    return None
                workflow = WorkflowRepository(self.session).get(workflow_id, for_update=True)
                TaskScheduler(self.session).synchronize(workflow, worker_context(worker_id))
                task = self.repo.next_claimable()
                if task is None:
                    return None
            timestamp = self.repo.clock()
            # A heartbeat may have committed between candidate selection and task locking.
            if (task.status == TaskStatus.PENDING and task.available_at > timestamp) or (
                task.status in {TaskStatus.CLAIMED, TaskStatus.RUNNING}
                and task.lease_expires_at > timestamp
            ):
                return None
            workflow = WorkflowRepository(self.session).get(task.workflow_instance_id)
            context = worker_context(worker_id)
            old_run = None
            if task.status in {TaskStatus.CLAIMED, TaskStatus.RUNNING}:
                old_run = self.repo.attempt(task.task_id, task.attempt_count)
                self.history.finish_run(
                    task,
                    old_run,
                    context,
                    RunStatus.ABANDONED,
                    error_code="LEASE_EXPIRED",
                    error_message="Worker lease expired",
                    disposition="LEASE_LOST",
                )
            if not expects_task(workflow, task) or task.attempt_count >= task.max_attempts:
                stale = not expects_task(workflow, task)
                self.history.task(
                    task,
                    context,
                    "Expired or stale task cannot execute",
                    status=TaskStatus.CANCELLED if stale else TaskStatus.FAILED,
                    completed_at=self.repo.clock(),
                    last_error_code="STALE_TASK" if stale else "RETRY_EXHAUSTED",
                    **RELEASE_LEASE,
                )
                if not stale and old_run:
                    AgentResultHandler(self.session).emit(
                        task,
                        old_run,
                        "FATAL_ERROR",
                        {"reason": "Worker recovery retry budget exhausted"},
                    )
                return None
            token = uuid4()
            timestamp = self.repo.clock()
            task = self.history.task(
                task,
                context,
                "Worker claimed task",
                status=TaskStatus.CLAIMED,
                attempt_count=task.attempt_count + 1,
                claimed_at=timestamp,
                started_at=None,
                lease_owner=worker_id,
                lease_token=token,
                heartbeat_at=timestamp,
                lease_expires_at=timestamp + timedelta(seconds=self.lease_seconds),
            )
            profile = profile_for_task(task.task_type) if profile_for_task else None
            run = self.repo.add(
                AgentRun(
                    task_id=task.task_id,
                    attempt_number=task.attempt_count,
                    worker_id=worker_id,
                    lease_token=token,
                    claimed_at=timestamp,
                    provider=profile.provider if profile else "mock",
                    model=profile.model if profile else "mock-v1",
                    input_metadata={
                        "task_type": task.task_type,
                        "state_version": task.workflow_state_version,
                        "output_schema": task.expected_output_schema,
                    },
                )
            )
            self.history.audit(task, None, run, context, "Agent attempt claimed")
            return TaskLease(task.task_id, run.run_id, worker_id, token, task.attempt_count)

    def start(self, lease):
        with self.session.begin():
            task, workflow = AgentResultHandler(self.session).lock_task(lease.task_id)
            if not valid_lease(task, lease, self.repo.clock()):
                return None
            run = self.repo.run(lease.run_id)
            if run.task_id != task.task_id or run.lease_token != lease.token:
                return None
            context = worker_context(lease.worker_id, lease.run_id)
            if not expects_task(workflow, task):
                self.history.task(
                    task,
                    context,
                    "Stale claimed task cancelled",
                    status=TaskStatus.CANCELLED,
                    completed_at=self.repo.clock(),
                    **RELEASE_LEASE,
                )
                self.history.finish_run(
                    task, run, context, RunStatus.CANCELLED, disposition="STALE_IGNORED"
                )
                return None
            if task.status == TaskStatus.RUNNING:
                return task
            timestamp = self.repo.clock()
            task = self.history.task(
                task,
                context,
                "Agent attempt started",
                status=TaskStatus.RUNNING,
                started_at=timestamp,
            )
            updated = self.repo.save(replace(run, status=RunStatus.RUNNING, started_at=timestamp))
            self.history.audit(task, run, updated, context, "Agent attempt started")
            return task

    def heartbeat(self, lease):
        with self.session.begin():
            task = self.repo.get(lease.task_id, for_update=True)
            timestamp = self.repo.clock()
            if not valid_lease(task, lease, timestamp):
                return False
            self.repo.save(
                replace(
                    task,
                    version=task.version + 1,
                    heartbeat_at=timestamp,
                    lease_expires_at=timestamp + timedelta(seconds=self.lease_seconds),
                )
            )
            return True
