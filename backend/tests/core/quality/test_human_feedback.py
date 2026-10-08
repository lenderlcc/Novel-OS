from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.core.quality.test_revision import finish_review
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def submit(d, raw="中间对白自然一些，开头和结尾保持不变。", **changes):
    draft = d.client.get(d.chapter_api + f"/versions/{d.workflow['draft_version']}").json()
    body = dict(
        event_id=str(uuid4()),
        expected_state_version=d.workflow["state_version"],
        source_chapter_version_id=draft["id"],
        raw_feedback=raw,
    )
    body.update(changes)
    response = d.client.post(d.url + "/feedback", json=body)
    return response, body


def test_human_feedback_full_slice(revision_quality_driver, core_database):
    d = revision_quality_driver
    review = finish_review(d, core_database, "SUCCESS")
    original = d.client.get(d.chapter_api + "/versions/1").json()
    brief = deepcopy(d.read("/creative-brief"))
    d.client._transport.raise_server_exceptions = True
    response, body = submit(d)
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["current_state"] == "C13_USER_FEEDBACK_DIAGNOSIS"
    duplicate = d.client.post(d.url + "/feedback", json=body)
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"]
    concurrent, _ = submit(d)
    assert concurrent.status_code == 409
    provider = RecordedProvider()
    for _ in range(6):
        assert d.workflow["status"] == "WAITING_AGENT", [
            (t["task_type"], t["last_error_code"], t["status"])
            for t in d.read("/agent-tasks")
            if t["status"] != "SUCCEEDED"
        ]
        worker = run_one(core_database, d, provider=provider)
    assert d.workflow["status"] == "WAITING_HUMAN", d.workflow
    assert d.workflow["draft_version"] == 2
    assert not worker.run_once()
    assert d.client.get(d.chapter_api + "/versions/1").json() == original
    assert d.read("/creative-brief") == brief
    assert d.client.get(d.chapter_api).json()["approved_version"] is None
    history = d.read("/feedback")
    assert len(history) == 1
    feedback = history[0]["feedback"]
    interpretation = history[0]["interpretation"]
    assert feedback["raw_feedback"] == body["raw_feedback"]
    assert feedback["source_chapter_version_id"] == original["id"]
    assert feedback["source_review_id"] == review["id"]
    assert interpretation["body"]["preserve_requests"]
    revision = d.read("/revisions")[0]
    assert revision["request"]["source_feedback_id"] == feedback["id"]
    assert revision["source_binding"] is None
    assert revision["plan"]["body"]["revision_source"] == "HUMAN_FEEDBACK"
    assert "feedback-preserve:0" in revision["plan"]["body"]["preserve_items"]
    assert "feedback-boundary:0" in revision["plan"]["body"]["do_not_change"]
    assert revision["plan"]["body"]["revision_zones"][0]["semantic_range"] == "局部表达"
    assert revision["result"]["body"]["fidelity"]["verdict"] == "PASS"
    successor = d.client.get(d.chapter_api + "/versions/2").json()
    assert d.reviews()[0]["chapter_version_id"] == successor["id"]
    assert {r.task_type for r in provider.requests} == {
        "INTERPRET_CHAPTER_FEEDBACK",
        "PLAN_CHAPTER_REVISION",
        "REVISE_CHAPTER",
        "VALIDATE_REVISION_FIDELITY",
        "REVIEW_CHAPTER_COMPLIANCE",
        "REVIEW_CHAPTER_NARRATIVE",
    }
    for table in ("human_feedback", "human_feedback_interpretations"):
        with core_database.session() as session, pytest.raises(IntegrityError), session.begin():
            session.execute(text(f"UPDATE {table} SET created_at=now()"))
    stale, _ = submit(d, source_chapter_version_id=original["id"])
    assert stale.status_code == 409


@pytest.fixture
def feedback_driver(revision_quality_driver, core_database):
    d = revision_quality_driver
    finish_review(d, core_database)
    response, _ = submit(d)
    assert response.status_code == 200, response.text
    d.refresh()
    return d


