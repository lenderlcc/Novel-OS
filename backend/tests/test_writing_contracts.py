import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.writing_mock import response
from novel_os.agents.writing_schemas import WritingAgentResult
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from tests.planning_support import fixture_outputs


def sample():
    plan = SimpleNamespace(
        selector_id="approved-plan",
        source_id=uuid4(),
        source_version=1,
        structured_payload={"planning": fixture_outputs()[1]["result"]},
    )
    request = SimpleNamespace(
        task_id=uuid4(), target_ref=uuid4(), context_package=SimpleNamespace(items=[plan])
    )
    return response(request, "WRITING_SUCCESS")


def test_generated_contract_is_the_same_schema_used_to_parse():
    definition = TaskDefinitionRegistry().get("WRITE_CHAPTER")
    assert definition.output_schema.model is WritingAgentResult
    body = sample()
    assert definition.output_schema.parse(json.dumps(body)) == WritingAgentResult.model_validate(
        body
    )
    assert len(definition.resolve(PromptRegistry())) == 9
    assert {c.value for c in definition.capabilities} == {"PROPOSE_DRAFT"}
    registry = ContextProfileRegistry()
    assert registry.for_task("WRITE_CHAPTER").version == 3
    assert registry.for_task("MOCK_WRITE").version == 2
    assert registry.for_task("WRITE_CHAPTER").future_knowledge_policy == "REQUIRED_ONLY"


@pytest.mark.parametrize(
    "field",
    [
        "chapter_id",
        "plan_id",
        "plan_version",
        "content",
        "scene_execution",
        "introduced_elements",
        "proposed_new_facts",
        "plan_deviations",
        "unresolved_questions",
        "assumptions",
        "knowledge_risk_flags",
        "style_notes",
        "confidence",
    ],
)
def test_required_writing_fields_cannot_be_omitted(field):
    body = sample()
    del body["result"][field]
    with pytest.raises(ValidationError):
        WritingAgentResult.model_validate(body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("content", "\x00"),
        ("plan_version", True),
        ("plan_version", 0),
        ("confidence", float("nan")),
        ("scene_execution", []),
    ],
)
def test_invalid_values_are_rejected(field, value):
    body = sample()
    body["result"][field] = value
    with pytest.raises(ValidationError):
        WritingAgentResult.model_validate(body)


def test_nested_control_metadata_is_rejected_and_prose_whitespace_is_preserved():
    body = sample()
    body["result"]["content"] = "  文本\n\n第二段\n"
    assert WritingAgentResult.model_validate(body).result.content == body["result"]["content"]
    body["result"]["scene_execution"][0]["next_state"] = "C16_COMPLETED"
    with pytest.raises(ValidationError):
        WritingAgentResult.model_validate(body)


def test_natural_prose_module_contains_substantive_nonmechanical_guidance():
    from novel_os.prompts.tasks import ref

    module = PromptRegistry().resolve(ref("natural-prose"))
    content = module.content
    for concern in (
        "Over Explanation",
        "Emotion Labeling",
        "Uniform Rhythm",
        "Template Transition",
        "Dialogue Functionalization",
        "Character Voice Collapse",
        "Excessive Closure",
        "Over-signposting",
    ):
        assert concern in content
    assert "flexible editorial guidance" in content
    assert "never sentence-length formulas" in content
    assert "Do not create artificial errors" in content
    assert "Do not optimize for evading an AI detector" in content
