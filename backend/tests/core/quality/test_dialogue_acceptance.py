from dataclasses import replace

import pytest

from novel_os.agents.registry import QUALITY_STAGE_TASKS
from novel_os.quality.policy import paragraphs
from tests.core.quality.conftest import QualityDriver
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.test_quality_dialogue_acceptance import issue


def test_audience_evidence_persists_exact_approved_profile_without_changing_draft(
    core_client, chapter_api, core_database
):
    project = chapter_api.split("/chapters/")[0]
    draft(core_client, project, naturalness="HIGH", reading_experience=["低阅读阻力"])
    approved = approve(core_client, project)
    draft(core_client, project, 1, naturalness="LOW", reading_experience=["DRAFT_ONLY_SECRET"])
    d = QualityDriver(core_client, chapter_api).approve_plan(core_database)
    run_one(core_database, d)
    before = d.client.get(d.chapter_api + "/versions/1").json()
    run_one(core_database, d)

    def result(request, body):
        profile = next(
            i for i in request.context_package.items if i.source_type == "PROJECT_WRITING_PROFILE"
        )
        assert str(profile.source_id) == approved["id"] and profile.source_version == 1
        assert "DRAFT_ONLY_SECRET" not in str(request.context_package)
        target = next(i for i in request.context_package.items if i.selector_id == "target-version")
        quote = paragraphs(target.structured_payload["content"])[0][:100]
        ref = dict(
            source_type="PROJECT_WRITING_PROFILE",
            source_id=str(profile.source_id),
            source_version=1,
            field="naturalness",
        )
        root = issue("OVER_STRUCTURED_DIALOGUE")
        mismatch = issue("AUDIENCE_STYLE_MISMATCH", source_refs=[ref])
        for finding in (root, mismatch):
            finding["evidence"][0]["excerpt"] = quote
        body["result"].update(
            narrative_verdict="PASS_WITH_WARNINGS",
            audience_fit_verdict="PASS_WITH_WARNINGS",
            quality_issues=[root, mismatch],
            source_refs=[ref],
            audience_evidence=[
                dict(
                    profile_field="naturalness",
                    profile_ref=ref,
                    expected="HIGH",
                    observed="离线证据传递测试，不代表模型文学诊断。",
                    reason="验证受众判断绑定批准偏好。",
                )
            ],
        )

    provider = RecordedProvider(result)
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS", d.workflow
    saved = d.reviews()[0]
    assert saved["body"]["reviewer_version"] == "A05-quality.v2"
    assert saved["body"]["audience_fit_verdict"] == "PASS_WITH_WARNINGS"
    evidence = saved["body"]["audience_evidence"][0]
    assert evidence["expected"] == "HIGH"
    assert evidence["profile_ref"]["source_id"] == approved["id"]
    assert saved["binding"]["profile_version"] == 1
    assert saved["body"]["strengths"]  # both Mock passes' evidenced strengths survive
    assert d.client.get(d.chapter_api + "/versions/1").json() == before
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    assert not any(t["agent_id"] == "A06_REVISION" for t in d.read("/agent-tasks"))


def test_pending_v1_review_finishes_and_remains_readable_after_v2_rollout(
    quality_driver, core_database, monkeypatch
):
    d = quality_driver
    run_one(core_database, d)
    current = QUALITY_STAGE_TASKS["REVIEW_CHAPTER_NARRATIVE"]
    with monkeypatch.context() as old_scheduler:
        old_scheduler.setitem(
            QUALITY_STAGE_TASKS,
            "REVIEW_CHAPTER_NARRATIVE",
            replace(current, result_schema="chapter-narrative-review.v1"),
        )
        run_one(core_database, d)
    pending = next(
        t for t in d.read("/agent-tasks") if t["task_type"] == "REVIEW_CHAPTER_NARRATIVE"
    )
    assert pending["expected_output_schema"] == "chapter-narrative-review.v1"
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C11_INTERNAL_PASS", d.workflow
    report = d.reviews()[0]
    assert report["body"]["reviewer_version"] == "A05-quality.v1"
    assert "audience_evidence" not in report["body"]
    assert report["body"]["overall_verdict"] == "PASS"
    completed = next(t for t in d.read("/agent-tasks") if t["task_id"] == pending["task_id"])
    assert completed["status"] == "SUCCEEDED"
    assert completed["attempt_count"] == 1


