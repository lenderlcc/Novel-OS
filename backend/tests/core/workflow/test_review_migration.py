from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema

from alembic import command
from novel_os.db.base import Base
from novel_os.db.session import Database

pytestmark = pytest.mark.integration

WORKFLOW_TABLES = {
    "workflow_definitions",
    "workflow_instances",
    "workflow_events",
    "workflow_transitions",
    "human_gates",
}


def history_snapshot(connection):
    return {
        name: connection.execute(select(Base.metadata.tables[name])).mappings().all()
        for name in sorted(WORKFLOW_TABLES - {"workflow_instances"} | {"audit_records"})
    }


@pytest.mark.parametrize("recovery", ["same_stage", "new_stage", "overwritten_new_stage"])
def test_0004_roundtrip_preserves_pending_recovery_and_history(
    driver, core_database, migration_config, recovery
):
    driver.advance_to("C07_WRITING")
    assert driver.fake("technical_failure").status_code == 200
    if recovery == "same_stage":
        assert driver.event("BLOCK").status_code == 200
    else:
        response = driver.client.post(
            driver.chapter_api + "/plans",
            json={"objective": "New plan", "required_outcome": "New end", "expected_version": 1},
        )
        assert response.status_code == 201, response.text
        assert driver.fake().status_code == 200
    assert driver.workflow["current_state"] == "C90_BLOCKED"
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        # NOVEL-004 adds 0005; this test still exercises the frozen 0004 recovery migration.
        command.downgrade(migration_config, "0004_workflow_recovery")
        history = history_snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0003_workflow_engine"
        )
        assert "resume_new_stage" not in {
            c["name"] for c in inspect(connection).get_columns("workflow_instances")
        }
        row = dict(connection.execute(text("SELECT * FROM workflow_instances")).mappings().one())
        assert row["blocked_guard"] == ("writable" if recovery == "same_stage" else None)
        if recovery == "overwritten_new_stage":
            # Reproduce an old 0003 secondary block overwriting the only recovery marker.
            # The original block's immutable audit remains the source for the backfill.
            connection.execute(
                text(
                    "UPDATE workflow_instances SET blocked_guard = 'writable', "
                    "state_version = state_version + 1"
                )
            )
            row = dict(
                connection.execute(text("SELECT * FROM workflow_instances")).mappings().one()
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("DELETE FROM workflow_instances"))
        command.upgrade(migration_config, "0004_workflow_recovery")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0004_workflow_recovery"
        )
        upgraded = dict(
            connection.execute(text("SELECT * FROM workflow_instances")).mappings().one()
        )
        assert upgraded.pop("resume_new_stage") == (recovery != "same_stage")
        assert upgraded == row
        assert history_snapshot(connection) == history
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    driver.refresh()
    resume = driver.command()
    assert driver.post("/resume", resume).status_code == 200
    recovered = driver.workflow.copy()
    assert recovered["planning_iteration_count"] == (1 if recovery == "same_stage" else 2)
    assert recovered["state_retry_count"] == (1 if recovery == "same_stage" else 0)
    assert recovered["retry_count"] == 1
    assert driver.post("/resume", resume).json()["duplicate"] is True
    assert driver.refresh() == recovered


def test_workflow_metadata_constraint_names_match_migrated_schema(core_database):
    with core_database.engine.connect() as connection:
        for name in WORKFLOW_TABLES:
            names = [
                c.name
                for c in Base.metadata.tables[name].constraints
                if isinstance(c, CheckConstraint)
            ]
            assert len(names) == len(set(names)), name
            migrated = {c["name"] for c in inspect(connection).get_check_constraints(name)}
            assert set(names) == migrated, name


def test_metadata_creates_valid_postgres_schema(database_settings):
    database = Database(database_settings)
    schema = "novel003_metadata_" + uuid4().hex
    try:
        with database.engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(CreateSchema(schema))
                # This identifier is generated above, never supplied by a client.
                connection.execute(text("SET LOCAL search_path TO " + schema))
                Base.metadata.create_all(connection)
                assert set(inspect(connection).get_table_names()) >= WORKFLOW_TABLES
            finally:
                transaction.rollback()
    finally:
        database.dispose()
