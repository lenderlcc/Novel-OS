import json
from dataclasses import asdict

from novel_os.domain.core import AuditRecord, CommandContext
from novel_os.domain.enums import AuditAction, ObjectType
from novel_os.domain.workflow import WorkflowTransition
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.workflows import WorkflowRepository


def snapshot(value) -> dict:
    return json.loads(json.dumps(asdict(value), default=str))


class TransitionAudit:
    """Workflow history links to the existing append-only Chapter audit stream."""

    def __init__(self, core: CoreRepository, workflows: WorkflowRepository):
        self.core = core
        self.workflows = workflows

    def record(self, before, after, command, context: CommandContext, guards, reason):
        chapter = self.core.get_chapter(after.project_id, after.chapter_id)
        audit = self.core.add(
            AuditRecord(
                project_id=after.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=after.chapter_id,
                target_version=chapter.version,
                action=AuditAction.UPDATE if before else AuditAction.CREATE,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason=reason,
                before=snapshot(before) if before else {},
                after={
                    **snapshot(after),
                    "workflow_id": str(after.id),
                    "event_id": str(command.event_id),
                    "event_type": command.event_type,
                    "simulation": True,
                },
            )
        )
        self.workflows.add(
            WorkflowTransition(
                workflow_id=after.id,
                event_id=command.event_id,
                from_state=before.current_state if before else None,
                to_state=after.current_state,
                from_status=before.status if before else None,
                to_status=after.status,
                from_version=before.state_version if before else 0,
                to_version=after.state_version,
                guards=list(guards),
                reason=reason,
                audit_record_id=audit.id,
            )
        )

    def gate(self, workflow, before, after, context):
        chapter = self.core.get_chapter(workflow.project_id, workflow.chapter_id)
        self.core.add(
            AuditRecord(
                project_id=workflow.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=workflow.chapter_id,
                target_version=chapter.version,
                action=AuditAction.UPDATE if before else AuditAction.CREATE,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason="Human gate " + after.status.value,
                before=snapshot(before) if before else {},
                after={
                    **snapshot(after),
                    "workflow_id": str(workflow.id),
                    "human_gate_id": str(after.id),
                },
            )
        )
