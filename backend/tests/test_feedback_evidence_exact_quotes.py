import json
import shutil
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.agents.runtime import AgentRuntime
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.agents import AgentId, AgentTask, Capability
from novel_os.domain.context import ContextPackage, ContextRequest, ContextStatus
from novel_os.domain.workflow import ChapterState
from novel_os.feedback.policy import validate_interpretation
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.providers.base import ModelRequest
from tests.prompt_test_support import edit_manifest


@pytest.fixture
def feedback_task():
    return AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=ChapterState.C13_USER_FEEDBACK_DIAGNOSIS,
        workflow_state_version=1,
        agent_id=AgentId.A02_REQUIREMENT,
        task_type="INTERPRET_CHAPTER_FEEDBACK",
        objective="调整对白，保留场景。",
        target_ref=uuid4(),
        capabilities=[Capability.REPORT_RESULT],
        expected_output_schema="chapter-feedback-result.v1",
        attempt_count=1,
    )


def feedback_context(task, version):
    if version is None:
        return None
    profile = ContextProfileRegistry().resolve("CP-008", version)
    request = ContextRequest(
        project_id=task.project_id,
        task_id=task.task_id,
        task_type=task.task_type,
        chapter_id=task.target_ref,
        workflow_id=task.workflow_instance_id,
        workflow_state_version=task.workflow_state_version,
        attempt_number=task.attempt_count,
    )
    # Sealed compilation fixture only: retrieval completeness belongs to ContextEngine tests.
    return ContextSerializer.seal(
        ContextPackage(
            project_id=task.project_id,
            task_id=task.task_id,
            workflow_id=task.workflow_instance_id,
            request=request,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_hash=profile.profile_hash,
            profile_json=profile.model_dump_json(),
            build_status=ContextStatus.READY,
            items=(),
            excluded_items=(),
            missing_required_items=(),
            authority_conflicts=(),
            source_snapshots=(),
            token_budget=profile.token_budget,
            prompt_overhead=0,
            output_reservation=0,
            estimated_tokens=0,
            future_knowledge_policy=profile.future_knowledge_policy,
            package_hash="",
        )
    )


@pytest.mark.parametrize("context_version", [1, 2, None])
def test_default_feedback_prepare_compiles_exact_quote_rule(feedback_task, context_version):
    prepared = AgentRuntime(MockModelProvider()).prepare(
        feedback_task, feedback_context(feedback_task, context_version)
    )
    assert isinstance(prepared, ModelRequest)
    template = next(m for m in prepared.prompt.modules if m.module.module_type == "TASK_TEMPLATE")
    assert template.module.version == 4
    text = next(m.content for m in prepared.prompt.messages if m.layer == "TASK_TEMPLATE")
    assert "literal contiguous substring" in text
    assert "Do not add presentation quotation marks" in text


@pytest.fixture
def future_feedback_registry(tmp_path):
    library = tmp_path / "prompts"
    shutil.copytree(PromptRegistry().root, library)
    templates = library / "task_template" / "interpret-chapter-feedback"
    shutil.copytree(templates / "v4", templates / "v5")
    edit_manifest(templates / "v5" / "manifest.json", version=5, status="STABLE")
    return PromptRegistry(library)


@pytest.mark.parametrize("context_version", [1, 2, None])
def test_default_feedback_prepare_uses_configured_stable_template(
    feedback_task, context_version, future_feedback_registry
):
    prepared = AgentRuntime(MockModelProvider(), prompts=future_feedback_registry).prepare(
        feedback_task, feedback_context(feedback_task, context_version)
    )
    assert isinstance(prepared, ModelRequest)
    template = next(m for m in prepared.prompt.modules if m.module.module_type == "TASK_TEMPLATE")
    assert (
        template.module.pin()
        == future_feedback_registry.resolve(
            ModuleRef(module_id="interpret-chapter-feedback")
        ).module.pin()
    )
    assert template.module.version == 5


