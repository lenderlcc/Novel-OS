"""Revision claims reach independent review as bounded, exact-version evidence."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novel_os.agents.provider import MockModelProvider
from novel_os.context.engine import ContextEngine
from novel_os.context.profiles import ContextProfileRegistry
from novel_os.domain.agents import AgentId, Capability
from novel_os.domain.context import CandidateBatch, ContextRequest, ContextStatus
from novel_os.domain.core import now
from novel_os.domain.enums import Authority
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import ModuleRef, canonical
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.runtime import PromptRuntime
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.quality.policy import indexed_paragraphs, validate_pass
from novel_os.quality.schemas import QualityIssue
from novel_os.repositories.revision import RevisionRepository
from novel_os.services.revision_context import RevisionContextReader
from tests.test_quality_contracts import issue, output, package
from tests.test_quality_dialogue_acceptance import narrative


@pytest.fixture
def outcome(monkeypatch):
    request = ContextRequest(
        project_id=uuid4(),
        chapter_id=uuid4(),
        workflow_id=uuid4(),
        task_id=uuid4(),
        task_type="REVIEW_CHAPTER_NARRATIVE",
        target_version=2,
    )
    revision = SimpleNamespace(
        id=uuid4(),
        project_id=request.project_id,
        chapter_id=request.chapter_id,
        contract={
            "fidelity_version": 1,
            "revision_source": "HUMAN_FEEDBACK",
            "raw_feedback": "合并重复解释，以明确行动结束。不要为了字数补写。",
            "clarifications": ["保留争执。"],
            "interpretation": {"requested_changes": [{"description": "合并解释"}]},
        },
    )
    plan = SimpleNamespace(
        id=uuid4(),
        body={
            "revision_targets": [{"issue_id": "feedback:0", "direction": "合并解释"}],
            "revision_zones": [{"semantic_range": "争执之后"}],
        },
    )
    result = SimpleNamespace(
        id=uuid4(),
        chapter_version_id=uuid4(),
        created_at=now(),
        body={
            "accepted": True,
            "fidelity": {"verdict": "PASS"},
            "declared_changes": ["已合并"],
            "addressed_issue_ids": ["feedback:0"],
            "unresolved_issue_ids": [],
        },
    )
    source = SimpleNamespace(id=uuid4(), content="“你为什么不说？”\n\n“我还没有查清。”")
    calls = []

    def read(self, *args):
        calls.append(args)
        return revision, plan, result, source

    monkeypatch.setattr(RevisionRepository, "review_evidence", read)
    selector = next(
        s
        for s in ContextProfileRegistry().for_task(request.task_type).selectors
        if s.selector_id == "review-revision-outcome"
    )
    return request, revision, plan, result, source, calls, selector


def test_exact_frozen_targets_and_source_are_diagnostic_not_authority(outcome):
    request, revision, plan, result, source, calls, selector = outcome
    items, pointers = RevisionContextReader(None).query(request, selector)
    assert calls == [(request.project_id, request.chapter_id, request.workflow_id, 2)]
    item = items[0]
    body = item.structured_payload
    assert item.source_id == result.id and item.authority_level == Authority.A7_AI_INFERENCE
    assert pointers == {"revision_result_id": str(result.id)}
    assert body["raw_feedback"] == revision.contract["raw_feedback"]
    assert body["interpretation"] == revision.contract["interpretation"]
    assert body["revision_targets"] == plan.body["revision_targets"]
    assert body["source_paragraphs"] == indexed_paragraphs(source.content)
    assert body["chapter_version_id"] == str(result.chapter_version_id)
    assert body["assessment_status"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert body["role"] == "DIAGNOSIS_ONLY"


def test_no_target_version_never_reads_latest_revision(outcome):
    request, _, _, _, _, calls, selector = outcome
    assert RevisionContextReader(None).query(replace(request, target_version=None), selector) == (
        (),
        {"revision_result_id": None},
    )
    assert not calls


def test_absent_revision_and_legacy_contract_do_not_block_review(outcome, monkeypatch):
    request, revision, _, result, _, _, selector = outcome
    revision.contract.pop("fidelity_version")
    result.body.pop("fidelity")
    assert RevisionContextReader(None).query(request, selector) == (
        (),
        {"revision_result_id": None},
    )
    monkeypatch.setattr(RevisionRepository, "review_evidence", lambda *args: None)
    assert RevisionContextReader(None).query(request, selector) == (
        (),
        {"revision_result_id": None},
    )


@pytest.mark.parametrize("corruption", ["rejected", "fidelity_fail"])
def test_new_revision_evidence_requires_accepted_successor(outcome, corruption):
    request, _, _, result, _, _, selector = outcome
    if corruption == "rejected":
        result.body["accepted"] = False
    else:
        result.body["fidelity"]["verdict"] = "FAIL"
    with pytest.raises(DomainError) as error:
        RevisionContextReader(None).query(request, selector)
    assert error.value.code == "CONTEXT_MISSING"


def test_review_outcome_budget_keeps_complete_input_or_blocks(outcome):
    request, _, _, _, _, _, selector = outcome
    evidence = RevisionContextReader(None).query(request, selector)[0][0]
    profile = (
        ContextProfileRegistry()
        .for_task(request.task_type)
        .model_copy(
            update={
                "selectors": (selector,),
                "token_budget": 100000,
            }
        )
    )
    batch = CandidateBatch((evidence,))
    engine = ContextEngine()
    ready = engine.build(request, profile, batch, prompt_overhead=200, output_reservation=300)
    assert ready.status == ContextStatus.READY and ready.package.items[0] == evidence
    huge = replace(
        evidence,
        payload_json=canonical(
            {
                **evidence.structured_payload,
                "source_paragraphs": indexed_paragraphs("完整证据" * 100000),
            }
        ),
    )
    blocked = engine.build(
        request, profile, CandidateBatch((huge,)), prompt_overhead=200, output_reservation=300
    )
    assert blocked.status == ContextStatus.BLOCKED
    assert blocked.error_code == "CONTEXT_BUDGET_EXCEEDED"
    assert blocked.package.items == (huge,) and not blocked.package.excluded_items
    assert blocked.package.items[0].payload_json == huge.payload_json


def test_current_review_uses_new_prompt_without_changing_historical_pin():
    registry = PromptRegistry()
    old = registry.resolve(ModuleRef(module_id="review-chapter-narrative", version=4))
    assert (
        old.module.content_hash
        == "43444652b071ca942dff9077f19f0a5b10b6a738d717735ae40182e46c76088e"
    )
    current = PromptRuntime(MockModelProvider()).prepare(
        task_id=uuid4(),
        task_type="REVIEW_CHAPTER_NARRATIVE",
        agent_id=AgentId.A05_REVIEW,
        attempt=1,
        target_ref=uuid4(),
        output_kind="chapter_narrative_review",
        capabilities={Capability.REVIEW},
        constraints=(),
        context_payload={},
    )
    assert (
        next(
            m.module.version
            for m in current.prompt.modules
            if m.module.module_id == "review-chapter-narrative"
        )
        == 6
    )
    assert (
        current.prompt.output
        == TaskDefinitionRegistry().get("REVIEW_CHAPTER_NARRATIVE").output_schema
    )
    assert ContextProfileRegistry().resolve("CP-006", 4).version == 4
    prior = registry.resolve(ModuleRef(module_id="review-chapter-narrative", version=5))
    assert prior.module.content_hash == (
        "338ddd9801af675d9cf3f313d0fc92a52536033c7f696ffb4670f48dfb0f24c4"
    )


def test_unfinished_prose_goal_reuses_p2_issue_without_forced_retry(outcome):
    request, _, _, _, _, _, selector = outcome
    diagnostic = RevisionContextReader(None).query(request, selector)[0][0]
    ref = {
        "source_type": "EXTENSION",
        "source_id": diagnostic.source_id,
        "source_version": 1,
        "field": "raw_feedback",
    }
    data = issue("OVER_STRUCTURED_DIALOGUE")
    data["source_refs"] = [ref]
    review = narrative([QualityIssue(**data)], source_refs=[ref])
    validate_pass(review, package(review, (diagnostic,)))
    assert review.narrative_verdict == "PASS_WITH_WARNINGS"
    assert review.quality_issues[0].severity == "P2"
    assert not review.quality_issues[0].requires_revision
    data = issue("MISSING_MUST")
    data["source_refs"] = [ref]
    hard = output([QualityIssue(**data)], compliance=True, source_refs=[ref])
    with pytest.raises(ValueError, match="Hard constraint requires"):
        validate_pass(hard, package(hard, (diagnostic,)))
