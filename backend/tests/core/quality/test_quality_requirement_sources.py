def test_formal_requirement_violation_is_quality_fail_not_technical_retry(
    core_client, chapter_api, core_database
):
    import json

    from novel_os.agents.provider import MockModelProvider
    from novel_os.providers.base import ModelResponse
    from novel_os.quality.policy import paragraphs
    from tests.core.quality.conftest import QualityDriver
    from tests.core.workflow.test_planning_vertical_slice import run_one
    from tests.test_quality_contracts import issue

    project = chapter_api.split("/chapters/")[0]
    r = core_client.post(
        project + "/requirements", json=dict(content="禁止引入魔法", requirement_type="FORBIDDEN")
    ).json()
    response = core_client.post(
        project + "/requirements/" + r["logical_id"] + "/approve", json=dict(expected_version=1)
    )
    assert response.status_code == 200, response.text
    d = QualityDriver(core_client, chapter_api).approve_plan(core_database)
    run_one(core_database, d)

    class CitingRequirement(MockModelProvider):
        def generate(self, request):
            body = json.loads(super().generate(request).content)
            record = next(
                i for i in request.context_package.items if i.source_type == "REQUIREMENT"
            )
            assert record.authority_level == "A2_USER_APPROVED"
            assert record.structured_payload["requirement_type"] == "FORBIDDEN"
            target = next(
                i for i in request.context_package.items if i.selector_id == "target-version"
            )
            ref = dict(
                source_type="REQUIREMENT",
                source_id=str(record.source_id),
                source_version=record.source_version,
                field="content",
            )
            finding = issue("FORBIDDEN_VIOLATION")
            finding["source_refs"] = [ref]
            finding["evidence"][0]["excerpt"] = paragraphs(target.structured_payload["content"])[0][
                :50
            ]
            body["result"].update(
                compliance_verdict="FAIL", hard_gate_issues=[finding], source_refs=[ref]
            )
            return ModelResponse(json.dumps(body))

    run_one(core_database, d, provider=CitingRequirement())
    task = next(t for t in d.read("/agent-tasks") if t["task_type"] == "REVIEW_CHAPTER_COMPLIANCE")
    assert task["status"] == "SUCCEEDED", (
        task["status"],
        task["last_error_code"],
        task["last_error_message"],
    )

    run_one(core_database, d)
    assert d.reviews()[0]["body"]["overall_verdict"] == "FAIL"
    assert task["attempt_count"] == 1