# Recorded semantic outputs test routing/contracts, not the live model's language skill.
@pytest.mark.parametrize(
    "raw,action,impact,boundary",
    [
        ("这版还是有点假，对话听起来太像两个人在轮流讲道理。", "REVISION", "PROSE_ONLY", None),
        (
            "养护棚那一段对白还是有点一问一答，前面不要动，最后继续上山的方向也不要改。",
            "REVISION",
            "PROSE_ONLY",
            None,
        ),
        ("开头挺好的。中间解释有点多，最后那段也可以保留。", "REVISION", "PROSE_ONLY", None),
        (
            "我改主意了，最后不要继续上山，让他坐撤离车离开。",
            "REPLAN_REQUIRED",
            "STORY_DIRECTION",
            "APPROVED_PLAN",
        ),
        (
            "以后所有章节都不要写心理活动。",
            "PROFILE_CHANGE_REQUIRED",
            "PROJECT_PREFERENCE",
            "PROJECT_PROFILE",
        ),
        (
            "开头不要动，但把开头换成医院。",
            "USER_DECISION_REQUIRED",
            "PROSE_ONLY",
            "USER_INSTRUCTIONS",
        ),
        ("这版可以了。", "NO_CHANGE", "NONE", None),
        ("还是没代入感。", "REVISION", "PROSE_ONLY", None),
        ("把这个锁定的方向改掉。", "USER_DECISION_REQUIRED", "STORY_DIRECTION", "LOCK"),
    ],
)
def test_semantic_routes_do_not_mutate_other_domains(
    revision_quality_driver, core_database, raw, action, impact, boundary
):
    d = revision_quality_driver
    finish_review(d, core_database)
    before_brief = d.read("/creative-brief")
    before_plan = d.client.get(d.chapter_api + "/plans/1").json()
    project = d.chapter_api.split("/chapters/")[0]
    profile = d.client.get(project + "/writing-profile").json()
    response, _ = submit(d, raw)
    assert response.status_code == 200, response.text
    d.refresh()

    def interpret(_, body):
        r = body["result"]
        r.update(
            action=action,
            change_impact=impact,
            conflicts=[dict(boundary=boundary, explanation="记录的语义冲突")] if boundary else [],
            decision_question="请确认以哪个要求为准？"
            if action == "USER_DECISION_REQUIRED"
            else None,
        )
        if action != "REVISION":
            r["requested_changes"] = []

    worker = run_one(core_database, d, provider=RecordedProvider(interpret))
    assert d.read("/feedback")[0]["interpretation"]["body"]["action"] == action
    assert d.read("/creative-brief") == before_brief
    assert d.client.get(d.chapter_api + "/plans/1").json() == before_plan
    assert d.client.get(project + "/writing-profile").json() == profile
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    if action != "REVISION":
        assert d.workflow["status"] == "WAITING_HUMAN"
        assert not d.read("/revisions")
        assert not worker.run_once()
    else:
        assert d.workflow["current_state"] == "C10_REVISION"
        assert len(d.read("/revisions")) == 1


