import pytest
from agent_test_support import worker
from sqlalchemy import inspect, select, text

from alembic import command
from novel_os.db.base import Base

pytestmark = pytest.mark.integration


def historical_snapshot(connection):
    return {
        name: connection.execute(
            select(
                *[
                    c
                    for c in table.c
                    if c.name
                    not in {
                        "revision_request_id",
                        "human_feedback_id",
                        "memory_request_id",
                        "report_character_id",
                    }
                ]
            ).order_by(*table.primary_key)
        )
        .mappings()
        .all()
        for name, table in Base.metadata.tables.items()
        if name
        not in {
            "human_feedback",
            "human_feedback_interpretations",
            "memory_requests",
            "memory_commit_proposals",
            "memory_commit_batches",
            "memory_subjects",
            "committed_memory",
            "creative_explorations",
            "character_behavior_profiles",
        }
        if name
        not in {"revision_requests", "revision_plans", "revision_results", "revision_candidates"}
        if name
        not in {"quality_review_bindings", "quality_review_passes", "chapter_quality_reviews"}
        if name
        not in {
            "prompt_lineages",
            "context_packages",
            "creative_briefs",
            "plan_generations",
            "plan_review_reports",
            "writing_task_bindings",
            "writing_generations",
            "project_writing_profiles",
        }
    }


def test_0006_roundtrip_preserves_all_existing_core_workflow_agent_and_audit_rows(
    driver, core_database, migration_config
):
    driver.event("USER_SUBMITTED")
    worker(core_database).run_once()
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        assert connection.scalar(text("SELECT count(*) FROM prompt_lineages")) == 1
        command.downgrade(migration_config, "0006_prompt_runtime")
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
            == "0022_feedback_before_review"
        )
        assert connection.scalar(text("SELECT count(*) FROM prompt_lineages")) == 0
        assert historical_snapshot(connection) == before
        command.check(migration_config)
    assert worker(core_database).run_once()
