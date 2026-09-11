import pytest
from agent_test_support import worker
from sqlalchemy import inspect, select, text

from alembic import command
from novel_os.db.base import Base

pytestmark = pytest.mark.integration


def historical_snapshot(connection):
    return {
        name: connection.execute(select(table).order_by(*table.primary_key)).mappings().all()
        for name, table in Base.metadata.tables.items()
        if name != "prompt_lineages"
    }


def test_0006_roundtrip_preserves_all_existing_core_workflow_agent_and_audit_rows(
    driver, core_database, migration_config
):
    driver.event("USER_SUBMITTED")
    worker(core_database).run_once()
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert connection.scalar(text("SELECT count(*) FROM prompt_lineages")) == 1
        before = historical_snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0005_agent_runtime"
        )
        assert "prompt_lineages" not in inspect(connection).get_table_names()
        assert historical_snapshot(connection) == before
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0006_prompt_runtime"
        )
        assert connection.scalar(text("SELECT count(*) FROM prompt_lineages")) == 0
        assert historical_snapshot(connection) == before
        command.check(migration_config)
    assert worker(core_database).run_once()