@pytest.mark.parametrize("case", ["local_repetition", "broken_choice", "effective_exchange"])
def test_recorded_prose_effects_keep_impact_and_strengths_without_auto_revision(
    quality_driver, core_database, case
):
    """Recorded judgments exercise evidence/routing, not live literary skill."""
    d = quality_driver
    opening = [
        "林舟把信压在桌角。",
        "“你把我的信拆了？”",
        "“你先看看封口。”阿岚把灯移近。",
    ]
    if case == "local_repetition":
        parts = opening + [
            "封口仍在，信没有被拆过。",
            "林舟翻过信。封口完好，所以她确实没拆。",
            "阿岚展开旧地图：“走这边，要多半天。”",
            "“我等得起。”林舟把信收进袖口。",
        ]
        code, severity, required = "OVER_EXPLAINED_REASONING", "P2", False
        evidence_indices = [4, 5]
        impact = "局部重复已知结论拖慢阅读，但查看封口到选择绕行仍有明确因果。"
        preserve = "保留质疑、展示封口及主动选择绕行的有效交锋，只合并重复结论。"
    elif case == "broken_choice":
        parts = [
            "林舟把信按在桌角，不让阿岚拿走。",
            "“我不会给你，也不相信这条路。”",
            "“那就走。”阿岚把旧地图折好。",
            "林舟把信交给她，同意从河边断路绕行。",
            "两人冒雨出门。",
        ]
        code, severity, required = "LOW_IMMERSION", "P1", True
        evidence_indices = [2, 3, 4]
        impact = "核心选择从拒绝直接变成同意，邻接段落没有触发或代价，读者无法理解让步。"
        preserve = "保留开始拒绝交信的抵触；修复已有冲突到让步的动机，不能删除全部交锋。"
    else:
        parts = opening + [
            "林舟借灯查看封口，松开挡着信的手。",
            "阿岚展开旧地图：“走这边，要多半天。”",
            "“我等得起。”林舟把信收进袖口。",
        ]
        code = severity = required = None
        evidence_indices = []
        impact = ""
        preserve = "保留质疑、可验证回应及带代价的选择，无需为了避免程序感删掉有效对白。"

    content = "\n\n".join(parts)
    verdict = "FAIL" if required else "PASS_WITH_WARNINGS" if code else "PASS"

    def recorded(request, body):
        if request.task_type == "WRITE_CHAPTER":
            body["result"]["content"] = content
        elif request.task_type == "REVIEW_CHAPTER_NARRATIVE":
            assert (
                next(
                    m.module.version
                    for m in request.prompt.modules
                    if m.module.module_id == "review-chapter-narrative"
                )
                == 6
            )
            target = next(
                i for i in request.context_package.items if i.selector_id == "target-version"
            )
            assert target.structured_payload["content"] == content
            finding = []
            if code:
                data = issue(code, severity, requires_revision=required)
                data.update(
                    description=impact,
                    impact=impact,
                    revision_direction=preserve,
                    evidence=[
                        dict(
                            paragraph_index=n,
                            excerpt=parts[n - 1],
                            reason="结合邻段的具体信息或选择变化。",
                        )
                        for n in evidence_indices
                    ],
                )
                finding = [data]
            body["result"].update(
                narrative_verdict=verdict,
                audience_fit_verdict="PASS",
                quality_issues=finding,
                audience_evidence=[],
                strengths=[
                    dict(
                        description="开场的质疑与抵触仍具有具体人物功能。",
                        evidence=[
                            dict(paragraph_index=2, excerpt=parts[1], reason="保留有效人物交锋。")
                        ],
                        preservation_direction=preserve,
                    )
                ],
            )

    provider = RecordedProvider(recorded)
    for _ in range(3):
        worker = run_one(core_database, d, provider=provider)
    saved = d.reviews()[0]["body"]
    assert saved["narrative_verdict"] == verdict
    assert saved["compliance_verdict"] == saved["audience_fit_verdict"] == "PASS"
    assert saved["hard_gate_issues"] == []
    assert saved["strengths"][-1]["preservation_direction"] == preserve
    assert all(i["code"] != "MISSING_MUST" for i in saved["quality_issues"])
    if code:
        assert saved["quality_issues"][0]["severity"] == severity
        assert saved["quality_issues"][0]["requires_revision"] == required
    assert d.workflow["status"] == "WAITING_HUMAN"
    assert not any(t["agent_id"] == "A06_REVISION" for t in d.read("/agent-tasks"))
    assert not worker.run_once()
    assert d.client.get(d.chapter_api + "/versions/1").json()["content"] == content
