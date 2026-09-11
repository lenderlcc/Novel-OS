import pytest
from agent_test_support import worker
from sqlalchemy import CheckConstraint, inspect, select, text

from alembic import command
from novel_os.db.base import Base

pytestmark = pytest.mark.integration


def snapshot(connection):
    return {
        name: connection.execute(select(table).order_by(*table.primary_key)).mappings().all()
        for name, table in Base.metadata.tables.items()
        if name not in {"agent_tasks", "agent_runs", "prompt_lineages"}
    }


def test_0005_roundtrip_preserves_core_workflow_audit_and_worker_recovers_waiting_stage(
    driver, core_database, migration_config
):
    driver.advance_to("C04_CHAPTER_PLANNING")
    assert worker(core_database).run_once()
    assert driver.refresh()["current_state"] == "C05_PLAN_REVIEW"
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert connection.scalar(text("SELECT count(*) FROM agent_runs")) == 1
        command.downgrade(migration_config, "0005_agent_runtime")
        before = snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0004_workflow_recovery"
        )
        assert not {"agent_tasks", "agent_runs"} & set(inspect(connection).get_table_names())
        assert snapshot(connection) == before
        command.upgrade(migration_config, "head")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0006_prompt_runtime"
        )
        assert connection.scalar(text("SELECT count(*) FROM agent_tasks")) == 0
        assert snapshot(connection) == before
        command.check(migration_config)
    # Existing NOVEL-003 stages have no AgentTask. A new worker safely schedules the missing stage.
    assert worker(core_database).run_once()
    assert driver.refresh()["current_state"] == "C06_PLAN_APPROVAL"
    tasks = driver.client.get(driver.url + "/agent-tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "MOCK_PLAN_REVIEW"
    assert tasks[0]["status"] == "SUCCEEDED"


def test_agent_metadata_matches_migrated_constraints(core_database):
    with core_database.engine.connect() as connection:
        for name in ("agent_tasks", "agent_runs"):
            expected = {
                constraint.name
                for constraint in Base.metadata.tables[name].constraints
                if isinstance(constraint, CheckConstraint)
            }
            actual = {c["name"] for c in inspect(connection).get_check_constraints(name)}
            assert expected == actual
