from dataclasses import asdict
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from novel_os.domain.agents import AgentRun, AgentTask, TaskStatus
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import WorkflowStatus
from novel_os.models.agents import AgentRunModel, AgentTaskModel
from novel_os.models.core import ProjectModel
from novel_os.models.workflow import WorkflowInstanceModel
from novel_os.repositories.core import to_domain

ACTIVE = (TaskStatus.CLAIMED, TaskStatus.RUNNING)


class AgentTaskRepository:
    """Only persistence/row locking; no transaction completion or workflow commands."""

    def __init__(self, session: Session):
        self.session = session

    def clock(self):
        return self.session.scalar(select(func.clock_timestamp()))

    def add(self, entity):
        model = AgentTaskModel if isinstance(entity, AgentTask) else AgentRunModel
        self.session.add(model(**asdict(entity)))
        self.session.flush()
        return entity

    def save(self, entity):
        model_type, key = (
            (AgentTaskModel, entity.task_id)
            if isinstance(entity, AgentTask)
            else (AgentRunModel, entity.run_id)
        )
        model = self.session.get(model_type, key)
        if model is None:
            raise DomainError("NOT_FOUND", "Execution record not found")
        for name, value in asdict(entity).items():
            setattr(model, name, value)
        self.session.flush()
        return entity

    def get(self, task_id: UUID, *, for_update=False):
        query = select(AgentTaskModel).where(AgentTaskModel.task_id == task_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.session.scalar(query)
        if row is None:
            raise DomainError("NOT_FOUND", "Agent task not found")
        return to_domain(row, AgentTask)

    def run(self, run_id: UUID):
        row = self.session.get(AgentRunModel, run_id, populate_existing=True)
        if row is None:
            raise DomainError("NOT_FOUND", "Agent run not found")
        return to_domain(row, AgentRun)

    def attempt(self, task_id: UUID, number: int):
        row = self.session.scalar(
            select(AgentRunModel).where(
                AgentRunModel.task_id == task_id, AgentRunModel.attempt_number == number
            )
        )
        return to_domain(row, AgentRun) if row else None

    def next_claimable(self):
        query = (
            select(AgentTaskModel)
            .join(ProjectModel, ProjectModel.id == AgentTaskModel.project_id)
            .where(
                or_(
                    and_(
                        AgentTaskModel.status == TaskStatus.PENDING,
                        AgentTaskModel.available_at <= func.clock_timestamp(),
                    ),
                    and_(
                        AgentTaskModel.status.in_(ACTIVE),
                        AgentTaskModel.lease_expires_at <= func.clock_timestamp(),
                    ),
                )
            )
            .order_by(
                AgentTaskModel.priority.desc(),
                AgentTaskModel.available_at,
                AgentTaskModel.created_at,
                AgentTaskModel.task_id,
            )
            .with_for_update(of=ProjectModel, skip_locked=True)
            .limit(1)
            .execution_options(populate_existing=True)
        )
        # Take the same Project root lock as all workflow mutations before the task lock.
        skipped = []
        while True:
            candidate = self.session.scalar(query.where(AgentTaskModel.task_id.not_in(skipped)))
            if candidate is None:
                return None
            row = self.session.scalar(
                select(AgentTaskModel)
                .where(AgentTaskModel.task_id == candidate.task_id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if row is not None:
                return to_domain(row, AgentTask)
            # A task-only heartbeat lock must not hide later runnable tasks. Exclude
            # this candidate on the next pass, retaining the Project → Task lock order.
            skipped.append(candidate.task_id)

    def logical(self, workflow_id, state_version, task_type):
        row = self.session.scalar(
            select(AgentTaskModel).where(
                AgentTaskModel.workflow_instance_id == workflow_id,
                AgentTaskModel.workflow_state_version == state_version,
                AgentTaskModel.task_type == task_type,
            )
        )
        return to_domain(row, AgentTask) if row else None

    def unscheduled_workflow(self):
        # Backfill an existing NOVEL-003 waiting stage after the additive migration.
        has_task = (
            select(AgentTaskModel.task_id)
            .where(
                AgentTaskModel.workflow_instance_id == WorkflowInstanceModel.id,
                AgentTaskModel.workflow_state_version == WorkflowInstanceModel.state_version,
            )
            .exists()
        )
        return self.session.scalar(
            select(WorkflowInstanceModel.id)
            .join(ProjectModel, ProjectModel.id == WorkflowInstanceModel.project_id)
            .where(WorkflowInstanceModel.status == WorkflowStatus.WAITING_AGENT, ~has_task)
            .order_by(WorkflowInstanceModel.id)
            .with_for_update(of=ProjectModel, skip_locked=True)
            .limit(1)
        )

    def unstarted(self, workflow_id):
        rows = self.session.scalars(
            select(AgentTaskModel)
            .where(
                AgentTaskModel.workflow_instance_id == workflow_id,
                AgentTaskModel.status.in_([TaskStatus.PENDING, TaskStatus.CLAIMED]),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [to_domain(row, AgentTask) for row in rows]

    def list_tasks(self, workflow_id, limit=100, offset=0):
        rows = self.session.scalars(
            select(AgentTaskModel)
            .where(AgentTaskModel.workflow_instance_id == workflow_id)
            .order_by(AgentTaskModel.workflow_state_version, AgentTaskModel.task_id)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, AgentTask) for row in rows]

    def list_runs(self, task_id, limit=100, offset=0):
        rows = self.session.scalars(
            select(AgentRunModel)
            .where(AgentRunModel.task_id == task_id)
            .order_by(AgentRunModel.attempt_number)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, AgentRun) for row in rows]
