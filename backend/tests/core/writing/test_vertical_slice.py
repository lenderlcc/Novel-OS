from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.planning_support import RecordedProvider


def test_e2e_a_writing_creates_draft_and_stops_at_c08(ready_writer, core_database):
    d = ready_writer
    provider = RecordedProvider()
    worker = run_one(core_database, d, provider=provider)
    assert d.workflow["current_state"] == "C08_DETERMINISTIC_CHECK", d.workflow
    history = d.read("/writing/history")
    assert len(history) == 1
    record = history[0]
    assert record["check_status"] == "PASS"
    assert record["check_codes"] == []
    assert record["plan_version"] == 1
    assert "content" not in record["metadata"]
    chapter = d.client.get(d.chapter_api).json()
    assert chapter["current_version"] == 1 and chapter["approved_version"] is None
    assert len(provider.requests) == 1
    assert worker.run_once() is False
