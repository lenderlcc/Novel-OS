from tests.core.quality.test_human_feedback import submit
from tests.core.quality.test_revision import finish_review
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def test_feedback_rebinds_exact_current_manual_draft_without_review(
    revision_quality_driver, core_database
):
    from tests.writing_support import post

    driver = revision_quality_driver
    finish_review(driver, core_database, "SUCCESS")
    created = post(
        driver.client,
        driver.chapter_api + "/versions",
        dict(expected_version=1, content="当前人工修改稿", change_reason="人工编辑"),
    )
    response, _ = submit(driver, source_chapter_version_id=created["id"])
    assert response.status_code == 200, response.text
    driver.refresh()
    assert driver.workflow["draft_version"] == 2
    assert driver.workflow["current_state"] == "C13_USER_FEEDBACK_DIAGNOSIS"
    history = driver.client.get(driver.url + "/feedback").json()
    assert history[0]["feedback"]["source_chapter_version_id"] == created["id"]
    assert history[0]["feedback"]["source_review_id"] is None

    run_one(core_database, driver, provider=RecordedProvider())
    assert driver.workflow["current_state"] == "C10_REVISION"


def test_low_confidence_feedback_result_has_no_recovery_path(
    revision_quality_driver, core_database
):
    driver = revision_quality_driver
    finish_review(driver, core_database, "SUCCESS")
    response, _ = submit(driver)
    assert response.status_code == 200
    driver.refresh()

    def lower_feedback_confidence(request, body):
        if request.output_kind == "human_feedback_interpretation":
            body["confidence"] = 0.2

    run_one(core_database, driver, provider=RecordedProvider(lower_feedback_confidence))
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    history = driver.client.get(driver.url + "/feedback").json()
    assert len(history) == 1
    assert history[0]["interpretation"] is None

    response = driver.client.post(driver.url + "/resume", json=driver.command())
    assert response.status_code == 200
    assert response.json()["workflow"]["current_state"] == "C13_USER_FEEDBACK_DIAGNOSIS"
    assert len(driver.client.get(driver.url + "/feedback").json()) == 1
