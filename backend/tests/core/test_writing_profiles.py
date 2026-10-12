from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from novel_os.db.base import Base
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType
from novel_os.domain.errors import DomainError
from novel_os.repositories.writing_profiles import WritingProfileRepository
from novel_os.services.writing_profiles import WritingProfileService


def draft(client, project, version=0, **preferences):
    response = client.post(
        project + "/writing-profile/drafts",
        json={
            "expected_version": version,
            "preferences": preferences,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve(client, project, version=1):
    response = client.post(project + "/writing-profile/approve", json={"expected_version": version})
    assert response.status_code == 200, response.text
    return response.json()


def test_profile_lifecycle_exact_approval_and_audit(core_client, project_api):
    url = project_api + "/writing-profile"
    assert core_client.get(url).json() == dict(
        current=None, approved=None, current_profile_version=None, approved_profile_version=None
    )
    v1 = draft(core_client, project_api, target_audience="悬疑读者", pacing="FAST")
    assert v1["status"] == "DRAFT"
    assert core_client.get(url + "/approved").json() is None
    a1 = approve(core_client, project_api)
    assert a1["authority_level"] == "A5_USER_PREFERENCE" and a1["approved_at"]
    assert a1["profile_hash"] == v1["profile_hash"]
    v2 = draft(core_client, project_api, 1, target_audience="其他读者", pacing="SLOW")
    state = core_client.get(url).json()
    assert (state["current_profile_version"], state["approved_profile_version"]) == (2, 1)
    assert state["approved"] == a1
    stale = core_client.post(url + "/approve", json={"expected_version": 1})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    a2 = approve(core_client, project_api, 2)
    history = core_client.get(url + "/versions").json()
    assert [v["status"] for v in history] == ["APPROVED", "SUPERSEDED"]
    assert history[1]["target_audience"] == "悬疑读者"
    assert a2["profile_hash"] == v2["profile_hash"] != a1["profile_hash"]
    audits = [
        r
        for r in core_client.get(project_api + "/audit").json()
        if "writing_profile_id" in r["after"]
    ]
    assert sorted(r["action"] for r in audits) == [
        "APPROVE",
        "APPROVE",
        "SUPERSEDE",
        "VERSION_CREATE",
        "VERSION_CREATE",
    ]
    assert all(r["after"]["authority_level"] == "A5_USER_PREFERENCE" for r in audits)


@pytest.mark.parametrize(
    "forgery", ["status", "authority_level", "approved_at", "source", "version", "actor"]
)
def test_client_cannot_assign_profile_authority(core_client, project_api, forgery):
    for body in (
        {"expected_version": 0, "preferences": {}, forgery: "APPROVED"},
        {"expected_version": 0, "preferences": {forgery: "APPROVED"}},
    ):
        assert (
            core_client.post(project_api + "/writing-profile/drafts", json=body).status_code == 422
        )
    assert core_client.get(project_api + "/writing-profile/versions").json() == []


def test_project_isolation_and_project_lock(core_client, project_api):
    foreign = core_client.post("/api/v1/projects", json={"name": "Other"}).json()
    other = "/api/v1/projects/" + foreign["id"]
    draft(core_client, project_api, target_audience="private audience")
    approve(core_client, project_api)
    assert core_client.get(other + "/writing-profile/versions").json() == []
    assert (
        core_client.post(
            other + "/writing-profile/approve", json={"expected_version": 1}
        ).status_code
        == 409
    )
    locked = core_client.post(
        project_api + "/locks",
        json={
            "target_type": "PROJECT",
            "target_id": project_api.split("/")[-1],
            "expected_version": 1,
        },
    )
    assert locked.status_code == 201
    for suffix, body in (
        ("drafts", {"expected_version": 1, "preferences": {}}),
        ("approve", {"expected_version": 1}),
    ):
        result = core_client.post(project_api + "/writing-profile/" + suffix, json=body)
        assert result.status_code == 409 and result.json()["error"]["code"] == "LOCKED_OBJECT"


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE project_writing_profiles SET preferences = '{}'::jsonb",
        "UPDATE project_writing_profiles SET version = 99",
        "UPDATE project_writing_profiles SET authority_level = 'A2_USER_APPROVED'",
        "UPDATE project_writing_profiles SET approved_by = 'forged'",
        "DELETE FROM project_writing_profiles",
    ],
)
def test_profile_history_database_immutable(core_client, project_api, core_database, sql):
    draft(core_client, project_api, target_audience="original")
    approve(core_client, project_api)
    with pytest.raises(DBAPIError), core_database.engine.begin() as connection:
        connection.execute(text(sql))
    assert (
        core_client.get(project_api + "/writing-profile/approved").json()["target_audience"]
        == "original"
    )


