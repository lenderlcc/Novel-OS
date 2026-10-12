from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from tests.core.quality.test_human_feedback import feedback_driver as feedback_driver
from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_revision import finish_review
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import post


def discard(d):
    body = {**d.command(), "feedback_id": d.workflow["human_feedback_id"]}
    result = d.client.post(d.url + "/feedback/discard", json=body)
    assert result.status_code == 200, result.text
    d.refresh()
    return body


def ask_question(_, body):
    body["result"].update(
        action="USER_DECISION_REQUIRED",
        change_impact="PROSE_ONLY",
        requested_changes=[],
        decision_question="保留故事结果只调整写法，还是改变故事方向？",
        ambiguities=["结尾写法或故事方向"],
        preserve_requests=["开头不变"],
    )


@pytest.mark.parametrize("during_model", [False, True])
@pytest.mark.parametrize("kind", ["draft", "profile"])
def test_stale_feedback_can_be_discarded_and_resubmitted(
    feedback_driver, core_database, kind, during_model
):
    from tests.core.test_writing_profiles import approve, draft

    d = feedback_driver
    original_history = d.read("/feedback")
    original_draft = d.client.get(d.chapter_api + "/versions/1").json()

    def change(*_):
        if kind == "draft":
            post(
                d.client,
                d.chapter_api + "/versions",
                dict(
                    expected_version=1,
                    content="新的人工稿。",
                    change_reason="人工编辑",
                ),
            )
        else:
            project = d.chapter_api.split("/chapters/")[0]
            draft(d.client, project, 1, target_audience="新批准受众")
            approve(d.client, project, 2)

    if not during_model:
        change()
    provider = RecordedProvider(change if during_model else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(during_model)
    assert d.workflow["status"] == "BLOCKED"
    assert d.post("/resume", d.command()).status_code == 409
    abandoned = discard(d)
    assert d.workflow["status"] == "WAITING_HUMAN"
    assert d.workflow["current_state"] == original_history[0]["feedback"]["return_state"]
    assert d.workflow["human_feedback_id"] is None
    assert d.workflow["resume_state"] is None
    assert d.read("/feedback") == original_history
    assert d.client.post(d.url + "/feedback/discard", json=abandoned).json()["duplicate"]
    assert d.client.get(d.chapter_api + "/versions/1").json() == original_draft
    assert submit(d)[0].status_code == 200
    d.refresh()
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C10_REVISION"
    assert len(d.read("/revisions")) == 1


def test_discard_ignores_late_feedback_and_preserves_history(feedback_driver, core_database):
    from tests.core.writing.test_lifecycle import deliver, prepare

    d = feedback_driver
    before = d.read("/feedback")
    lease, _, execution = prepare(core_database)
    wrong = {**d.command(), "feedback_id": str(uuid4())}
    assert d.client.post(d.url + "/feedback/discard", json=wrong).status_code == 409
    discard(d)
    assert deliver(core_database, lease, execution) == "STALE_IGNORED"
    assert d.read("/feedback") == before
    assert d.read("/revisions") == []
    assert d.client.get(d.chapter_api).json()["current_version"] == 1
    assert submit(d)[0].status_code == 200


def test_clarification_keeps_only_related_user_messages_through_revision(
    revision_quality_driver, core_database
):
    d = revision_quality_driver
    finish_review(d, core_database)
    original_draft = d.client.get(d.chapter_api + "/versions/1").json()
    assert submit(d, "这版挺好。独立的历史意见。")[0].status_code == 200
    d.refresh()

    def no_change(_, body):
        body["result"].update(action="NO_CHANGE", change_impact="NONE", requested_changes=[])

    run_one(core_database, d, provider=RecordedProvider(no_change))
    original = "开头千万不要动，中间对白自然一点；结尾不好，需要处理。"
    assert submit(d, original)[0].status_code == 200
    d.refresh()
    run_one(core_database, d, provider=RecordedProvider(ask_question))
    first = deepcopy(d.read("/feedback")[0])
    assert (
        submit(d, "保留故事结果。", reply_to_feedback_id=first["feedback"]["id"])[0].status_code
        == 200
    )
    d.refresh()
    run_one(core_database, d, provider=RecordedProvider(ask_question))
    second = deepcopy(d.read("/feedback")[0])
    assert (
        submit(d, "只调整写法。", reply_to_feedback_id=second["feedback"]["id"])[0].status_code
        == 200
    )
    d.refresh()
    seen = []

    def interpret(request, body):
        item = next(i for i in request.context_package.items if i.selector_id == "human-feedback")
        payload = item.structured_payload
        seen.extend(payload["clarifications"])
        assert [m["raw_feedback"] for m in seen] == [original, "保留故事结果。"]
        assert all(m["decision_question"] for m in seen)
        assert payload["raw_feedback"] == "只调整写法。"
        body["result"].update(
            preserve_requests=["开头千万不要动"],
            do_not_change=["保留故事结果"],
            feedback_evidence=["开头千万不要动", "只调整写法"],
        )

    run_one(core_database, d, provider=RecordedProvider(interpret))
    request = d.read("/revisions")[0]["request"]
    assert request["contract"]["clarifications"] == seen
    assert "开头千万不要动" in request["contract"]["preserve_items"].values()
    stages = RecordedProvider()
    for _ in range(5):
        run_one(core_database, d, provider=stages)
    for request in stages.requests[:3]:
        contract = next(
            i for i in request.context_package.items if i.selector_id == "revision-contract"
        )
        assert contract.structured_payload["clarifications"] == seen
    assert d.workflow["status"] == "WAITING_HUMAN"
    assert d.workflow["draft_version"] == 2
    assert d.client.get(d.chapter_api + "/versions/1").json() == original_draft
    history = d.read("/feedback")
    assert history[1] == second and history[2] == first
    assert (
        d.reviews()[0]["chapter_version_id"]
        == d.client.get(d.chapter_api + "/versions/2").json()["id"]
    )


@pytest.mark.parametrize("invalid", ["obsolete", "other_draft", "not_a_question"])
def test_clarification_rejects_wrong_parent(revision_quality_driver, core_database, invalid):
    d = revision_quality_driver
    finish_review(d, core_database)
    assert submit(d)[0].status_code == 200
    d.refresh()
    if invalid == "not_a_question":

        def no_change(_, body):
            body["result"].update(action="NO_CHANGE", change_impact="NONE", requested_changes=[])

        run_one(core_database, d, provider=RecordedProvider(no_change))
    else:
        run_one(core_database, d, provider=RecordedProvider(ask_question))
    parent = d.read("/feedback")[0]["feedback"]
    source = parent["source_chapter_version_id"]
    if invalid == "obsolete":
        assert submit(d)[0].status_code == 200
        d.refresh()
        run_one(core_database, d, provider=RecordedProvider(ask_question))
    elif invalid == "other_draft":
        source = post(
            d.client,
            d.chapter_api + "/versions",
            dict(
                expected_version=1,
                content="新正文。",
                change_reason="人工修改",
            ),
        )["id"]
    result, _ = submit(
        d, "只调整写法。", reply_to_feedback_id=parent["id"], source_chapter_version_id=source
    )
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "VERSION_CONFLICT"


@pytest.mark.parametrize("support", [False, True])
def test_review_strengths_do_not_override_human_revision(
    revision_quality_driver, core_database, support
):
    d = revision_quality_driver
    review = finish_review(d, core_database)
    assert review["body"]["strengths"]
    assert submit(d, "删掉结尾直接总结的表达，其他地方不要动。")[0].status_code == 200
    d.refresh()

    def interpret(request, body):
        if support:
            review_item = next(
                i for i in request.context_package.items if i.selector_id == "feedback-review"
            )
            body["result"]["supporting_review_issue_ids"] = list(
                review_item.structured_payload["target_issues"]
            )[:1]

    run_one(core_database, d, provider=RecordedProvider(interpret))
    contract = d.read("/revisions")[0]["request"]["contract"]
    assert contract["revision_source"] == ("BOTH" if support else "HUMAN_FEEDBACK")
    assert not any(k.startswith("strength:") for k in contract["preserve_items"])
    assert any(k.startswith("CHAPTER_PLAN:") for k in contract["preserve_items"])
    assert any(k.startswith("PROJECT_WRITING_PROFILE:") for k in contract["do_not_change"])
    assert "feedback-preserve:0" in contract["preserve_items"]
    for _ in range(6 - 1):
        run_one(core_database, d)
    revision = d.read("/revisions")[0]
    assert revision["plan"]["body"]["strength_preservation"] == []
    assert revision["result"]["body"]["fidelity"]["verdict"] == "PASS"
    assert d.workflow["draft_version"] == 2


def test_0015_roundtrip_preserves_existing_feedback(
    feedback_driver, core_database, migration_config
):
    d = feedback_driver
    before = d.read("/feedback")
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0014_human_feedback")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0014_human_feedback"
        )
        assert "reply_to_feedback_id" not in {
            c["name"] for c in inspect(connection).get_columns("human_feedback")
        }
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    assert d.read("/feedback") == before


def test_0015_rejects_loss_of_clarification_history(
    feedback_driver, core_database, migration_config
):
    d = feedback_driver
    run_one(core_database, d, provider=RecordedProvider(ask_question))
    parent = d.read("/feedback")[0]["feedback"]
    assert submit(d, "只调整写法。", reply_to_feedback_id=parent["id"])[0].status_code == 200
    with (
        pytest.raises(DBAPIError, match="immutable feedback clarification history"),
        core_database.engine.begin() as connection,
    ):
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0014_human_feedback")
    assert d.read("/feedback")[0]["feedback"]["reply_to_feedback_id"] == parent["id"]
