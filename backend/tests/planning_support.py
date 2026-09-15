import json
from types import SimpleNamespace
from uuid import uuid4

from novel_os.agents.planning_mock import response
from novel_os.agents.provider import MockModelProvider
from novel_os.domain.agents import MockScenario
from novel_os.domain.context import SourceType
from novel_os.providers.base import ModelResponse


class RecordedProvider(MockModelProvider):
    """Offline structured responses; no claim to measure live-model language quality."""

    def __init__(self, transform=None):
        super().__init__()
        self.transform = transform or (lambda request, body: None)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        body = json.loads(super().generate(request).content)
        self.transform(request, body)
        return ModelResponse(json.dumps(body, ensure_ascii=False))


def fixture_outputs():
    def item(source, payload):
        return SimpleNamespace(
            source_type=source,
            logical_id=uuid4(),
            source_version=1,
            structured_payload=payload,
            locked=False,
        )

    raw = item(SourceType.TASK_INPUT, {"objective": "必须找到线索。不能杀死主角。保留人物信任。"})
    request = SimpleNamespace(
        task_id=uuid4(),
        target_ref=uuid4(),
        output_kind="creative_brief",
        context_package=SimpleNamespace(items=[raw]),
    )
    brief = response(request, MockScenario.SUCCESS)
    brief_item = item(SourceType.CREATIVE_BRIEF, brief["result"])
    request.output_kind = "chapter_plan"
    request.context_package.items = [brief_item]
    plan = response(request, MockScenario.SUCCESS)
    plan_item = item(SourceType.CHAPTER_PLAN, {"planning": plan["result"]})
    request.output_kind = "plan_review"
    request.context_package.items = [brief_item, plan_item]
    review = response(request, MockScenario.SUCCESS)
    return brief, plan, review