@pytest.mark.parametrize("historical_version", [2, 3])
def test_explicit_feedback_template_pin_survives_new_stable_version(
    feedback_task, historical_version, future_feedback_registry, monkeypatch
):
    tasks = TaskDefinitionRegistry()
    definition = replace(
        tasks.get(feedback_task.task_type),
        task_template=ModuleRef(module_id="interpret-chapter-feedback", version=historical_version),
    )
    monkeypatch.setattr(tasks, "get", lambda *args: definition)
    prepared = AgentRuntime(
        MockModelProvider(), tasks=tasks, prompts=future_feedback_registry
    ).prepare(feedback_task, feedback_context(feedback_task, 2))
    assert isinstance(prepared, ModelRequest)
    template = next(m for m in prepared.prompt.modules if m.module.module_type == "TASK_TEMPLATE")
    assert (
        template.module.pin()
        == future_feedback_registry.resolve(definition.task_template).module.pin()
    )
    assert template.module.version == historical_version


def feedback_output(feedback, quote):
    body = {
        "task_id": str(uuid4()),
        "status": "SUCCESS",
        "result": {
            "kind": "human_feedback_interpretation",
            "feedback_id": str(feedback.id),
            "source_chapter_version_id": str(feedback.source_chapter_version_id),
            "intent_summary": "只调整对白表达。",
            "requested_changes": [{"description": "调整对白。", "target_regions": ["对白"]}],
            "preserve_requests": [],
            "do_not_change": [],
            "target_regions": ["对白"],
            "quality_concerns": [],
            "scope": "LOCAL",
            "safe_inferences": [],
            "ambiguities": [],
            "conflicts": [],
            "change_impact": "PROSE_ONLY",
            "action": "REVISION",
            "user_message": "将按原场景调整对白。",
            "decision_question": None,
            "feedback_evidence": [quote],
            "supporting_review_issue_ids": [],
            "source_refs": [
                {
                    "source_type": "EXTENSION",
                    "source_id": str(feedback.id),
                    "source_version": 1,
                    "field": "raw_feedback",
                }
            ],
            "confidence": 0.9,
        },
        "confidence": 0.9,
        "assumptions": [],
        "issues": [],
        "proposed_changes": [],
        "memory_proposals": [],
        "escalation": None,
    }
    raw_output = json.dumps(body, ensure_ascii=False)
    contract = TaskDefinitionRegistry().get("INTERPRET_CHAPTER_FEEDBACK").output_schema
    return raw_output, contract.parse(raw_output).result


@pytest.mark.parametrize(
    ("raw", "quote", "accepted"),
    [
        ("中间对白自然一些，开头保持不变。", "中间对白自然一些", True),
        ("中间对白自然一些，开头保持不变。", "“中间对白自然一些”", False),
        ("中间对白自然一些，开头保持不变。", '"中间对白自然一些"', False),
        ("请保留“开头”，只调整对白。", "“开头”", True),
        ("中间对白自然一些，开头保持不变。", "对白更自然", False),
    ],
)
def test_feedback_evidence_preserves_user_characters(raw, quote, accepted):
    feedback_id, draft_id = uuid4(), uuid4()
    feedback = SimpleNamespace(id=feedback_id, source_chapter_version_id=draft_id, raw_feedback=raw)
    raw_output, output = feedback_output(feedback, quote)
    original_result = output.model_dump(mode="json")
    package = SimpleNamespace(
        items=[
            SimpleNamespace(
                selector_id="human-feedback",
                source_type="EXTENSION",
                source_id=feedback_id,
                source_version=1,
                structured_payload={},
            )
        ]
    )
    if accepted:
        validate_interpretation(output, feedback, package, None)
    else:
        with pytest.raises(ValueError, match="quote the user's actual words"):
            validate_interpretation(output, feedback, package, None)
    assert output.feedback_evidence == [quote]
    assert output.model_dump(mode="json") == original_result
    assert json.loads(raw_output)["result"] == original_result


def test_clarification_evidence_quotes_user_answer_not_ai_question():
    feedback_id, draft_id = uuid4(), uuid4()
    feedback = SimpleNamespace(
        id=feedback_id, source_chapter_version_id=draft_id, raw_feedback="是"
    )
    _, output = feedback_output(feedback, "只调整写法")
    item = SimpleNamespace(
        selector_id="human-feedback",
        source_type="EXTENSION",
        source_id=feedback_id,
        source_version=1,
        structured_payload={
            "clarifications": [
                {"raw_feedback": "只调整写法", "decision_question": "保留所有场景？"}
            ]
        },
    )
    validate_interpretation(output, feedback, SimpleNamespace(items=[item]), None)
    _, output = feedback_output(feedback, "保留所有场景？")
    with pytest.raises(ValueError, match="quote the user's actual words"):
        validate_interpretation(output, feedback, SimpleNamespace(items=[item]), None)
