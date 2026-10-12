"""Writer output versions retain exact Task lineage through migration round trips."""

from dataclasses import replace

import pytest
from sqlalchemy import text

from alembic import command
from tests.core.writing.test_lifecycle import deliver, prepare


@pytest.mark.parametrize("version", [1, 2])
def test_saved_v1_and_current_v2_writer_persist_exact_lineage(
    writing_driver, core_database, migration_config, monkeypatch, version
):
    from novel_os.agents import registry

    # Reproduce a legitimately scheduled historical task; task pins are immutable.
    monkeypatch.setattr(
        registry,
        "WRITING_TASK",
        replace(registry.WRITING_TASK, result_schema=f"chapter-writing-result.v{version}"),
    )
    d = writing_driver.approve_plan(core_database)
    lease, _, execution = prepare(core_database)
    assert deliver(core_database, lease, execution) == "APPLIED"
    assert len(d.client.get(d.chapter_api + "/versions").json()) == 1
    with core_database.engine.begin() as connection:
        lineage = connection.execute(
            text(
                "SELECT l.output_schema_version, t.expected_output_schema "
                "FROM writing_generations g JOIN prompt_lineages l "
                "ON l.lineage_id=g.prompt_lineage_id JOIN agent_tasks t "
                "ON t.task_id=g.agent_task_id"
            )
        ).one()
        assert tuple(lineage) == (version, f"chapter-writing-result.v{version}")
        before = connection.execute(text("SELECT * FROM writing_generations")).mappings().all()
        guard_before = connection.scalar(
            text("SELECT pg_get_functiondef('guard_writing_evidence()'::regprocedure)")
        )
        assert "output_schema_version IN (1,2)" in guard_before
        assert "= t.expected_output_schema" in guard_before
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0020_character_report_lineage")
        guard_old = connection.scalar(
            text("SELECT pg_get_functiondef('guard_writing_evidence()'::regprocedure)")
        )
        assert "output_schema_version=1" in guard_old
        assert "w.workflow_definition_version IN (2,3,4)" in guard_old
        assert (
            connection.execute(text("SELECT * FROM writing_generations")).mappings().all() == before
        )
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(
                text("SELECT pg_get_functiondef('guard_writing_evidence()'::regprocedure)")
            )
            == guard_before
        )
        assert (
            connection.execute(text("SELECT * FROM writing_generations")).mappings().all() == before
        )
        command.check(migration_config)