def test_profile_repository_flush_and_service_rollback(
    core_client, project_api, core_database, monkeypatch
):
    draft(core_client, project_api, target_audience="v1")
    approve(core_client, project_api)
    draft(core_client, project_api, 1, target_audience="v2")
    project_id = UUID(project_api.split("/")[-1])
    with core_database.session() as session:
        repo = WritingProfileRepository(session)
        v2 = repo.get(project_id)
        monkeypatch.setattr(session, "commit", lambda: pytest.fail("Repository committed"))
        repo.add(replace(v2, id=UUID(int=123), version=3))
        with core_database.engine.connect() as connection:
            assert connection.scalar(text("SELECT max(version) FROM project_writing_profiles")) == 2
        session.rollback()

    def fail(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(WritingProfileService, "record_audit", fail)
    with core_database.session() as session, pytest.raises(RuntimeError, match="audit failure"):
        WritingProfileService(session).approve(
            project_id, 2, CommandContext(request_id="test", actor_id="user"), "test"
        )
    state = core_client.get(project_api + "/writing-profile").json()
    assert state["approved_profile_version"] == 1 and state["current"]["status"] == "DRAFT"


def test_only_user_can_save_or_approve_profile(core_database, project_api):
    project_id = UUID(project_api.split("/")[-1])
    for actor in (ActorType.AGENT, ActorType.SYSTEM):
        with (
            core_database.session() as session,
            pytest.raises(DomainError, match="requires a user"),
        ):
            WritingProfileService(session).create_draft(
                project_id,
                {},
                0,
                CommandContext(request_id="test", actor_id="agent", actor_type=actor),
                "test",
            )


def test_two_simultaneous_drafts_allocate_one_next_version(core_client, project_api):
    barrier = Barrier(2)

    def write():
        barrier.wait(timeout=5)
        return core_client.post(
            project_api + "/writing-profile/drafts",
            json={
                "expected_version": 0,
                "preferences": {"target_audience": "test"},
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: write(), range(2)))
    assert sorted(results) == [201, 409]
    assert len(core_client.get(project_api + "/writing-profile/versions").json()) == 1


def test_0010_roundtrip_preserves_prior_data(
    core_client, project_api, core_database, migration_config
):
    draft(core_client, project_api, target_audience="migration fixture")
    approve(core_client, project_api)

    def snapshot(connection):
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
                            "creative_exploration_id",
                            "selected_candidate_id",
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
            not in {
                "revision_requests",
                "revision_plans",
                "revision_results",
                "revision_candidates",
            }
            if name
            not in {"quality_review_bindings", "quality_review_passes", "chapter_quality_reviews"}
            if name != "project_writing_profiles"
        }

    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0010_project_writing_profile")
        before = snapshot(connection)
        command.downgrade(migration_config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0009_writing_agent"
        )
        assert "project_writing_profiles" not in inspect(connection).get_table_names()
        assert snapshot(connection) == before
        command.upgrade(migration_config, "head")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0022_feedback_before_review"
        )
        assert snapshot(connection) == before
        assert connection.scalar(text("SELECT count(*) FROM project_writing_profiles")) == 0
        command.check(migration_config)
