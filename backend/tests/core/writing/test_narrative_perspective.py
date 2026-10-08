from uuid import UUID

import pytest
from sqlalchemy import text

from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.services.prompt_lineages import PromptLineageService
from tests.core.test_writing_profiles import approve, draft
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.core.writing.conftest import WritingDriver
from tests.core.writing.test_project_writing_profile_context import profiles, project
from tests.planning_support import RecordedProvider
from tests.writing_support import chapter


@pytest.mark.parametrize("perspective", ["FIRST_PERSON", "THIRD_PERSON", None])
def test_approved_perspective_and_draft_isolation_through_writing_lineage(
    writing_driver, core_database, perspective
):
    d = writing_driver
    url = project(d)
    legacy = {} if perspective is None else {"narrative_perspective": perspective}
    v1 = draft(d.client, url, **legacy)
    approved = approve(d.client, url)
    v2 = draft(d.client, url, 1, narrative_perspective="THIRD_PERSON")
    d.approve_plan(core_database)
    plans_before = d.client.get(d.chapter_api + "/plans").json()
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    request = provider.requests[0]
    assert request.context_package.profile_id == "CP-005"
    selected = profiles(request.context_package)[0]
    payload = selected.structured_payload
    assert payload.get("narrative_perspective") == perspective
    assert selected.authority_level == "A5_USER_PREFERENCE"
    assert payload["writing_profile_version"] == 1
    assert payload["writing_profile_id"] == approved["profile_id"]
    assert payload["writing_profile_hash"] == approved["profile_hash"] == v1["profile_hash"]
    assert v2["profile_hash"] != payload["writing_profile_hash"]
    prompt = "\n".join(m.content for m in request.prompt.messages)
    if perspective:
        assert f'"narrative_perspective":"{perspective}"' in prompt
    else:
        assert "narrative_perspective" not in payload
    generation = d.read("/writing/history")[0]
    with core_database.session() as session:
        stored = ContextPackageRepository(session).get(UUID(generation["context_package_id"]))
        assert profiles(stored)[0] == selected
    lineage = d.client.get(f"/api/v1/agent-runs/{generation['agent_run_id']}/prompt-lineage").json()
    assert lineage["task_template"]["version"] == 6
    assert lineage["task_id"] == generation["agent_task_id"]
    assert d.client.get(d.chapter_api + "/plans").json() == plans_before
    assert d.client.get(url + "/writing-profile/approved").json() == approved

    # Approval selects v2 only for subsequent tasks; v1 and its lineage stay intact.
    approved2 = approve(d.client, url, 2)
    second = WritingDriver(d.client, chapter(d.client, url, 2))
    second.approve_plan(core_database)
    provider2 = RecordedProvider()
    run_one(core_database, second, provider=provider2)
    selected2 = profiles(provider2.requests[0].context_package)[0].structured_payload
    assert selected2["narrative_perspective"] == "THIRD_PERSON"
    assert selected2["writing_profile_version"] == 2
    assert selected2["writing_profile_hash"] == approved2["profile_hash"]
    with core_database.session() as session:
        old = ContextPackageRepository(session).get(UUID(generation["context_package_id"]))
        assert old == stored
    history = d.client.get(url + "/writing-profile/versions").json()
    assert history[1]["profile_hash"] == approved["profile_hash"]
    assert history[1]["narrative_perspective"] == perspective


def test_draft_only_profile_is_not_sent_to_writer(writing_driver, core_database):
    d = writing_driver
    draft(d.client, project(d), narrative_perspective="THIRD_PERSON")
    d.approve_plan(core_database)
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert profiles(provider.requests[0].context_package) == []
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"


@pytest.mark.parametrize("timing", ["queued", "before_model", "during_model"])
def test_perspective_only_approval_change_makes_existing_writer_stale(
    writing_driver, core_database, monkeypatch, timing
):
    d = writing_driver
    url = project(d)
    draft(d.client, url, narrative_perspective="FIRST_PERSON")
    approve(d.client, url)
    d.approve_plan(core_database)

    def change(*_):
        draft(d.client, url, 1, narrative_perspective="THIRD_PERSON")
        approve(d.client, url, 2)

    if timing == "queued":
        change()
    elif timing == "before_model":
        original = PromptLineageService.bind

        def bind(self, *args, **kwargs):
            value = original(self, *args, **kwargs)
            change()
            return value

        monkeypatch.setattr(PromptLineageService, "bind", bind)
    provider = RecordedProvider(change if timing == "during_model" else None)
    run_one(core_database, d, provider=provider)
    assert len(provider.requests) == int(timing == "during_model")
    if provider.requests:
        assert (
            profiles(provider.requests[0].context_package)[0].structured_payload[
                "narrative_perspective"
            ]
            == "FIRST_PERSON"
        )
    assert d.read("/agent-tasks")[-1]["last_error_code"] == "CONTEXT_STALE"
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []


def test_third_person_dialogue_with_first_person_pronouns_is_not_rejected(
    writing_driver, core_database
):
    d = writing_driver
    draft(d.client, project(d), narrative_perspective="THIRD_PERSON")
    approve(d.client, project(d))
    d.approve_plan(core_database)
    prose = "林峤走到窗口前。“我不知道。我的票呢？我们等一等。”他说。“你先走。”同伴答道。"

    def dialogue(request, body):
        body["result"]["content"] = prose

    run_one(core_database, d, provider=RecordedProvider(dialogue))
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert d.read("/writing/history")[0]["check_status"] == "PASS"
    assert d.client.get(d.chapter_api + "/versions").json()[0]["content"] == prose


def test_invalid_perspective_http_rejected_and_legacy_row_has_no_backfill(
    core_client, project_api, core_database
):
    response = core_client.post(
        project_api + "/writing-profile/drafts",
        json={"expected_version": 0, "preferences": {"narrative_perspective": "OMNISCIENT"}},
    )
    assert response.status_code == 422
    draft(core_client, project_api)
    approved = approve(core_client, project_api)
    assert approved["narrative_perspective"] is None
    with core_database.session() as session:
        payload = session.scalar(text("SELECT preferences FROM project_writing_profiles"))
        assert "narrative_perspective" not in payload
