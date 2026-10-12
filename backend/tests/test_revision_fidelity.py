from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novel_os.revision.fidelity import RevisionFidelityValidator, preservation_ids
from novel_os.revision.fidelity_schemas import FidelityRevisionPlan, RevisionFidelityOutput
from novel_os.revision.mock import fidelity_output, locality_fields
from novel_os.revision.policy import validate_result
from novel_os.revision.schemas import RevisionResultOutput

pytest_plugins = ["tests.test_revision_contracts"]


@pytest.fixture
def fidelity_outputs(revision_outputs):
    request, package, plan, body, result = deepcopy(revision_outputs)
    source = "她把旧伞放在柜台边。\n\n他答应陪她到码头，却没有催她。\n\n她握住伞柄，终于点头。"
    package.items[-1].structured_payload["content"] = source
    body.update(locality_fields(body, request.contract, source))
    plan.body = body
    package.items[1].structured_payload = {**body, "revision_plan_id": str(plan.id)}
    result["content"] = (
        "她把旧伞放在柜台边。\n\n“你不走？”她问。他把门推开，等着她。\n\n她握住伞柄，终于点头。"
    )
    from novel_os.prompts.contracts import digest

    candidate = SimpleNamespace(
        id=uuid4(), body={**result, "content_hash": digest(result["content"])}
    )
    package.items.append(
        SimpleNamespace(
            selector_id="revision-candidate",
            source_id=candidate.id,
            structured_payload={**candidate.body, "candidate_id": str(candidate.id)},
            source_version=1,
            source_type="EXTENSION",
        )
    )
    common = {
        k: result[k]
        for k in ["source_chapter_version_id", "source_review_id", "source_refs", "confidence"]
    }
    common["kind"] = "revision_fidelity"
    output = fidelity_output(common, {i.selector_id: i for i in package.items}, "SUCCESS")
    return request, package, plan, candidate, body, output


def test_locality_defaults_and_three_preservation_lists(fidelity_outputs):
    request, package, _, _, body, _ = fidelity_outputs
    body.pop("change_budget")
    body.pop("allowed_structural_change")
    plan = RevisionFidelityValidator.plan(
        FidelityRevisionPlan.model_validate(body),
        request,
        package.items[-2].structured_payload["content"],
    )
    assert plan.change_budget == "MINIMAL" and plan.allowed_structural_change == "LOCAL"
    assert (
        plan.preserve_scene_elements
        and plan.preserve_relationship_elements
        and plan.preserve_effective_details
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "no_zones",
        "unknown_zone_issue",
        "missing_strength",
        "duplicate_element",
        "invented_quote",
        "outside_paragraph",
        "chapter_wide_no_reason",
        "broad_without_authority",
        "full_pass_without_authority",
        "invented_review_root_cause",
    ],
)
def test_invalid_revision_plan_rejected(fidelity_outputs, mutation):
    request, package, _, _, body, _ = fidelity_outputs
    if mutation == "no_zones":
        body["revision_zones"] = []
    elif mutation == "unknown_zone_issue":
        body["revision_zones"][0]["issue_ids"] = [str(uuid4())]
    elif mutation == "missing_strength":
        body["strength_preservation"] = []
    elif mutation == "duplicate_element":
        body["preserve_scene_elements"][0]["element_id"] = "detail:0"
    elif mutation == "invented_quote":
        body["preserve_scene_elements"][0]["evidence"][0]["excerpt"] = "原稿中不存在的句子"
    elif mutation == "outside_paragraph":
        body["revision_zones"][0].update(paragraph_start=1, paragraph_end=99)
    elif mutation == "chapter_wide_no_reason":
        body["allowed_structural_change"] = "CHAPTER_WIDE"
    elif mutation == "broad_without_authority":
        body["change_budget"] = "BROAD"
    elif mutation == "full_pass_without_authority":
        body["scope"] = "FULL_PASS"
    else:
        body.update(
            allowed_structural_change="CHAPTER_WIDE",
            structural_authorization=dict(
                issue_id=body["target_issue_ids"][0],
                review_root_cause="伪造全章问题",
                reason="重新写",
                why_local_insufficient="我想改",
            ),
        )
    with pytest.raises(ValueError):
        RevisionFidelityValidator.plan(
            FidelityRevisionPlan.model_validate(body),
            request,
            package.items[-2].structured_payload["content"],
        )


def test_source_story_can_survive_substantial_local_dialogue_rewrite(fidelity_outputs):
    request, package, plan, candidate, _, output = fidelity_outputs
    RevisionFidelityValidator.semantic(
        RevisionFidelityOutput.model_validate(output), request, plan, candidate, package
    )
    assert package.items[-2].structured_payload["content"] != candidate.body["content"]
    assert output["verdict"] == "PASS"


@pytest.mark.parametrize(
    "check,code",
    [
        ("SCENE_PREMISE", "UNAUTHORIZED_SCENE_REPLACEMENT"),
        ("scene:0", "UNAUTHORIZED_SCENE_REPLACEMENT"),
        ("RELATIONSHIP_FUNCTION", "REVISION_STRENGTH_REGRESSION"),
        ("strength:0", "REVISION_STRENGTH_REGRESSION"),
        ("UNAFFECTED_MATERIAL", "REVISION_SCOPE_VIOLATION"),
        ("STRUCTURAL_SCOPE", "REVISION_SCOPE_VIOLATION"),
    ],
)
def test_semantic_violations_are_internal_failure_not_quality_taxonomy(
    fidelity_outputs, check, code
):
    request, package, plan, candidate, _, output = fidelity_outputs
    output["verdict"] = "FAIL"
    next(c for c in output["checks"] if c["check_id"] == check)["preserved"] = False
    output["violations"] = [
        dict(code=code, check_ids=[check], description="无必要替换或破坏原稿功能")
    ]
    parsed = RevisionFidelityOutput.model_validate(output)
    RevisionFidelityValidator.semantic(parsed, request, plan, candidate, package)
    assert parsed.verdict == "FAIL"


