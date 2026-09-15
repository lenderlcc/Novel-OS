from uuid import uuid4

import pytest

from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider
from tests.writing_support import plan, post


def regenerate(driver, draft_version=None):
    return driver.client.post(
        driver.url + "/writing/regenerate",
        json={
            "event_id": str(uuid4()),
            "expected_state_version": driver.workflow["state_version"],
            "expected_draft_version": (
                driver.workflow["draft_version"] if draft_version is None else draft_version
            ),
        },
    )


@pytest.mark.parametrize("suspend", ["PAUSE", "BLOCK"])
@pytest.mark.parametrize("manual_draft", [False, True])
def test_c08_resume_preserves_checked_draft(ready_writer, core_database, suspend, manual_draft):
    d = ready_writer
    run_one(core_database, d)
    checked = d.client.get(d.chapter_api + "/versions/1").json()
    generations = d.read("/writing/history")
    tasks = d.read("/agent-tasks")
    assert d.event(suspend).status_code == 200
    if manual_draft:
        post(
            d.client,
            d.chapter_api + "/versions",
            dict(
                expected_version=1,
                content="Independent user draft, without Writing generation evidence",
                change_reason="User edit while workflow is suspended",
            ),
        )

    resumed = d.event("RESUME")
    assert resumed.status_code == 200 and resumed.json()["outcome"] == "APPLIED"
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert d.workflow["draft_version"] == 1
    assert d.read("/writing/history") == generations
    assert generations[0]["chapter_version_id"] == checked["id"]
    assert d.client.get(d.chapter_api + "/versions/1").json() == checked
    assert d.read("/agent-tasks") == tasks
    chapter = d.client.get(d.chapter_api).json()
    assert chapter["current_version"] == (2 if manual_draft else 1)
    assert chapter["approved_version"] is None

    if manual_draft:
        # Neither current_version nor the old workflow token can adopt/overwrite the edit.
        assert regenerate(d, 2).status_code == 409
        assert regenerate(d, 1).status_code == 409
        assert d.refresh()["draft_version"] == 1
        assert len(d.client.get(d.chapter_api + "/versions").json()) == 2
    else:
        assert regenerate(d).status_code == 200
        run_one(core_database, d)
        assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
        assert d.workflow["draft_version"] == 2
        assert len(d.read("/writing/history")) == 2


@pytest.mark.parametrize("entry", ["regenerate", "PAUSE", "BLOCK"])
def test_c08_changed_approved_plan_recovers_through_new_plan_gate(
    ready_writer, core_database, entry
):
    d = ready_writer
    run_one(core_database, d)
    first = d.client.get(d.chapter_api + "/versions/1").json()
    history = d.read("/writing/history")
    tasks = d.read("/agent-tasks")
    if entry != "regenerate":
        assert d.event(entry).status_code == 200
    plan(d.client, d.chapter_api, 2)
    post(d.client, d.chapter_api + "/plans/approve", dict(expected_version=2))

    result = regenerate(d) if entry == "regenerate" else d.event("RESUME")
    assert result.status_code == 200 and result.json()["outcome"] == "BLOCKED"
    d.refresh()
    assert d.workflow["current_state"] == "C90_BLOCKED"
    assert d.workflow["resume_state"] == "C04_CHAPTER_PLANNING"
    assert d.workflow["blocked_guard"] is None
    assert d.workflow["draft_version"] == 1
    assert d.read("/writing/history") == history
    assert d.read("/agent-tasks") == tasks

    resumed = d.event("RESUME")
    assert resumed.status_code == 200 and resumed.json()["outcome"] == "APPLIED"
    assert d.workflow["current_state"] == "C04_CHAPTER_PLANNING"
    assert (d.workflow["plan_version"], d.workflow["draft_version"]) == (2, 1)
    run_one(core_database, d)
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C06_PLAN_APPROVAL"
    assert len(d.read("/writing/history")) == 1
    assert d.decide().status_code == 200
    run_one(core_database, d)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert (d.workflow["plan_version"], d.workflow["draft_version"]) == (3, 2)
    history = d.read("/writing/history")
    assert [row["plan_version"] for row in history] == [1, 3]
    assert d.client.get(d.chapter_api + "/versions/1").json() == first


def test_c08_proposed_plan_does_not_replace_approved_binding(ready_writer, core_database):
    d = ready_writer
    run_one(core_database, d)
    plan(d.client, d.chapter_api, 2, objective="UNAPPROVED_PLAN_V2_SECRET")
    assert d.event("PAUSE").status_code == 200
    resumed = d.event("RESUME")
    assert resumed.status_code == 200 and resumed.json()["outcome"] == "APPLIED"
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert regenerate(d).status_code == 200
    provider = RecordedProvider()
    run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK"
    assert (d.workflow["plan_version"], d.workflow["draft_version"]) == (1, 2)
    package = provider.requests[0].context_package
    assert "UNAPPROVED_PLAN_V2_SECRET" not in str(package)
    assert [i.source_version for i in package.items if i.selector_id == "approved-plan"] == [1]
