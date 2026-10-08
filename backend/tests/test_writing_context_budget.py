from dataclasses import replace
from uuid import uuid4

from novel_os.agents.planning_schemas import ChapterPlanOutput
from novel_os.agents.provider import MockModelProvider
from novel_os.context.policies import TokenBudgetService
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.agents import AgentId, Capability
from novel_os.domain.context import ContextRequest, SourceType
from novel_os.prompts.contracts import canonical
from novel_os.prompts.runtime import PromptRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.tokens import prompt_overhead
from tests.context.test_context import item
from tests.planning_support import fixture_outputs


def test_structured_chinese_plan_fits_writing_budget_without_dropping_p0():
    registry = ContextProfileRegistry()
    previous = registry.resolve("CP-005", 3)
    current = registry.resolve("CP-005", 4)
    assert current.version == 4
    assert (
        previous.profile_hash == "10f8501248c2ba3bad9faf94584bc5f7bc676df35d7417c0f1e42236d26f984f"
    )
    assert current.selectors == previous.selectors
    assert current.future_knowledge_policy == previous.future_knowledge_policy

    request = ContextRequest(
        project_id=uuid4(), task_id=uuid4(), chapter_id=uuid4(), task_type="WRITE_CHAPTER"
    )
    runtime = PromptRuntime(
        MockModelProvider(), tasks=TaskDefinitionRegistry(model_profile="lingzhi-structured")
    )
    skeleton = runtime.prepare(
        task_id=request.task_id,
        task_type=request.task_type,
        agent_id=AgentId.A04_WRITING,
        attempt=1,
        target_ref=request.chapter_id,
        output_kind="writing_result",
        capabilities={Capability.PROPOSE_DRAFT},
        constraints=(),
        context_payload={},
    )
    raw_plan = fixture_outputs()[1]["result"]
    raw_plan["scenes"] = [
        {
            **raw_plan["scenes"][0],
            "id": f"S{n}",
            **{
                key: "寻找线索时保留人物之间尚未说开的分歧。" * 20
                for key in (
                    "purpose",
                    "conflict",
                    "key_change",
                    "character_state_change",
                    "exit_condition",
                )
            },
        }
        for n in range(1, 5)
    ]
    for coverage in raw_plan["requirement_coverage"]:
        coverage["scene_ids"] = ["S1"]
    plan = ChapterPlanOutput.model_validate(raw_plan)
    approved = item(
        request,
        selector_id="approved-plan",
        source_type=SourceType.CHAPTER_PLAN,
        payload_json=canonical({"planning": plan.model_dump(mode="json")}),
    )
    budget = TokenBudgetService()
    overhead = prompt_overhead(skeleton)
    reserve = skeleton.profile.max_output_tokens
    assert budget.select(request, previous, [approved], overhead, reserve)[3]
    selected, excluded, cost, overflow = budget.select(
        request, current, [approved], overhead, reserve
    )
    assert selected == (approved,) and not excluded and not overflow
    assert cost + overhead + reserve <= current.token_budget

    oversized = replace(approved, payload_json=canonical({"content": "保留必需证据" * 10000}))
    selected, excluded, _, overflow = budget.select(
        request, current, [oversized], overhead, reserve
    )
    assert overflow and selected == (oversized,) and not excluded
