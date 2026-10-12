"""Offline output and historical prompt contracts, not character quality evaluations."""

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.characters.interpretation import CharacterProfileAgentResult


class ProfileProvider(MockModelProvider):
    def __init__(self, transform=None):
        super().__init__()
        self.requests = []
        self.transform = transform

    def generate(self, request):
        self.requests.append(request)
        response = super().generate(request)
        body = json.loads(response.content)
        body["result"]["profile"]["communication_style"] = "Direct, but avoids naming fear"
        if self.transform:
            self.transform(body)
        return replace(response, content=json.dumps(body))


def test_a02_profile_report_uses_shared_runtime_and_user_input_only():
    provider = ProfileProvider()
    execution = AgentRuntime(provider).execute_report(
        "INTERPRET_CHARACTER_PROFILE", "Direct, but avoids naming fear"
    )
    assert execution.error_code is None
    assert execution.result.result.profile.communication_style == "Direct, but avoids naming fear"
    assert execution.result.result.profile.decision_tendency is None
    assert execution.result.result.profile.relationship_modifiers == []
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.output_kind == "character_profile_draft"
    assert request.context_package.profile_id == "CP-010"
    assert [item.source_type for item in request.context_package.items] == ["TASK_INPUT"]
    assert (
        json.loads(request.prompt.output.schema_json)
        == CharacterProfileAgentResult.model_json_schema()
    )
    assert (
        "APPROVE"
        not in json.loads(
            next(m.content for m in request.prompt.messages if m.layer == "AUTHORITY_CONSTRAINTS")
        )["authority"]["capabilities"]
    )


@pytest.mark.parametrize("field", ["proposed_changes", "memory_proposals"])
def test_a02_nonempty_mutation_output_fails_contract_before_persistence(field):
    provider = ProfileProvider(
        lambda body: body.update({field: [{"capability": "APPROVE", "target_ref": str(uuid4())}]})
    )
    execution = AgentRuntime(provider).execute_report("INTERPRET_CHARACTER_PROFILE", "Direct")
    assert execution.error_code == "SCHEMA_PARSE_ERROR"
    assert execution.result is None
    assert len(provider.requests) == 1


@pytest.mark.parametrize("field", ["status", "authority_level", "approved_at", "version"])
def test_a02_cannot_return_server_fields_inside_profile(field):
    provider = ProfileProvider(lambda body: body["result"]["profile"].update({field: "fake"}))
    execution = AgentRuntime(provider).execute_report("INTERPRET_CHARACTER_PROFILE", "Direct")
    assert execution.error_code == "SCHEMA_PARSE_ERROR"


def test_a02_report_entry_cannot_execute_writer_or_approve():
    provider = ProfileProvider()
    execution = AgentRuntime(provider).execute_report("WRITE_CHAPTER", "Write prose")
    assert execution.error_code == "AUTHORITY_DENIED"
    assert provider.requests == []


@pytest.mark.parametrize(
    "task,profile,old_context,new_context,old_prompt,new_prompt",
    [
        ("PLAN_CHAPTER", "CP-004", 6, 8, 6, 8),
        ("PLAN_CHAPTER", "CP-004", 7, 9, 7, 9),
        ("EXPLORE_CHAPTER_CONCEPTS", "CP-004E", 1, 2, 1, 2),
        ("REVIEW_CHAPTER_PLAN", "CP-004R", 3, 4, 4, 5),
        ("WRITE_CHAPTER", "CP-005", 6, 7, 4, 5),
        ("REVIEW_CHAPTER_COMPLIANCE", "CP-006", 3, 4, 1, 2),
        ("REVIEW_CHAPTER_NARRATIVE", "CP-006", 3, 4, 2, 3),
        ("PLAN_CHAPTER_REVISION", "CP-007", 7, 8, 6, 8),
        ("REVISE_CHAPTER", "CP-007", 7, 8, 7, 8),
        ("INTERPRET_CHAPTER_FEEDBACK", "CP-008", 1, 2, 4, 4),
    ],
)
def test_character_integration_selects_new_prompts_without_rewriting_historical_pins(
    task, profile, old_context, new_context, old_prompt, new_prompt
):
    runtime = AgentRuntime(MockModelProvider())
    previous_schemas = {
        "PLAN_CHAPTER": "chapter-planning-result.v2",
        "REVIEW_CHAPTER_PLAN": "chapter-plan-review-result.v2",
        "WRITE_CHAPTER": "chapter-writing-result.v1",
        "REVIEW_CHAPTER_COMPLIANCE": "chapter-compliance-review.v1",
        "REVIEW_CHAPTER_NARRATIVE": "chapter-narrative-review.v2",
    }
    schema = previous_schemas.get(task)
    definition = runtime.prompts.tasks.get(task, schema)
    for context, expected in [(old_context, old_prompt), (new_context, new_prompt)]:
        request = runtime.prompts.prepare(
            task_id=uuid4(),
            task_type=task,
            agent_id=definition.agent_id,
            attempt=1,
            target_ref=uuid4(),
            output_kind="contract-probe",
            capabilities=definition.capabilities,
            constraints=[],
            expected_output_schema=schema,
            context_payload={"profile": {"id": profile, "version": context}},
        )
        template = next(
            m.module for m in request.prompt.modules if m.module.module_type == "TASK_TEMPLATE"
        )
        assert template.version == expected
