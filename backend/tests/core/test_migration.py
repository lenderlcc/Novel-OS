import pytest
from sqlalchemy import inspect, text

from alembic import command

pytestmark = pytest.mark.integration

TABLES = {
    "projects",
    "requirements",
    "decisions",
    "locks",
    "chapters",
    "chapter_plans",
    "chapter_versions",
    "audit_records",
    "alembic_version",
}


def test_upgrade_downgrade_upgrade_in_isolated_test_schema(core_database, migration_config):
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0002_core_domain")
        assert set(inspect(connection).get_table_names()) == TABLES
        pointers = {item["name"] for item in inspect(connection).get_foreign_keys("chapters")}
        assert {
            "fk_chapters_current_version",
            "fk_chapters_approved_version",
            "fk_chapters_current_plan_version",
            "fk_chapters_approved_plan_version",
        } <= pointers
        command.downgrade(migration_config, "-1")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_bootstrap"
        )
        command.upgrade(migration_config, "0002_core_domain")
        assert set(inspect(connection).get_table_names()) == TABLES
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_core_domain"
        )
        command.upgrade(migration_config, "head")
        command.check(migration_config)
