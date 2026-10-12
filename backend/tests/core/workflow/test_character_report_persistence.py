"""Standalone reports preserve the existing execution scope and historical evidence."""

from dataclasses import asdict, replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from novel_os.domain.agents import AgentId, AgentRun, AgentTask, TaskStatus
from novel_os.domain.core import now
from novel_os.domain.prompts import PromptLineage
from novel_os.domain.workflow import ChapterState
from novel_os.models.agents import AgentTaskModel
from novel_os.models.context import ContextPackageModel
from novel_os.repositories.agent_tasks import AgentTaskRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.agent_queue import AgentQueue


def character(client, project, name):
    response = client.post(project + "/characters", json={"name": name})
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


def report(project_id, character_id, **changes):
    task = AgentTask(
        project_id=project_id,
        workflow_instance_id=None,
        workflow_state=None,
        workflow_state_version=None,
        agent_id=AgentId.A02_REQUIREMENT,
        task_type="INTERPRET_CHARACTER_PROFILE",
        objective="Interpret explicit user character description",
        target_ref=None,
        report_character_id=character_id,
        capabilities=["REPORT_RESULT"],
        expected_output_schema="character-profile-draft.v1",
        max_attempts=1,
    )
    return replace(task, **changes)


def test_database_rejects_partial_scope_and_report_authority_deviations(
    driver, core_database, project_api
):
    pid = UUID(driver.creation["project_id"])
    cid = character(driver.client, project_api, "Mira")
    task = report(pid, cid)
    invalid = [
        {"workflow_instance_id": UUID(driver.workflow["id"])},
        {"workflow_state": ChapterState.C01_REQUIREMENT_INTAKE},
        {"workflow_state_version": 1},
        {"target_ref": UUID(driver.creation["chapter_id"])},
        {"report_character_id": None},
        {"task_type": "PARSE_CHAPTER_REQUIREMENT"},
        {"agent_id": AgentId.A07_MEMORY},
        {"capabilities": []},
        {"capabilities": ["REPORT_RESULT", "COMMIT_CANON"]},
        {"expected_output_schema": "chapter-memory-result.v2"},
        {"max_attempts": 2},
        {
            "workflow_instance_id": UUID(driver.workflow["id"]),
            "workflow_state": ChapterState.C01_REQUIREMENT_INTAKE,
            "workflow_state_version": 1,
            "target_ref": UUID(driver.creation["chapter_id"]),
            "report_character_id": None,
        },
    ]
    with core_database.session() as session, session.begin():
        repo = AgentTaskRepository(session)
        for changes in invalid:
            with pytest.raises(IntegrityError) as failure, session.begin_nested():
                repo.add(replace(task, task_id=uuid4(), **changes))
            assert failure.value.orig.diag.constraint_name == "ck_agent_tasks_execution_scope"
        repo.add(task)
        assert repo.get(task.task_id) == task


def test_report_character_fk_rejects_another_project(core_client, project_api, core_database):
    pid = UUID(project_api.rsplit("/", 1)[1])
    other = core_client.post("/api/v1/projects", json={"name": "Other"}).json()
    foreign = character(core_client, "/api/v1/projects/" + other["id"], "Jun")
    with (
        pytest.raises(IntegrityError) as failure,
        core_database.session() as session,
        session.begin(),
    ):
        AgentTaskRepository(session).add(report(pid, foreign))
    assert failure.value.orig.diag.constraint_name == (
        "fk_agent_tasks_report_character_id_memory_subjects"
    )


def test_background_queue_never_claims_pending_or_expired_explicit_reports(
    driver, core_database, project_api
):
    assert driver.event("USER_SUBMITTED").status_code == 200
    pid = UUID(driver.creation["project_id"])
    cid = character(driver.client, project_api, "Mira")
    expired = now() - timedelta(minutes=1)
    tasks = [
        report(pid, cid, priority=100),
        report(
            pid,
            cid,
            priority=100,
            status=TaskStatus.CLAIMED,
            attempt_count=1,
            claimed_at=expired,
            lease_owner="explicit-user",
            lease_token=uuid4(),
            lease_expires_at=expired,
            heartbeat_at=expired,
        ),
    ]
    with core_database.session() as session, session.begin():
        repo = AgentTaskRepository(session)
        for task in tasks:
            repo.add(task)
    with core_database.session() as session:
        lease = AgentQueue(session).claim("background-worker")
        assert lease is not None
        claimed = AgentTaskRepository(session).get(lease.task_id)
        assert claimed.workflow_instance_id == UUID(driver.workflow["id"])
        assert claimed.report_character_id is None
    with core_database.session() as session:
        assert AgentQueue(session).claim("background-worker") is None
        repo = AgentTaskRepository(session)
        assert [repo.get(task.task_id) for task in tasks] == tasks


