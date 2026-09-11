import json
import subprocess
import sys
from uuid import UUID

import pytest
from agent_test_support import claim, pending_task, runs, start
from sqlalchemy import text

from novel_os.domain.agents import RunStatus

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("recovery", [False, True])
def test_independent_worker_process_resumes_pending_or_expired_task(
    driver, core_database, core_settings, tmp_path, recovery
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    task_id = UUID(pending_task(driver)["task_id"])
    if recovery:
        start(core_database, claim(core_database, "dead-worker"))
        with core_database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE agent_tasks SET lease_expires_at=clock_timestamp()-INTERVAL '1 second',"
                    " version=version+1 WHERE task_id=:id"
                ),
                {"id": task_id},
            )
    config = tmp_path / "worker.toml"
    config.write_text(
        "postgres_url = " + json.dumps(core_settings.postgres_url.get_secret_value()) + "\n"
    )
    config.chmod(0o600)
    process = subprocess.run(
        [sys.executable, "-m", "novel_os.worker", "--once", "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert process.returncode == 0, "Independent worker did not complete successfully"
    assert "agent_attempt_finished" in process.stderr
    assert driver.refresh()["current_state"] == "C05_PLAN_REVIEW"
    history = runs(core_database, task_id)
    assert len(history) == (2 if recovery else 1)
    assert history[-1].status == RunStatus.SUCCEEDED
    if recovery:
        assert history[0].status == RunStatus.ABANDONED
        assert history[0].worker_id == "dead-worker"