@pytest.mark.parametrize("phase", [0, 1])
@pytest.mark.parametrize("during_model", [False, True])
@pytest.mark.parametrize("change_kind", ["draft", "plan", "profile", "lock"])
def test_feedback_freshness(feedback_driver, core_database, phase, during_model, change_kind):
    from tests.core.test_writing_profiles import approve, draft
    from tests.writing_support import plan, post

    d = feedback_driver
    if phase:
        run_one(core_database, d)

    def change(*_):
        project = d.chapter_api.split("/chapters/")[0]
        if change_kind == "draft":
            post(
                d.client,
                d.chapter_api + "/versions",
                dict(expected_version=1, content="新的人工稿", change_reason="变更"),
            )
        elif change_kind == "plan":
            plan(d.client, d.chapter_api, 2)
            post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))
        elif change_kind == "profile":
            draft(d.client, project, 1, target_audience="新批准受众")
            approve(d.client, project, 2)
        else:
            chapter = d.client.get(d.chapter_api).json()
            post(
                d.client,
                project + "/locks",
                dict(
                    expected_version=chapter["version"],
                    target_type="CHAPTER",
                    target_id=chapter["id"],
                    reason="用户锁定",
                ),
            )

    if not during_model:
        change()
    provider = RecordedProvider(change if during_model else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(during_model)
    assert d.workflow["status"] == "BLOCKED", d.workflow
    assert d.read("/revisions")[0]["plan"] is None if phase else not d.read("/revisions")


@pytest.mark.parametrize(
    "mutation", ["source", "proposal", "memory", "action", "evidence", "scope", "authority"]
)
def test_invalid_interpretation_contract(feedback_driver, core_database, mutation):
    d = feedback_driver

    def corrupt(request, body):
        result = body["result"]
        if mutation == "source":
            result["source_chapter_version_id"] = str(uuid4())
        elif mutation in {"proposal", "memory"}:
            body["proposed_changes" if mutation == "proposal" else "memory_proposals"] = [
                dict(capability="PROPOSE_DRAFT", target_ref=str(request.target_ref))
            ]
        elif mutation == "action":
            result["action"] = "REWRITE_ALL"
        elif mutation == "evidence":
            result["feedback_evidence"] = ["不是用户写的引文"]
        elif mutation == "scope":
            result["target_regions"] = ["其他范围"]
        else:
            result["change_impact"] = "STORY_DIRECTION"

    run_one(core_database, d, provider=RecordedProvider(corrupt))
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "SCHEMA_PARSE_ERROR"
    assert d.read("/feedback")[0]["interpretation"] is None
    assert d.read("/revisions") == []


def test_provider_retry_duplicate_delivery_and_cancel(feedback_driver, core_database):
    from tests.core.writing.test_lifecycle import deliver, prepare

    d = feedback_driver
    run_one(core_database, d, "MODEL_ERROR_ONCE")
    assert d.read("/agent-tasks")[-1]["status"] == "PENDING"
    lease, _, execution = prepare(core_database)
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert deliver(core_database, lease, execution) == "DUPLICATE"
    d.refresh()
    assert len(d.read("/revisions")) == 1
    assert len(d.read("/feedback")) == 1
    lease, _, execution = prepare(core_database)
    assert d.post("/cancel", d.command()).status_code == 200
    assert deliver(core_database, lease, execution) == "STALE_IGNORED"
    assert d.client.get(d.chapter_api).json()["current_version"] == 1


def test_feedback_fidelity_fail_preserves_source(feedback_driver, core_database):
    d = feedback_driver
    for _ in range(3):
        run_one(core_database, d)
    run_one(core_database, d, "QUALITY_FAIL")
    assert d.workflow["status"] == "BLOCKED"
    record = d.read("/revisions")[0]
    assert record["result"]["chapter_version_id"] is None
    assert record["result"]["body"]["fidelity"]["verdict"] == "FAIL"
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert len(d.reviews()) == 1


def test_feedback_rollback_and_flush_only(feedback_driver, core_database, monkeypatch):
    from novel_os.repositories.feedback import FeedbackRepository
    from tests.core.writing.test_lifecycle import deliver, prepare

    d = feedback_driver
    lease, _, execution = prepare(core_database)
    original = FeedbackRepository.add

    def fail(self, record):
        with monkeypatch.context() as patch:
            patch.setattr(
                self.session, "commit", lambda: pytest.fail("Repository commit forbidden")
            )
            original(self, record)
        raise RuntimeError("rollback probe")

    with monkeypatch.context() as patch:
        patch.setattr(FeedbackRepository, "add", fail)
        with pytest.raises(RuntimeError, match="rollback probe"):
            deliver(core_database, lease, execution)
    assert d.read("/feedback")[0]["interpretation"] is None
    assert d.read("/revisions") == []
    assert deliver(core_database, lease, execution) == "APPLIED"


def test_concurrent_feedback_is_single_request(revision_quality_driver, core_database):
    from concurrent.futures import ThreadPoolExecutor

    d = revision_quality_driver
    finish_review(d, core_database)
    version = d.workflow["state_version"]
    source = d.client.get(d.chapter_api + "/versions/1").json()["id"]
    bodies = [
        dict(
            event_id=str(uuid4()),
            expected_state_version=version,
            source_chapter_version_id=source,
            raw_feedback="改对白",
        )
        for _ in range(2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda body: d.client.post(d.url + "/feedback", json=body), bodies))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert len(d.read("/feedback")) == 1


def test_feedback_migration_roundtrip(core_database, migration_config):
    from sqlalchemy import inspect

    from alembic import command

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0013_revision_fidelity")
        assert "human_feedback" not in inspect(connection).get_table_names()
        command.upgrade(migration_config, "head")
        command.check(migration_config)


def test_current_manual_draft_without_review_is_bound_explicitly(
    revision_quality_driver, core_database
):
    from tests.writing_support import post

    d = revision_quality_driver
    finish_review(d, core_database)
    manual = post(
        d.client,
        d.chapter_api + "/versions",
        dict(expected_version=1, content="雨停了。她收起那封信。", change_reason="人工新稿"),
    )
    response, _ = submit(d, source_chapter_version_id=manual["id"])
    assert response.status_code == 200, response.text
    d.refresh()
    assert d.workflow["draft_version"] == 2
    assert d.read("/feedback")[0]["feedback"]["source_review_id"] is None
    for _ in range(4):
        run_one(core_database, d)
    assert d.workflow["draft_version"] == 3
    assert d.client.get(d.chapter_api + "/versions/2").json() == manual
    assert d.read("/revisions")[0]["request"]["source_review_id"] is None
