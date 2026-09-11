from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from novel_os.domain.core import CommandContext
from novel_os.domain.workflow import EventCommand
from novel_os.models.core import AuditRecordModel, ChapterModel
from novel_os.models.workflow import WorkflowDefinitionModel, WorkflowInstanceModel
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.workflow.runtime import WorkflowRuntime

pytestmark = pytest.mark.integration

TABLES = {
    "workflow_definitions",
    "workflow_instances",
    "workflow_events",
    "workflow_transitions",
    "human_gates",
}


def test_0003_roundtrip_keeps_core_records_and_audit_history(
    driver, core_database, migration_config
):
    driver.advance_to("C06_PLAN_APPROVAL")
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        audits = connection.scalar(select(func.count()).select_from(AuditRecordModel))
        command.downgrade(migration_config, "0003_workflow_engine")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0003_workflow_engine"
        )
        assert set(inspect(connection).get_table_names()) >= TABLES
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_core_domain"
        )
        assert not TABLES & set(inspect(connection).get_table_names())
        assert connection.scalar(select(func.count()).select_from(ChapterModel)) == 1
        assert connection.scalar(select(func.count()).select_from(AuditRecordModel)) == audits
        command.upgrade(migration_config, "head")
        assert set(inspect(connection).get_table_names()) >= TABLES
        command.check(migration_config)
        assert connection.scalar(select(func.count()).select_from(WorkflowInstanceModel)) == 0
        assert connection.scalar(select(func.count()).select_from(AuditRecordModel)) == audits


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("workflow_definitions", "digest", "'changed'"),
        ("workflow_events", "event_type", "'OTHER'"),
        ("workflow_transitions", "reason", "'changed'"),
        ("workflow_instances", "state_version", "state_version + 2"),
        ("human_gates", "artifact_version", "artifact_version + 1"),
    ],
)
def test_database_rejects_history_or_binding_mutation(driver, core_database, table, column, value):
    driver.advance_to("C06_PLAN_APPROVAL")
    with core_database.engine.connect() as connection:
        with pytest.raises(IntegrityError):
            # SQL fragments are a fixed test matrix, never external input.
            connection.execute(text(f"UPDATE {table} SET {column} = {value}"))
        connection.rollback()


@pytest.mark.parametrize("table", sorted(TABLES))
def test_database_rejects_hard_delete(driver, core_database, table):
    driver.advance_to("C06_PLAN_APPROVAL")
    with core_database.engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(f"DELETE FROM {table}"))
        connection.rollback()


def test_repository_flushes_but_does_not_commit(driver, core_database, monkeypatch):
    with core_database.session() as session:
        repo = WorkflowRepository(session)
        original = repo.get(UUID(driver.workflow["id"]))

        def forbidden():
            pytest.fail("Repository attempted to commit or rollback")

        monkeypatch.setattr(session, "commit", forbidden)
        repo.save(replace(original, state_version=original.state_version + 1))
        session.rollback()
    assert driver.refresh()["state_version"] == original.state_version


def test_application_owns_one_commit_per_event(driver, core_database):
    commits = []

    def on_commit(connection):
        commits.append(True)

    event.listen(core_database.engine, "commit", on_commit)
    with core_database.session() as session:
        WorkflowRuntime(session).dispatch_event(
            UUID(driver.workflow["id"]),
            EventCommand(event_id=uuid4(), event_type="USER_SUBMITTED", expected_state_version=1),
            CommandContext("ownership", "user"),
        )
    event.remove(core_database.engine, "commit", on_commit)
    assert len(commits) == 1


def test_invalid_persisted_definition_fails_workflow(driver, core_database, monkeypatch):
    driver.advance_to("C01_REQUIREMENT_INTAKE")
    with core_database.session() as session:
        runtime = WorkflowRuntime(session)
        original = runtime.repo.definition

        def invalid(definition_id, version):
            return replace(original(definition_id, version), digest="corrupt")

        monkeypatch.setattr(runtime.repo, "definition", invalid)
        result = runtime.dispatch_event(
            UUID(driver.workflow["id"]),
            EventCommand(
                event_id=uuid4(),
                event_type="PAUSE",
                expected_state_version=driver.workflow["state_version"],
            ),
            CommandContext("invalid-definition", "user"),
        )
        assert result.workflow["current_state"] == "C91_FAILED"
    assert driver.refresh()["status"] == "FAILED"


def test_second_active_workflow_same_chapter_rejected(driver):
    response = driver.client.post(
        "/api/v1/workflows/chapter", json={**driver.creation, "event_id": str(uuid4())}
    )
    assert response.status_code == 409
    assert driver.refresh()["state_version"] == 1


def test_definition_record_saved_only_once(driver, core_database):
    with core_database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowDefinitionModel)) == 1


def test_corrupt_state_status_is_failed_not_advanced(driver, core_database):
    with core_database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE workflow_instances SET status = 'WAITING_HUMAN', "
                "state_version = state_version + 1"
            )
        )
    driver.refresh()
    assert driver.event("USER_SUBMITTED").status_code == 200
    assert driver.workflow["current_state"] == "C91_FAILED"
    assert driver.workflow["status"] == "FAILED"
