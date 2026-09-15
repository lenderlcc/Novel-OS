from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from novel_os.db.base import Base
from novel_os.domain.core import AuditRecord
from novel_os.domain.errors import DomainError
from novel_os.models.writing import WritingGenerationModel, WritingTaskBindingModel
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.writing import WritingRepository
from novel_os.services.writing_results import WritingResultService
from tests.core.workflow.test_planning_vertical_slice import run_one
from tests.core.writing.test_lifecycle import deliver, prepare


@pytest.mark.parametrize("failure", ["generation", "audit", "check", "transition"])
def test_entire_writing_transaction_rolls_back_then_same_delivery_succeeds(
    ready_writer, core_database, monkeypatch, failure
):
    d = ready_writer
    lease, _, execution = prepare(core_database)
    original_add = WritingRepository.add
    original_audit = CoreRepository.add
    original_check = WritingResultService.check_persisted

    def add(self, entity):
        original_add(self, entity)
        raise RuntimeError("injected writing insert failure")

    def audit(self, entity):
        result = original_audit(self, entity)
        if (
            isinstance(entity, AuditRecord)
            and entity.reason == "Writing result and deterministic check recorded"
        ):
            raise RuntimeError("injected writing audit failure")
        return result

    def check(self, *args):
        original_check(self, *args)
        raise DomainError("VERSION_CONFLICT", "injected check failure")

    from novel_os.workflow.runtime import WorkflowRuntime

    original_transition = WorkflowRuntime._transition

    def transition(self, workflow, target, *args, **kwargs):
        result = original_transition(self, workflow, target, *args, **kwargs)
        if target == "C08_DETERMINISTIC_CHECK":
            raise RuntimeError("injected transition failure")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(
            *{
                "generation": (WritingRepository, "add", add),
                "audit": (CoreRepository, "add", audit),
                "check": (WritingResultService, "check_persisted", check),
                "transition": (WorkflowRuntime, "_transition", transition),
            }[failure]
        )
        with pytest.raises((RuntimeError, DomainError), match="injected"):
            deliver(core_database, lease, execution)
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []
    assert d.refresh()["current_state"] == "C07_WRITING"
    assert d.read("/agent-tasks")[-1]["status"] == "RUNNING"
    with core_database.session() as session:
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM audit_records "
                    "WHERE reason='Writing result and deterministic check recorded'"
                )
            )
            == 0
        )
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert len(d.read("/writing/history")) == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE chapter_versions SET content='overwritten'",
        "UPDATE writing_generations SET metadata='{}'",
        "DELETE FROM writing_generations",
        "UPDATE writing_task_bindings SET expected_draft_version=20",
        "DELETE FROM writing_task_bindings",
    ],
)
def test_database_protects_content_and_writing_evidence(ready_writer, core_database, sql):
    d = ready_writer
    run_one(core_database, d)
    before = d.read("/writing/history")
    body = d.client.get(d.chapter_api + "/versions/1").json()
    with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
        connection.execute(text(sql))
    assert d.read("/writing/history") == before
    assert d.client.get(d.chapter_api + "/versions/1").json() == body


def test_repository_flush_does_not_commit_or_rollback(ready_writer, core_database, monkeypatch):
    d = ready_writer
    lease, _, execution = prepare(core_database)
    original_add = WritingRepository.add

    def checked_add(self, entity):
        with monkeypatch.context() as patch:
            patch.setattr(self.session, "commit", lambda: pytest.fail("Repository committed"))
            patch.setattr(self.session, "rollback", lambda: pytest.fail("Repository rolled back"))
            added = original_add(self, entity)
        with core_database.engine.connect() as observer:
            assert observer.scalar(text("SELECT count(*) FROM writing_generations")) == 0
            assert observer.scalar(text("SELECT count(*) FROM chapter_versions")) == 0
        return added

    monkeypatch.setattr(WritingRepository, "add", checked_add)
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert len(d.read("/writing/history")) == 1


@pytest.mark.parametrize(
    "forgery",
    [
        "project_id",
        "plan_id",
        "chapter_id",
        "agent_run_id",
        "prompt_lineage_id",
        "context_package_id",
        "chapter_version_id",
    ],
)
def test_database_rejects_cross_bound_generation(ready_writer, core_database, monkeypatch, forgery):
    d = ready_writer
    lease, _, execution = prepare(core_database)
    original = WritingRepository.add

    def forged(self, entity):
        return original(self, replace(entity, **{forgery: uuid4()}))

    monkeypatch.setattr(WritingRepository, "add", forged)
    with pytest.raises(IntegrityError):
        deliver(core_database, lease, execution)
    assert d.read("/writing/history") == []
    assert d.client.get(d.chapter_api + "/versions").json() == []


def test_0009_roundtrip_preserves_all_prior_data(ready_writer, core_database, migration_config):
    run_one(core_database, ready_writer)
    added = {"writing_task_bindings", "writing_generations"}

    def snapshot(connection):
        return {
            name: connection.execute(select(table).order_by(*table.primary_key)).mappings().all()
            for name, table in Base.metadata.tables.items()
            if name not in added
        }

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0009_writing_agent"
        )
        before = snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0008_requirement_planning"
        )
        assert not added & set(inspect(connection).get_table_names())
        assert snapshot(connection) == before
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0009_writing_agent"
        )
        assert snapshot(connection) == before
        assert added <= set(inspect(connection).get_table_names())
        command.check(migration_config)
        for table in (WritingGenerationModel.__table__, WritingTaskBindingModel.__table__):
            assert {c.name for c in table.constraints} >= {
                c["name"] for c in inspect(connection).get_foreign_keys(table.name)
            }
