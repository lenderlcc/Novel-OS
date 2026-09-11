from dataclasses import replace

from novel_os.domain.agents import AgentRun, AgentTask, RunStatus
from novel_os.domain.core import AuditRecord, CommandContext
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.core import CoreRepository
from novel_os.workflow.audit import snapshot

RELEASE_LEASE = dict(lease_owner=None, lease_token=None, lease_expires_at=None, heartbeat_at=None)


def worker_context(worker_id: str, run_id=None):
    return CommandContext(str(run_id or "agent-worker"), worker_id, ActorType.SYSTEM)


class TaskHistory:
    def __init__(self, session):
        self.repo = AgentTaskRepository(session)
        self.core = CoreRepository(session)

    def audit(self, task: AgentTask, before, after, context, reason):
        chapter = self.core.get_chapter(task.project_id, task.target_ref)
        self.core.add(
            AuditRecord(
                project_id=task.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=task.target_ref,
                target_version=chapter.version,
                action=AuditAction.UPDATE if before else AuditAction.CREATE,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason=reason,
                before=snapshot(before) if before else {},
                after={
                    **snapshot(after),
                    "agent_task_id": str(task.task_id),
                    "workflow_id": str(task.workflow_instance_id),
                },
            )
        )

    def task(self, before: AgentTask, context, reason, **changes):
        after = self.repo.save(replace(before, version=before.version + 1, **changes))
        self.audit(after, before, after, context, reason)
        return after

    def finish_run(self, task, run: AgentRun, context, status: RunStatus, **changes):
        finished = self.repo.clock()
        after = self.repo.save(
            replace(
                run,
                status=status,
                finished_at=finished,
                duration_ms=max(
                    0, int((finished - (run.started_at or run.claimed_at)).total_seconds() * 1000)
                ),
                **changes,
            )
        )
        self.audit(task, run, after, context, "Agent attempt finished")
        return after
