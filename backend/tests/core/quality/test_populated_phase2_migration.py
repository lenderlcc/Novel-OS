"""Existing committed memory survives Phase 2 upgrades with its original provenance."""

from sqlalchemy import inspect, text

from alembic import command
from tests.core.quality.test_memory_commit import confirm, prepare


def test_populated_0019_backfill_preserves_exact_historical_records(
    quality_driver, core_database, migration_config
):
    d = quality_driver
    prepare(d, core_database)
    response = confirm(
        d, ["fact", "state", "knowledge", "belief", "relationship", "thread", "summary"]
    )
    assert response.status_code == 200, response.text
    assert d.refresh()["current_state"] == "C16_COMPLETED"

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert connection.scalar(text("SELECT count(*) FROM memory_subjects")) > 0
        assert (
            connection.scalar(text("SELECT count(*) FROM memory_subjects WHERE batch_id IS NULL"))
            == 0
        )
        assert connection.scalar(text("SELECT count(*) FROM character_behavior_profiles")) == 0
        assert connection.scalar(text("SELECT count(*) FROM creative_explorations")) == 0
        command.downgrade(migration_config, "0017_memory_state_transitions")

        inspector = inspect(connection)
        quote = connection.dialect.identifier_preparer.quote
        historical = {
            name: {
                "columns": [c["name"] for c in inspector.get_columns(name)],
                "order": inspector.get_pk_constraint(name)["constrained_columns"],
            }
            for name in inspector.get_table_names()
            if name != "alembic_version"
        }

        def snapshot():
            return {
                name: connection.execute(
                    text(
                        "SELECT "
                        + ", ".join(quote(c) for c in shape["columns"])
                        + " FROM "
                        + quote(name)
                        + " ORDER BY "
                        + ", ".join(quote(c) for c in shape["order"])
                    )
                )
                .mappings()
                .all()
                for name, shape in historical.items()
            }

        before = snapshot()
        assert before["committed_memory"] and before["agent_runs"]
        assert before["prompt_lineages"] and before["context_packages"]
        command.upgrade(migration_config, "0018_creative_exploration")
        assert snapshot() == before
        command.upgrade(migration_config, "0019_character_behavior_profile")
        assert snapshot() == before
        subjects = (
            connection.execute(
                text(
                    "SELECT s.id, s.created_at, s.created_by, b.committed_at, b.confirmed_by "
                    "FROM memory_subjects s JOIN memory_commit_batches b ON b.id=s.batch_id "
                    "ORDER BY s.id"
                )
            )
            .mappings()
            .all()
        )
        assert len(subjects) == len(before["memory_subjects"])
        assert all(
            row["created_at"] == row["committed_at"]
            and row["created_by"] == row["confirmed_by"] == "local-user"
            for row in subjects
        )
        command.upgrade(migration_config, "0020_character_report_lineage")
        assert snapshot() == before
        command.downgrade(migration_config, "-1")
        assert snapshot() == before
        command.upgrade(migration_config, "head")
        assert snapshot() == before
        assert connection.execute(
            text("SELECT id, created_at, created_by FROM memory_subjects ORDER BY id")
        ).mappings().all() == [
            {key: row[key] for key in ("id", "created_at", "created_by")} for row in subjects
        ]
        command.check(migration_config)

    assert d.refresh()["current_state"] == "C16_COMPLETED"
    assert d.client.get(d.chapter_api).json()["status"] == "COMPLETED"
    history = d.read("/memory")[0]
    assert history["status"] == "COMMITTED"
    assert len(history["entries"]) == 7
