from dataclasses import replace

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