@pytest.mark.parametrize(
    "mutation",
    [
        "fake_pass",
        "missing_check",
        "unknown_check",
        "missing_violation",
        "false_violation",
        "wrong_source",
        "wrong_candidate",
        "wrong_hash",
        "wrong_plan",
        "fabricated_source_evidence",
        "fabricated_revised_evidence",
        "empty_preserved_evidence",
    ],
)
def test_semantic_forgery_and_cross_field_contradictions_rejected(fidelity_outputs, mutation):
    request, package, plan, candidate, _, output = fidelity_outputs
    if mutation == "fake_pass":
        output["checks"][0]["preserved"] = False
    elif mutation == "missing_check":
        output["checks"] = [c for c in output["checks"] if c["check_id"] != "strength:0"]
    elif mutation == "unknown_check":
        output["checks"].append({**output["checks"][0], "check_id": "fabricated"})
    elif mutation == "missing_violation":
        output["verdict"] = "FAIL"
        output["checks"][0]["preserved"] = False
    elif mutation == "false_violation":
        output["violations"] = [
            dict(
                code="REVISION_SCOPE_VIOLATION",
                check_ids=["SCENE_PREMISE"],
                description="但全部通过",
            )
        ]
    elif mutation == "wrong_source":
        output["source_chapter_version_id"] = str(uuid4())
    elif mutation == "wrong_candidate":
        output["candidate_id"] = str(uuid4())
    elif mutation == "wrong_hash":
        output["candidate_content_hash"] = "0" * 64
    elif mutation == "wrong_plan":
        output["revision_plan_id"] = str(uuid4())
    elif mutation == "fabricated_source_evidence":
        output["checks"][0]["source_evidence"][0]["excerpt"] = "不存在的场景"
    elif mutation == "fabricated_revised_evidence":
        output["checks"][0]["revised_evidence"][0]["excerpt"] = "不存在的场景"
    else:
        output["checks"][0]["revised_evidence"] = []
    with pytest.raises(ValueError):
        RevisionFidelityValidator.semantic(
            RevisionFidelityOutput.model_validate(output), request, plan, candidate, package
        )


def test_authorized_whole_chapter_change_has_real_review_root_cause(fidelity_outputs):
    request, package, plan, candidate, body, output = fidelity_outputs
    issue_id = body["target_issue_ids"][0]
    request.contract["target_issues"][issue_id]["description"] = (
        "全章均使用不符合已批准视角的叙述人称"
    )
    body.update(
        allowed_structural_change="CHAPTER_WIDE",
        change_budget="BROAD",
        scope="FULL_PASS",
        structural_authorization=dict(
            issue_id=issue_id,
            review_root_cause=request.contract["target_issues"][issue_id]["description"],
            reason="全章纠正叙述视角",
            why_local_insufficient="每段叙述视角都有同一问题，仍保留场景和关系",
        ),
    )
    RevisionFidelityValidator.semantic(
        RevisionFidelityOutput.model_validate(output), request, plan, candidate, package
    )


def test_unresolved_abstract_stakes_does_not_force_regeneration(fidelity_outputs):
    request, package, plan, candidate, _, output = fidelity_outputs
    issue = next(iter(request.contract["target_issues"]))
    request.contract["target_issues"][issue]["code"] = "ABSTRACT_STAKES"
    result = {k: v for k, v in candidate.body.items() if k != "content_hash"}
    result.update(
        addressed_issue_ids=[],
        unresolved_issue_ids=[issue],
        blocked_reasons=[
            dict(
                issue_id=issue,
                reason="Insufficient authorized context for stronger concretization.",
            )
        ],
    )
    validate_result(RevisionResultOutput.model_validate(result), request, plan, package)
    assert output["verdict"] == "PASS"  # Independent fidelity is separate from issue clearance.


def test_every_strength_has_an_independent_check(fidelity_outputs):
    _, _, _, _, body, output = fidelity_outputs
    assert "strength:0" in preservation_ids(FidelityRevisionPlan.model_validate(body))
    assert {c["check_id"] for c in output["checks"]} == preservation_ids(
        FidelityRevisionPlan.model_validate(body)
    )


def test_case04_local_dialogue_pass_does_not_require_text_identity(fidelity_outputs):
    from pathlib import Path

    from novel_os.prompts.contracts import digest
    from novel_os.revision.mock import excerpt

    request, package, plan, candidate, body, output = fidelity_outputs
    folder = Path(__file__).resolve().parents[2] / "evals/revision/010a/case-04"
    source = (folder / "source.txt").read_text()
    revised = (folder / "local-edit-fixture.txt").read_text()
    package.items[-2].structured_payload["content"] = source
    body.update(locality_fields(body, request.contract, source))
    candidate.body["content"] = revised
    candidate.body["content_hash"] = digest(revised)
    package.items[-1].structured_payload = {**candidate.body, "candidate_id": str(candidate.id)}
    output["candidate_content_hash"] = digest(revised)
    for check in output["checks"]:
        check["source_evidence"] = [excerpt(source)]
        check["revised_evidence"] = [excerpt(revised)]
    RevisionFidelityValidator.semantic(
        RevisionFidelityOutput.model_validate(output), request, plan, candidate, package
    )
    assert source != revised
    assert "先干活，措辞待会儿确认。" in revised
    assert source.split("一道风卷过院墙")[0] == revised.split("一道风卷过院墙")[0]
    assert source.split("又一滴雨打在篷布上")[1] == revised.split("又一滴雨打在篷布上")[1]
