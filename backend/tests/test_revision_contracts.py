from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novel_os.agents.registry import AgentRegistry
from novel_os.domain.agents import AgentId
from novel_os.prompts.registry import PromptRegistry
from novel_os.prompts.tasks import TaskDefinitionRegistry
from novel_os.revision.mock import response
from novel_os.revision.policy import validate_plan, validate_result
from novel_os.revision.schemas import RevisionPlanOutput, RevisionResultOutput


@pytest.fixture
def revision_outputs():
    issue, chapter, source, review, plan_id = (uuid4() for _ in range(5))
    contract = dict(
        source_chapter_version_id=str(source),
        source_review_id=str(review),
        target_issues={
            str(issue): dict(
                code="OVER_EXPLAINED_REASONING",
                severity="P1",
                description="重复说明",
                revision_direction="压缩重复说明",
                evidence=[dict(paragraph_index=1, excerpt="他停下。", reason="动作已说明")],
            )
        },
        preserve_items={"strength:0": "保留人物犹豫", "plan:1": "最终继续原计划"},
        do_not_change={
            "locked:1": dict(authority="A1_USER_LOCKED", value="不改变结尾"),
            "profile:1": dict(authority="A5_USER_PREFERENCE", value="THIRD_PERSON"),
        },
        review_authority="DIAGNOSIS_ONLY",
    )
    item = SimpleNamespace(
        selector_id="revision-contract",
        structured_payload=contract,
        source_type="EXTENSION",
        source_id=uuid4(),
        source_version=1,
    )
    package = SimpleNamespace(items=[item])
    request = SimpleNamespace(
        task_id=uuid4(), target_ref=chapter, output_kind="revision_plan", context_package=package
    )
    body = response(request, "SUCCESS")["result"]
    entity = SimpleNamespace(
        chapter_id=chapter,
        source_chapter_version_id=source,
        source_review_id=review,
        source_feedback_id=None,
        contract=contract,
    )
    plan = SimpleNamespace(id=plan_id, body=body)
    package.items.extend(
        [
            SimpleNamespace(
                selector_id="revision-plan",
                structured_payload={**body, "revision_plan_id": str(plan_id)},
                source_type="EXTENSION",
                source_id=plan_id,
                source_version=1,
            ),
            SimpleNamespace(
                selector_id="target-version",
                structured_payload={"content": "他停下。"},
                source_type="CHAPTER_VERSION",
                source_id=source,
                source_version=1,
            ),
        ]
    )
    request.output_kind = "revision_result"
    result = response(request, "SUCCESS")["result"]
    return entity, package, plan, body, result


def test_valid_plan_and_result(revision_outputs):
    request, package, plan, body, result = revision_outputs
    validate_plan(RevisionPlanOutput.model_validate(body), request, package)
    validate_result(RevisionResultOutput.model_validate(result), request, plan, package)
    assert body["scope"] == "TARGETED"


@pytest.mark.parametrize(
    "field",
    [
        "chapter_id",
        "source_chapter_version_id",
        "source_review_id",
        "target_issue_ids",
        "preserve_items",
        "do_not_change",
        "evidence",
        "priority",
        "source_refs",
    ],
)
def test_plan_rejects_tampered_contract(revision_outputs, field):
    request, package, _, body, _ = revision_outputs
    body = deepcopy(body)
    if field.endswith("_id"):
        body[field] = str(uuid4())
    elif field == "target_issue_ids":
        body[field] = [str(uuid4())]
    elif field in {"preserve_items", "do_not_change"}:
        body[field] = ["review-suggested-new-ending"]
    elif field == "evidence":
        body["revision_targets"][0]["evidence_refs"][0]["excerpt"] = "伪造摘录"
    elif field == "priority":
        body["revision_targets"][0]["priority"] = "P2"
    else:
        body[field][0]["source_id"] = str(uuid4())
    with pytest.raises(ValueError):
        validate_plan(RevisionPlanOutput.model_validate(body), request, package)


@pytest.mark.parametrize(
    "kind",
    [
        "identity",
        "unknown_issue",
        "missing_issue",
        "duplicate_issue",
        "blocked_claimed_fixed",
        "preserve_removed",
        "blocked_but_addressed",
        "no_content_no_reason",
    ],
)
def test_execution_accounts_for_exact_issues_and_preservation(revision_outputs, kind):
    request, package, plan, _, body = revision_outputs
    body = deepcopy(body)
    if kind == "identity":
        body["revision_plan_id"] = str(uuid4())
    elif kind == "unknown_issue":
        body["addressed_issue_ids"] = [str(uuid4())]
    elif kind == "missing_issue":
        body["addressed_issue_ids"] = []
    elif kind == "duplicate_issue":
        body["unresolved_issue_ids"] = body["addressed_issue_ids"]
    elif kind == "blocked_claimed_fixed":
        plan.body["revision_targets"] = []
    elif kind == "preserve_removed":
        body["preserved_items"] = ["strength:0"]
    elif kind == "blocked_but_addressed":
        body["blocked_reasons"] = [dict(issue_id=body["addressed_issue_ids"][0], reason="证据不足")]
    else:
        body["content"] = None
    with pytest.raises(ValueError):
        validate_result(RevisionResultOutput.model_validate(body), request, plan, package)


def test_a06_has_one_owner_and_two_versioned_prompt_tasks():
    definition = AgentRegistry().get(AgentId.A06_REVISION)
    assert definition.agent_id == AgentId.A06_REVISION
    for task_type in ["PLAN_CHAPTER_REVISION", "REVISE_CHAPTER"]:
        task = TaskDefinitionRegistry().get(task_type)
        assert task.agent_id == AgentId.A06_REVISION
        PromptRegistry().resolve(task.agent_role)


def test_do_not_change_ids_are_not_output_keep_ids(revision_outputs):
    request, package, plan, _, result = revision_outputs
    body = deepcopy(result)
    body["preserved_items"].append(next(iter(request.contract["do_not_change"])))
    with pytest.raises(ValueError, match="preserve the source commitments"):
        validate_result(RevisionResultOutput.model_validate(body), request, plan, package)
    validate_result(RevisionResultOutput.model_validate(result), request, plan, package)
