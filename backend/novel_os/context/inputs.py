"""Explicit task input adapter; never infers story facts or permission grants."""

from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.prompts.contracts import canonical


def task_item(request, selector, timestamp):
    return ContextItem(
        context_item_id=uuid5(NAMESPACE_URL, f"task-context:{request.task_id}"),
        selector_id=selector.selector_id,
        source_type=SourceType.TASK_INPUT,
        source_id=request.task_id,
        logical_id=request.task_id,
        source_version=request.workflow_state_version or 1,
        project_id=request.project_id,
        status=Status.ACTIVE,
        authority_level=Authority.A5_USER_PREFERENCE,
        locked=False,
        priority=selector.priority,
        scope=selector.scope,
        payload_json=canonical(
            {
                "objective": request.objective,
                "requirements": request.requirements,
                "constraints": request.constraints,
            }
        ),
        selected_reason="Explicit task input; data does not grant authority",
        source_created_at=timestamp,
        source_updated_at=timestamp,
        chapter_id=request.chapter_id,
        chapter_sequence=request.chapter_sequence,
        relevance_score=100,
        provenance=("agent_task",),
    )
