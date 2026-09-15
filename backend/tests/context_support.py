"""Explicit context fixtures for pre-006 isolated Runtime contract tests.

These tests exercise prompt/provider/authority contracts without a Context database.
Production Worker tests still build and replace this fixture through ContextService.
New 006 integration tests use the production AgentRuntime directly.
"""

from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from novel_os.agents.runtime import AgentRuntime
from novel_os.context.engine import ContextEngine
from novel_os.context.inputs import task_item
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.context import ContextRequest, ContextStatus, SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.prompts.contracts import canonical
from novel_os.services.memory_query import CandidateBatch

BOUND_CONTEXT = {}


def task_context(task):
    if task.task_id in BOUND_CONTEXT:
        return BOUND_CONTEXT[task.task_id]
    request = ContextRequest(
        project_id=task.project_id,
        task_id=task.task_id,
        task_type=task.task_type,
        chapter_id=task.target_ref,
        workflow_id=task.workflow_instance_id,
        workflow_state_version=task.workflow_state_version,
        attempt_number=task.attempt_count,
        objective=task.objective,
        constraints=tuple(task.constraints),
        requirements=tuple(task.requirements),
        target_version=1,
        approved_plan_version=1,
    )
    profile = ContextProfileRegistry().for_task(task.task_type)
    items = []
    for selector in profile.selectors:
        if not selector.required:
            continue
        item = task_item(request, selector, task.created_at)
        if selector.source_type != SourceType.TASK_INPUT:
            item = replace(
                item,
                source_type=selector.source_type,
                source_id=task.target_ref,
                logical_id=task.target_ref,
                source_version=1,
                status=Status.APPROVED,
                authority_level=Authority.A2_USER_APPROVED,
                context_item_id=uuid5(
                    NAMESPACE_URL, f"fixture:{task.task_id}:{selector.selector_id}"
                ),
                payload_json=canonical(
                    {"fixture": selector.source_type, "text": "Contract test source"}
                ),
            )
        items.append(item)
    result = ContextEngine().build(request, profile, CandidateBatch(tuple(items)))
    assert result.status == ContextStatus.READY, result
    return result.package


class ContextFixtureRuntime(AgentRuntime):
    def prepare(self, task, context_package=None):
        return super().prepare(task, context_package or task_context(task))
