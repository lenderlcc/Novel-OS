"""Contract and evidence checks; Mock acceptance is not an LLM quality claim."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from novel_os.agents.authority import AuthorityValidator
from novel_os.agents.provider import MockModelProvider
from novel_os.agents.registry import AgentRegistry
from novel_os.agents.runtime import AgentRuntime, ExecutionResult
from novel_os.domain.agents import AgentId, AgentTask, Capability
from novel_os.domain.context import SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.workflow import ChapterState
from novel_os.prompts.contracts import ModuleRef
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.quality.policy import aggregate, validate_pass
from novel_os.quality.schemas import (
    NarrativeReviewV2,
    QualityIssue,
    read_review,
)
from tests.test_quality_contracts import issue as base_issue
from tests.test_quality_contracts import output, package

ROOT = Path(__file__).resolve().parents[2]
CODES = ("OVER_STRUCTURED_DIALOGUE", "CHARACTERS_AS_ARGUMENTS", "WEAK_CHARACTER_VOICE")


def issue(code, severity=None, **changes):
    data = base_issue(code, severity)
    data.update(changes)
    return data


def narrative(issues=(), **changes):
    body = output(issues).model_dump()
    body.update(audience_evidence=[], **changes)
    return NarrativeReviewV2.model_validate(body)


def audience_case(field="naturalness", expected="HIGH"):
    ref = dict(
        source_type="PROJECT_WRITING_PROFILE", source_id=uuid4(), source_version=7, field=field
    )
    profile = SimpleNamespace(
        selector_id="approved-writing-profile",
        source_type=SourceType.PROJECT_WRITING_PROFILE,
        source_id=ref["source_id"],
        source_version=7,
        status=Status.APPROVED,
        authority_level=Authority.A5_USER_PREFERENCE,
        structured_payload={field: expected},
    )
    root = QualityIssue(**issue("OVER_STRUCTURED_DIALOGUE"))
    audience = QualityIssue(**issue("AUDIENCE_STYLE_MISMATCH", source_refs=[ref]))
    evidence = dict(
        profile_field=field,
        profile_ref=ref,
        expected=expected,
        observed="人物连续完整回答彼此的论点，个人反应被压缩。",
        reason="这与用户明确要求的自然交流体验存在直接冲突。",
    )
    body = output([root, audience], source_refs=[ref]).model_dump()
    body["audience_evidence"] = [evidence]
    return body, profile


@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize(
    "severity,required,verdict",
    [
        ("P1", True, "FAIL"),
        ("P1", False, "PASS_WITH_WARNINGS"),
        ("P2", False, "PASS_WITH_WARNINGS"),
    ],
)
def test_dialogue_character_contract_is_impact_based(code, severity, required, verdict):
    data = issue(code, severity)
    data["requires_revision"] = required
    review = narrative([QualityIssue(**data)])
    validate_pass(review, package(review))
    assert review.narrative_verdict == verdict
    assert review.audience_fit_verdict == "PASS"
    assert review.audience_evidence == []


@pytest.mark.parametrize(
    "content",
    [
        "“为什么？”\n\n“因为有风险。”\n\n“那你想怎样？”\n\n“按原定顺序。”",
        "“我认为你错了。”\n\n“我不同意。”\n\n“先按规程检查。”",
        "“请将材料交给他。”\n\n“何时出发？”\n\n“午后。”",
    ],
)
def test_no_deterministic_dialogue_trigger_or_mandatory_issue(content):
    review = narrative()
    context = package(review)
    context.items[0].structured_payload["content"] = content
    before = review.model_dump()
    validate_pass(review, context)
    assert review.model_dump() == before
    assert review.narrative_verdict == "PASS" and review.quality_issues == []


def test_overlapping_signals_can_remain_one_root_issue():
    data = issue("OVER_STRUCTURED_DIALOGUE")
    data["impact"] = "对话过于高效，也压缩了人物声音与关系的具体性。"
    review = narrative([QualityIssue(**data)])
    validate_pass(review, package(review))
    assert [i.code for i in review.quality_issues] == ["OVER_STRUCTURED_DIALOGUE"]
    assert review.audience_fit_verdict == "PASS"


@pytest.mark.parametrize(
    "field,expected",
    [
        ("naturalness", "HIGH"),
        ("reading_experience", ["低阅读阻力", "自然交流"]),
        ("target_audience", "重视人物互动的读者" * 8),
    ],
)
def test_audience_warning_requires_exact_profile_mismatch(field, expected):
    body, profile = audience_case(field, expected)
    review = NarrativeReviewV2.model_validate(body)
    validate_pass(review, package(review, [profile]))
    assert review.audience_fit_verdict == "PASS_WITH_WARNINGS"
    assert review.audience_evidence[0].expected == expected
    assert review.audience_evidence[0].profile_ref.source_version == 7


def test_narrative_warning_does_not_implicitly_fail_audience_with_profile():
    _, profile = audience_case()
    review = narrative([QualityIssue(**issue("ABSTRACT_STAKES"))])
    validate_pass(review, package(review, [profile]))
    assert review.narrative_verdict == "PASS_WITH_WARNINGS"
    assert review.audience_fit_verdict == "PASS"


@pytest.mark.parametrize(
    "change",
    [
        "missing_evidence",
        "missing_issue",
        "contradictory_pass",
        "missing_top_ref",
        "missing_issue_ref",
        "duplicate_field",
        "wrong_field",
    ],
)
def test_audience_cross_field_contradictions_rejected(change):
    body, _ = audience_case()
    if change == "missing_evidence":
        body["audience_evidence"] = []
    elif change == "missing_issue":
        body["quality_issues"] = body["quality_issues"][:1]
        body["audience_fit_verdict"] = "PASS"
    elif change == "contradictory_pass":
        body["audience_fit_verdict"] = "PASS"
    elif change == "missing_top_ref":
        body["source_refs"] = []
    elif change == "missing_issue_ref":
        body["quality_issues"][-1]["source_refs"] = []
    elif change == "duplicate_field":
        body["audience_evidence"] *= 2
    else:
        body["audience_evidence"][0]["profile_field"] = "reading_experience"
    with pytest.raises(ValidationError):
        NarrativeReviewV2.model_validate(body)


@pytest.mark.parametrize(
    "change",
    [
        "wrong_version",
        "wrong_expected",
        "draft",
        "wrong_authority",
        "not_selected",
        "metadata_field",
        "unspecified",
    ],
)
def test_audience_cannot_fabricate_or_use_unapproved_preferences(change):
    body, profile = audience_case()
    extras = [profile]
    if change == "wrong_version":
        profile.source_version += 1
    elif change == "wrong_expected":
        profile.structured_payload["naturalness"] = "LOW"
    elif change == "draft":
        profile.status = Status.DRAFT
    elif change == "wrong_authority":
        profile.authority_level = Authority.A7_AI_INFERENCE
    elif change == "not_selected":
        extras = []
    elif change == "metadata_field":
        body, profile = audience_case("writing_profile_hash", "hash-is-not-a-preference")
        extras = [profile]
    else:
        body, profile = audience_case("naturalness", "UNSPECIFIED")
        extras = [profile]
    review = NarrativeReviewV2.model_validate(body)
    with pytest.raises(ValueError):
        validate_pass(review, package(review, extras))


def test_aggregate_preserves_evidence_and_strengths_and_reads_v1():
    body, _ = audience_case()
    review = NarrativeReviewV2.model_validate(body)
    compliance = output(compliance=True)
    compliance = compliance.model_copy(
        update={
            "chapter_id": review.chapter_id,
            "chapter_version_id": review.chapter_version_id,
        }
    )
    from novel_os.domain.core import now
    from novel_os.quality.schemas import Strength

    strength = Strength(
        description="保留了用户决定的方向。",
        evidence=review.quality_issues[0].evidence,
        preservation_direction="保留最终选择及此前的真实动摇。",
    )
    compliance = compliance.model_copy(update={"strengths": [strength]})
    record = SimpleNamespace(prompt_lineage_id=uuid4(), context_package_id=uuid4())
    combined = aggregate(compliance, review, record, record, now())
    assert combined.reviewer_version == "A05-quality.v2"
    assert combined.audience_evidence == review.audience_evidence
    assert strength in combined.strengths
    assert read_review(combined.model_dump()) == combined
    assert combined.compliance_verdict == "PASS"
    old = aggregate(compliance, output(), record, record, now())
    assert old.reviewer_version == "A05-quality.v1"
    assert "audience_evidence" not in old.model_dump()
    assert read_review(old.model_dump()) == old


def test_historical_schema_and_prompts_preserved_with_current_v3_prompt():
    registry = TaskDefinitionRegistry()
    old = registry.get("REVIEW_CHAPTER_NARRATIVE", "chapter-narrative-review.v1")
    new = registry.get("REVIEW_CHAPTER_NARRATIVE")
    assert (
        old.output_schema.schema_hash
        == "36cd8adef506e8028f8d93213d8113f9a89052da1152a65bf225e576adc66485"
    )
    assert new.output_schema.version == 3
    prompts = PromptRegistry()
    assert prompts.resolve(old.task_template).module.version == 1
    current = prompts.resolve(new.task_template)
    assert current.module.version == 4
    assert (
        prompts.resolve(
            ModuleRef(module_id="review-chapter-narrative", version=1)
        ).module.content_hash
        == "9bad143fe2c9638d84d9dbf592c90e4cd92dde3c4820ee402930305cd32e13f8"
    )
    assert (
        prompts.resolve(
            ModuleRef(module_id="review-chapter-narrative", version=2)
        ).module.content_hash
        == "b430defd21b2492d6c72fb92b510e767830fe2e4e8b09f2d561c449f0187a869"
    )
    for specific in ("车票", "确认单", "那边怎么办", "之后再说", "Case 05", "Case 04"):
        assert specific not in current.content


@pytest.mark.parametrize("version", [1, 2])
def test_queued_legacy_and_current_task_prepare_exact_contract(version):
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=ChapterState.C09_INTERNAL_REVIEW,
        workflow_state_version=3,
        agent_id=AgentId.A05_REVIEW,
        task_type="REVIEW_CHAPTER_NARRATIVE",
        objective="审阅",
        target_ref=uuid4(),
        capabilities=[Capability.REVIEW],
        expected_output_schema=f"chapter-narrative-review.v{version}",
    )
    runtime = AgentRuntime(MockModelProvider())
    prepared = runtime.prepare(task)
    assert not isinstance(prepared, ExecutionResult), prepared
    assert prepared.prompt.output.version == version
    assert isinstance(
        runtime.prepare(replace(task, expected_output_schema="chapter-narrative-review.v99")),
        ExecutionResult,
    )


@pytest.mark.parametrize("task_type", ["REVIEW_CHAPTER_COMPLIANCE", "MOCK_REVIEW"])
@pytest.mark.parametrize("invalid_schema", [None, "", "unknown.v1"])
def test_tasks_without_legacy_schema_reject_missing_or_unknown_contract(task_type, invalid_schema):
    registry = AgentRegistry()
    definition = registry.task(task_type)
    task = AgentTask(
        project_id=uuid4(),
        workflow_instance_id=uuid4(),
        workflow_state=definition.state,
        workflow_state_version=3,
        agent_id=definition.agent_id,
        task_type=task_type,
        objective="审阅",
        target_ref=uuid4(),
        capabilities=[definition.capability],
        expected_output_schema=definition.result_schema,
    )
    authority = AuthorityValidator(registry)
    assert authority.validate(task) == definition
    with pytest.raises(DomainError, match="Task identity"):
        authority.validate(replace(task, expected_output_schema=invalid_schema))


@pytest.mark.parametrize("case", ["case-04", "case-05"])
def test_acceptance_fixture_pins_real_draft_and_separates_human_themes(case):
    path = ROOT / "evals/quality/009a" / case
    manifest = json.loads((path / "manifest.json").read_text())
    raw = (path / "input.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["input_sha256"]
    inputs = json.loads(raw)
    item = next(i for i in inputs["items"] if i["selector_id"] == "target-version")
    assert item["source_id"] == manifest["chapter_version_id"]
    content = json.loads(item["payload_json"])["content"]
    assert hashlib.sha256(content.encode()).hexdigest() == manifest["draft_sha256"]
    assert "human_expected_themes" not in inputs
    if case == "case-05":
        assert manifest["profile_refs"] == []  # actual latest Project has no Profile
        before = json.loads((path / "before.json").read_text())["reviews"][0]["body"]
        assert read_review(before).compliance_verdict == "PASS"
        assert not any(i["code"] == "MAJOR_DIRECTION_VIOLATION" for i in before["hard_gate_issues"])
        assert before["strengths"]  # preserves actual baseline, no fabricated new AI verdict
