import pytest

from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("WRITING_LOCAL_DEVIATION", None),
        ("WRITING_MODERATE_DEVIATION", None),
        ("WRITING_MAJOR_DEVIATION", "MAJOR_PLAN_DEVIATION"),
        ("WRITING_PROPOSED_FACT", None),
        ("WRITING_KNOWLEDGE_RISK", None),
    ],
)
def test_deviation_and_proposal_policy(ready_writer, core_database, scenario, code):
    d = ready_writer
    run_one(core_database, d, scenario)
    records = d.read("/writing/history")
    assert len(records) == 1
    r = records[0]
    assert r["check_status"] == ("BLOCKED" if code else "PASS")
    assert r["check_codes"] == ([code] if code else [])
    assert d.workflow["current_state"] == ("C90_BLOCKED" if code else "C08_DETERMINISTIC_CHECK")
    versions = d.client.get(d.chapter_api + "/versions").json()
    assert len(versions) == (0 if code else 1)
    if versions:
        assert (
            versions[0]["status"] == "DRAFT" and versions[0]["authority_level"] == "A7_AI_INFERENCE"
        )
        assert versions[0]["approved_at"] is None
    if scenario == "WRITING_PROPOSED_FACT":
        assert r["metadata"]["proposed_new_facts"][0]["importance"] == "MINOR"
    assert all("content" not in row["metadata"] for row in records)


@pytest.mark.parametrize(
    "kind",
    [
        "REQUIRED_OUTCOME",
        "ENDING_DIRECTION",
        "MAJOR_DIRECTION",
        "LOCKED_DECISION",
        "CORE_CHARACTER",
        "WORLD_RULE",
        "FUTURE_STRUCTURE",
        "FORBIDDEN_CONSTRAINT",
    ],
)
def test_major_change_cannot_hide_behind_local_label(ready_writer, core_database, kind):
    d = ready_writer

    def mutate(request, body):
        body["result"]["plan_deviations"] = [
            dict(
                type=kind,
                location="结尾",
                planned_behavior="遵守计划",
                actual_behavior="改变方向",
                reason="提案",
                impact="影响章节",
                severity="LOCAL",
                requires_replan=False,
                confidence=0.99,
            )
        ]

    run_one(core_database, d, provider=RecordedProvider(mutate))
    record = d.read("/writing/history")[0]
    assert "MAJOR_PLAN_DEVIATION" in record["check_codes"]
    assert record["chapter_version_id"] is None
    assert d.workflow["current_state"] == "C90_BLOCKED"


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_scene", "SCENE_FUNCTION_INCOMPLETE"),
        ("changed_function", "SCENE_FUNCTION_INCOMPLETE"),
        ("incomplete_scene", "SCENE_FUNCTION_INCOMPLETE"),
        ("confirmed_leak", "CHARACTER_KNOWLEDGE_LEAK"),
        ("major_fact", "MAJOR_NEW_FACT"),
        ("escalation", "WRITING_NEEDS_HUMAN"),
        ("confidence", "WRITING_NEEDS_HUMAN"),
    ],
)
def test_deterministic_check_blocks_explicit_invalid_evidence(
    ready_writer, core_database, mutation, code
):
    d = ready_writer

    def mutate(request, body):
        output = body["result"]
        if mutation == "missing_scene":
            output["scene_execution"][0]["scene_id"] = "UNKNOWN"
        elif mutation == "changed_function":
            output["scene_execution"][0]["planned_function"] = "Invented scene purpose"
        elif mutation == "incomplete_scene":
            output["scene_execution"][0]["function_completed"] = False
        elif mutation == "confirmed_leak":
            output["knowledge_risk_flags"] = [
                dict(
                    character_ref="甲",
                    fact="秘密",
                    knowledge_type="GLOBAL_ONLY",
                    source_location="对话",
                    risk="人物无来源得知事实",
                    confirmed_leak=True,
                )
            ]
        elif mutation == "major_fact":
            output["proposed_new_facts"] = [
                dict(
                    fact="世界规则改变",
                    scope="世界",
                    importance="MAJOR",
                    reason="无法按原计划执行",
                    source_location="结尾",
                    confidence=0.9,
                )
            ]
        elif mutation == "escalation":
            body["escalation"] = dict(required=True, reason="重大选择需要审批")
        else:
            output["confidence"] = 0.4

    run_one(core_database, d, provider=RecordedProvider(mutate))
    record = d.read("/writing/history")[0]
    assert code in record["check_codes"]
    assert d.client.get(d.chapter_api + "/versions").json() == []


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "authority_level",
        "approved_at",
        "version",
        "system_actor",
        "next_state",
        "next_event",
        "event",
        "quality_pass",
    ],
)
def test_fake_control_fields_are_rejected_before_persistence(ready_writer, core_database, field):
    d = ready_writer

    def mutate(request, body):
        body["result"][field] = "APPROVED"

    run_one(core_database, d, provider=RecordedProvider(mutate))
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "SCHEMA_PARSE_ERROR"


@pytest.mark.parametrize(
    "capability",
    [
        "APPROVE",
        "LOCK",
        "UNLOCK",
        "COMMIT_CANON",
        "SET_WORKFLOW_STATE",
        "DIRECT_DATABASE_WRITE",
        "PROPOSE_DRAFT",
    ],
)
def test_writer_cannot_request_authority_actions(ready_writer, core_database, capability):
    d = ready_writer

    def mutate(request, body):
        body["proposed_changes"] = [dict(capability=capability, target_ref=str(request.target_ref))]

    run_one(core_database, d, provider=RecordedProvider(mutate))
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "AUTHORITY_DENIED"


@pytest.mark.parametrize(
    "scenario,error",
    [("WRITING_EMPTY_CONTENT", "SCHEMA_PARSE_ERROR"), ("WRITING_STALE_RESULT", "CONTEXT_STALE")],
)
def test_empty_or_misbound_output_never_becomes_draft(ready_writer, core_database, scenario, error):
    d = ready_writer
    run_one(core_database, d, scenario)
    assert d.read("/agent-tasks")[-1]["last_error_code"] == error
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []
