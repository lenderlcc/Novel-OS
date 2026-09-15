import pytest
from sqlalchemy import inspect, select, text

from alembic import command
from novel_os.db.base import Base
from tests.core.workflow.test_planning_vertical_slice import run_one

pytestmark = pytest.mark.integration
ADDED = {"creative_briefs", "plan_generations", "plan_review_reports"}


def historical_rows(connection):
    return {
        name: connection.execute(select(table).order_by(*table.primary_key)).mappings().all()
        for name, table in Base.metadata.tables.items()
        if name not in ADDED
    }


def test_0008_roundtrip_preserves_all_older_tables_including_business_workflow(
    planning_driver, core_database, migration_config
):
    run_one(core_database, planning_driver)
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0008_requirement_planning"
        )
        before = historical_rows(connection)
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0007_context_engine"
        )
        assert not ADDED & set(inspect(connection).get_table_names())
        assert historical_rows(connection) == before
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0008_requirement_planning"
        )
        assert set(inspect(connection).get_table_names()) >= ADDED
        assert historical_rows(connection) == before
        command.check(migration_config)
