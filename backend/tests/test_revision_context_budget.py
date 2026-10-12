from dataclasses import replace
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.context.policies import TokenBudgetService
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.agents import AgentId, Capability
from novel_os.domain.context import ContextRequest
from novel_os.prompts.contracts import canonical
from novel_os.prompts.runtime import PromptRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.profiles import ModelProfileRegistry
from novel_os.providers.tokens import prompt_overhead
from novel_os.quality.policy import indexed_paragraphs
from tests.context.test_context import item


@pytest.mark.parametrize(
    ("task_type", "agent", "output", "extra_size"),
    [
        ("PLAN_CHAPTER_REVISION", AgentId.A06_REVISION, "chapter_revision_plan", 0),
        ("REVISE_CHAPTER", AgentId.A06_REVISION, "chapter_revision_result", 25000),
        ("VALIDATE_REVISION_FIDELITY", AgentId.A05_REVIEW, "revision_fidelity", 40000),
    ],
)
def test_revision_capacity_preserves_complete_evidence(task_type, agent, output, extra_size):
    registry = ContextProfileRegistry()
    old = registry.resolve("CP-007", 4)
    new = registry.for_task(task_type)
    assert old.profile_hash == "44dc4887161e5eb5e2d206c0e9df009e7d7937f7fe05abf67705c78cfad6b9b9"
    assert new.version == 8 and {s.selector_id for s in new.selectors} >= {
        s.selector_id for s in old.selectors
    }
    assert new.future_knowledge_policy == old.future_knowledge_policy
    request = ContextRequest(
        project_id=uuid4(), task_id=uuid4(), chapter_id=uuid4(), task_type=task_type
    )
    runtime = PromptRuntime(
        MockModelProvider(), tasks=TaskDefinitionRegistry(model_profile="lingzhi-structured")
    )
    skeleton = runtime.prepare(
        task_id=request.task_id,
        task_type=task_type,
        agent_id=agent,
        attempt=1,
        target_ref=request.chapter_id,
        output_kind=output,
        capabilities={Capability.PROPOSE_DRAFT, Capability.REVIEW},
        constraints=(),
        context_payload={},
    )
    # Representative multi-source Chinese prose/diagnosis/authority documents;
    # independent of any acceptance story, all remain P0 and byte-identical.
    sizes = [7000, 15000, 50000, 21000, 5000, extra_size]
    evidence = [
        item(request, payload_json=canonical({"text": "完整原文" * (size // 12)}))
        for size in sizes
        if size
    ]
    overhead, reserve = prompt_overhead(skeleton), skeleton.profile.max_output_tokens
    budget = TokenBudgetService()
    assert budget.select(request, old, evidence, overhead, reserve)[3]
    selected, excluded, cost, overflow = budget.select(request, new, evidence, overhead, reserve)
    assert not overflow and not excluded and set(selected) == set(evidence)
    assert cost + overhead + reserve <= new.token_budget
    oversized = replace(evidence[0], payload_json=canonical({"text": "完整原文" * 40000}))
    assert budget.select(request, new, [oversized], overhead, reserve)[3]


def test_numbered_long_source_and_candidate_fit_new_budget_without_dropping_evidence():
    registry = ContextProfileRegistry()
    old, new = registry.resolve("CP-007", 5), registry.for_task("VALIDATE_REVISION_FIDELITY")
    assert old.token_budget == 240000
    assert new.version == 8 and new.token_budget == 400000
    assert {s.selector_id for s in new.selectors} >= {s.selector_id for s in old.selectors}
    request = ContextRequest(
        project_id=uuid4(),
        task_id=uuid4(),
        chapter_id=uuid4(),
        task_type="VALIDATE_REVISION_FIDELITY",
    )
    skeleton = PromptRuntime(
        MockModelProvider(), tasks=TaskDefinitionRegistry(model_profile="lingzhi-structured")
    ).prepare(
        task_id=request.task_id,
        task_type=request.task_type,
        agent_id=AgentId.A05_REVIEW,
        attempt=1,
        target_ref=request.chapter_id,
        output_kind="revision_fidelity",
        capabilities={Capability.REVIEW},
        constraints=(),
        context_payload={},
    )
    content = "\n\n".join("完整原稿证据" * 17 for _ in range(196))
    evidence = [
        item(
            request,
            selector_id=selector,
            payload_json=canonical({"content": content, "paragraphs": indexed_paragraphs(content)}),
        )
        for selector in ["target-version", "revision-candidate"]
    ]
    evidence.append(item(request, payload_json=canonical({"review_and_plan": "依据" * 15000})))
    overhead, reserve = prompt_overhead(skeleton), skeleton.profile.max_output_tokens
    budget = TokenBudgetService()
    assert budget.select(request, old, evidence, overhead, reserve)[3]
    selected, excluded, cost, overflow = budget.select(request, new, evidence, overhead, reserve)
    assert not overflow and not excluded and set(selected) == set(evidence)
    assert cost + overhead + reserve <= new.token_budget
    assert new.token_budget < ModelProfileRegistry().context_window(skeleton.profile)