def test_report_history_api_is_scoped_paginated_and_exposes_nullable_binding(
    core_client, project_api, core_database
):
    pid = UUID(project_api.rsplit("/", 1)[1])
    mira = character(core_client, project_api, "Mira")
    jun = character(core_client, project_api, "Jun")
    older = report(pid, mira, created_at=now() - timedelta(seconds=1))
    latest = report(pid, mira)
    with core_database.session() as session, session.begin():
        repo = AgentTaskRepository(session)
        for task in (older, latest, report(pid, jun)):
            repo.add(task)
    url = project_api + f"/characters/{mira}/behavior-profile/interpretations"
    response = core_client.get(url, params={"limit": 1, "offset": 1})
    assert response.status_code == 200, response.text
    assert [row["task_id"] for row in response.json()] == [str(older.task_id)]
    assert core_client.get(f"/api/v1/agent-tasks/{latest.task_id}/context").status_code == 404
    row = core_client.get("/api/v1/agent-tasks/" + str(latest.task_id)).json()
    assert row["report_character_id"] == str(mira)
    assert all(
        row[key] is None
        for key in (
            "workflow_instance_id",
            "workflow_state",
            "workflow_state_version",
            "target_ref",
        )
    )
    assert "lease_token" not in row
    other = core_client.post("/api/v1/projects", json={"name": "Other"}).json()
    wrong_scope = url.replace(str(pid), other["id"])
    assert core_client.get(wrong_scope).status_code == 404
    assert core_client.get(url.replace(str(mira), str(uuid4()))).status_code == 404
    assert core_client.get(url, params={"limit": 0}).status_code == 422


def test_0020_roundtrip_preserves_existing_chapter_tasks(driver, core_database, migration_config):
    assert driver.event("USER_SUBMITTED").status_code == 200
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection

        def snapshot():
            return (
                connection.execute(
                    select(
                        *[c for c in AgentTaskModel.__table__.c if c.name != "report_character_id"]
                    ).order_by(AgentTaskModel.task_id)
                )
                .mappings()
                .all()
            )

        original = snapshot()
        assert len(original) == 1
        command.downgrade(migration_config, "0019_character_behavior_profile")
        columns = {c["name"]: c for c in inspect(connection).get_columns("agent_tasks")}
        assert "report_character_id" not in columns
        assert all(
            not columns[name]["nullable"]
            for name in (
                "workflow_instance_id",
                "workflow_state",
                "workflow_state_version",
                "target_ref",
            )
        )
        assert snapshot() == original
        command.upgrade(migration_config, "head")
        assert snapshot() == original
        command.check(migration_config)


def test_0020_downgrade_refuses_and_preserves_report_execution_evidence(
    core_client, project_api, core_database, migration_config
):
    pid = UUID(project_api.rsplit("/", 1)[1])
    cid = character(core_client, project_api, "Mira")
    task = report(pid, cid)
    run = AgentRun(
        task_id=task.task_id, attempt_number=1, worker_id="explicit-user", lease_token=uuid4()
    )
    with core_database.session() as session, session.begin():
        repo = AgentTaskRepository(session)
        repo.add(task)
        repo.add(run)
        PromptLineageRepository(session).add(
            PromptLineage(
                agent_run_id=run.run_id,
                task_id=task.task_id,
                system_policy={},
                agent_role={},
                task_template={},
                skills=[],
                quality_profile={},
                output_schema_id="character-profile-draft",
                output_schema_version=1,
                output_schema_hash="a" * 64,
                model_profile_id="mock-default",
                model_profile_hash="b" * 64,
                model_profile={},
                compiled_prompt_hash="c" * 64,
            )
        )
        session.add(
            ContextPackageModel(
                context_package_id=uuid4(),
                agent_run_id=run.run_id,
                task_id=task.task_id,
                profile_id="CP-010",
                profile_version=1,
                profile_hash="d" * 64,
                package_hash="e" * 64,
                build_status="READY",
                snapshot={},
                created_at=now(),
            )
        )
    with (
        pytest.raises(DBAPIError, match="Export standalone character report execution history"),
        core_database.engine.begin() as connection,
    ):
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0019_character_behavior_profile")
    with core_database.engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0022_feedback_before_review"
        )
        for table in ("agent_tasks", "agent_runs", "prompt_lineages", "context_packages"):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1
    with core_database.session() as session:
        assert asdict(AgentTaskRepository(session).get(task.task_id)) == asdict(task)
