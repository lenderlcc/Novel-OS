"""Temporary NOVEL-014 engineering verification; retained only as a local run artifact."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from novel_os.domain.core import CommandContext
from novel_os.domain.enums import ActorType, Authority, Status
from novel_os.domain.errors import DomainError
from novel_os.repositories.character_profiles import CharacterProfileRepository
from novel_os.services.character_profiles import CharacterProfileService


def character(client, project, name="A", aliases=None):
    response = client.post(project + "/characters", json={"name": name, "aliases": aliases or []})
    assert response.status_code == 201, response.text
    return response.json()


def profile_url(project, char):
    return project + "/characters/" + char["id"] + "/behavior-profile"


def draft(client, url, version=0, **profile):
    response = client.post(url + "/drafts", json={"expected_version": version, "profile": profile})
    assert response.status_code == 201, response.text
    return response.json()


def approve(client, url, version=1):
    response = client.post(url + "/approve", json={"expected_version": version})
    assert response.status_code == 200, response.text
    return response.json()


def test_manual_identity_keeps_memory_empty_and_has_provenance(core_client, project_api):
    a = character(core_client, project_api, "林遥", ["小林"])
    assert a["batch_id"] is None and a["created_at"] and a["created_by"] == "local-user"
    assert core_client.get(project_api + "/characters").json() == [a]
    assert core_client.get(project_api + "/memory").json() == []
    assert core_client.get(profile_url(project_api, a)).json() == dict(
        current=None, approved=None, current_profile_version=None, approved_profile_version=None
    )
    assert core_client.post(project_api + "/characters", json={"name": "小林"}).status_code == 409


def test_immutable_versions_exact_approval_distinct_pointers_and_audit(core_client, project_api):
    a = character(core_client, project_api)
    url = profile_url(project_api, a)
    v1 = draft(core_client, url, decision_tendency="Act then adjust", risk_tolerance="HIGH")
    assert v1["status"] == "DRAFT" and v1["authority_level"] == "A7_AI_INFERENCE"
    assert core_client.get(url + "/approved").json() is None
    a1 = approve(core_client, url)
    assert a1["authority_level"] == "A3_CANON" and a1["approved_at"]
    assert a1["profile_hash"] == v1["profile_hash"]
    v2 = draft(core_client, url, 1, decision_tendency="Ask then act")
    assert v2["supersedes_id"] == v1["id"]
    assert (
        v2["profile_id"]
        == v1["profile_id"]
        == str(uuid5(UUID(a["id"]), "character-behavior-profile"))
    )
    assert v2["profile_id"] != a["id"]
    state = core_client.get(url).json()
    assert (state["current_profile_version"], state["approved_profile_version"]) == (2, 1)
    assert state["approved"] == a1
    assert core_client.post(url + "/approve", json={"expected_version": 1}).status_code == 409
    a2 = approve(core_client, url, 2)
    history = core_client.get(url + "/versions").json()
    assert [v["status"] for v in history] == ["APPROVED", "SUPERSEDED"]
    assert history[1]["decision_tendency"] == "Act then adjust"
    assert a2["profile_hash"] == v2["profile_hash"] != a1["profile_hash"]
    audits = [
        r
        for r in core_client.get(project_api + "/audit").json()
        if "character_profile_id" in r["after"]
    ]
    assert sorted(r["action"] for r in audits) == [
        "APPROVE",
        "APPROVE",
        "SUPERSEDE",
        "VERSION_CREATE",
        "VERSION_CREATE",
    ]


@pytest.mark.parametrize("risk", ["MEDIUM_HIGH", 50, "aggressive"])
def test_invalid_risk_rejected(core_client, project_api, risk):
    url = profile_url(project_api, character(core_client, project_api))
    response = core_client.post(
        url + "/drafts", json={"expected_version": 0, "profile": {"risk_tolerance": risk}}
    )
    assert response.status_code == 422


def test_cross_project_character_and_relationship_rejected(core_client, project_api):
    a = character(core_client, project_api)
    b = character(core_client, project_api, "B")
    other = core_client.post("/api/v1/projects", json={"name": "Other"}).json()
    other_url = "/api/v1/projects/" + other["id"]
    c = character(core_client, other_url, "C")
    url = profile_url(project_api, a)
    assert core_client.get(profile_url(other_url, a)).status_code == 404
    assert (
        core_client.post(
            profile_url(other_url, a) + "/drafts", json={"expected_version": 0, "profile": {}}
        ).status_code
        == 404
    )
    for modifier in (c["id"], str(uuid4())):
        assert (
            core_client.post(
                url + "/drafts",
                json={
                    "expected_version": 0,
                    "profile": {"relationship_modifiers": [{"other_character_id": modifier}]},
                },
            ).status_code
            == 404
        )
    for modifiers in (
        [{"other_character_id": a["id"]}],
        [{"other_character_id": b["id"]}, {"other_character_id": b["id"]}],
    ):
        assert (
            core_client.post(
                url + "/drafts",
                json={"expected_version": 0, "profile": {"relationship_modifiers": modifiers}},
            ).status_code
            == 422
        )
    saved = draft(
        core_client,
        url,
        relationship_modifiers=[
            {"other_character_id": b["id"], "interaction_tendency": "Relaxes with B"}
        ],
    )
    assert saved["relationship_modifiers"][0]["other_character_id"] == b["id"]


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE character_behavior_profiles SET body = '{}'::jsonb",
        "UPDATE character_behavior_profiles SET version = 99",
        "UPDATE character_behavior_profiles SET authority_level = 'A2_USER_APPROVED'",
        "UPDATE character_behavior_profiles SET approved_by = 'forged'",
        "UPDATE character_behavior_profiles SET source_text = 'forged'",
        "DELETE FROM character_behavior_profiles",
        "UPDATE memory_subjects SET name = 'forged'",
        "DELETE FROM memory_subjects",
    ],
)
def test_database_history_immutable(core_client, project_api, core_database, sql):
    url = profile_url(project_api, character(core_client, project_api))
    draft(core_client, url, communication_style="Direct")
    approve(core_client, url)
    with pytest.raises(DBAPIError), core_database.engine.begin() as connection:
        connection.execute(text(sql))
    assert core_client.get(url + "/approved").json()["communication_style"] == "Direct"


@pytest.mark.parametrize("forgery", ["authority_level", "status", "source", "approved_by"])
def test_user_cannot_forge_approval(core_client, project_api, forgery):
    url = profile_url(project_api, character(core_client, project_api))
    for payload in (
        {"expected_version": 0, "profile": {}, forgery: "APPROVED"},
        {"expected_version": 0, "profile": {forgery: "APPROVED"}},
    ):
        assert core_client.post(url + "/drafts", json=payload).status_code == 422


@pytest.mark.parametrize("reason", ["   ", "bad\x00reason"])
def test_profile_command_reason_rejects_blank_or_null_bytes(core_client, project_api, reason):
    url = profile_url(project_api, character(core_client, project_api))
    rejected = core_client.post(
        url + "/drafts", json={"expected_version": 0, "profile": {}, "reason": reason}
    )
    assert rejected.status_code == 422
    assert core_client.get(url + "/versions").json() == []
    draft(core_client, url)
    rejected = core_client.post(url + "/approve", json={"expected_version": 1, "reason": reason})
    assert rejected.status_code == 422
    state = core_client.get(url).json()
    assert state["current"]["status"] == "DRAFT" and state["approved"] is None


def test_approved_query_draft_exclusion_and_supersession(core_client, project_api, core_database):
    a = character(core_client, project_api)
    b = character(core_client, project_api, "B")
    aurl, burl = profile_url(project_api, a), profile_url(project_api, b)
    draft(core_client, aurl)
    draft(core_client, burl)
    pid, aid, bid = UUID(project_api.split("/")[-1]), UUID(a["id"]), UUID(b["id"])
    with core_database.session() as session:
        assert CharacterProfileRepository(session).approved_for_characters(pid, [aid, bid]) == []
    approve(core_client, aurl)
    draft(core_client, aurl, 1, attention_bias="Doors")
    with core_database.session() as session:
        rows = CharacterProfileRepository(session).approved_for_characters(pid, [aid])
        assert (
            len(rows) == 1
            and rows[0].version == 1
            and rows[0].authority_level == Authority.A3_CANON
        )
    approve(core_client, aurl, 2)
    with core_database.session() as session:
        repo = CharacterProfileRepository(session)
        assert repo.get(pid, aid, version=1).status == Status.SUPERSEDED
        assert repo.approved_for_characters(pid, [aid])[0].version == 2
        assert repo.approved_for_characters(pid, [bid]) == []


def test_only_user_and_project_lock(core_client, project_api, core_database):
    a = character(core_client, project_api)
    url = profile_url(project_api, a)
    pid, aid = UUID(project_api.split("/")[-1]), UUID(a["id"])
    for actor in (ActorType.AGENT, ActorType.SYSTEM):
        with (
            core_database.session() as session,
            pytest.raises(DomainError, match="requires a user"),
        ):
            CharacterProfileService(session).create_draft(
                pid,
                aid,
                {},
                0,
                CommandContext(request_id="test", actor_id="agent", actor_type=actor),
                "test",
            )
    locked = core_client.post(
        project_api + "/locks",
        json={"target_type": "PROJECT", "target_id": str(pid), "expected_version": 1},
    )
    assert locked.status_code == 201
    assert (
        core_client.post(url + "/drafts", json={"expected_version": 0, "profile": {}}).status_code
        == 409
    )


def test_simultaneous_drafts_exact_version(core_client, project_api):
    url = profile_url(project_api, character(core_client, project_api))
    barrier = Barrier(2)

    def write():
        barrier.wait(timeout=5)
        return core_client.post(
            url + "/drafts", json={"expected_version": 0, "profile": {}}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: write(), range(2))) == [201, 409]


def test_repository_flush_and_approval_rollback(
    core_client, project_api, core_database, monkeypatch
):
    a = character(core_client, project_api)
    url = profile_url(project_api, a)
    draft(core_client, url)
    approve(core_client, url)
    draft(core_client, url, 1)
    pid, aid = UUID(project_api.split("/")[-1]), UUID(a["id"])
    with core_database.session() as session:
        repo = CharacterProfileRepository(session)
        v2 = repo.get(pid, aid)
        monkeypatch.setattr(session, "commit", lambda: pytest.fail("Repository committed"))
        repo.add(replace(v2, id=uuid4(), version=3, supersedes_id=v2.id))
        with core_database.engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT max(version) FROM character_behavior_profiles")) == 2
            )
        session.rollback()

    def fail(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(CharacterProfileService, "record_audit", fail)
    with core_database.session() as session, pytest.raises(RuntimeError, match="audit failure"):
        CharacterProfileService(session).approve(
            pid, aid, 2, CommandContext(request_id="test", actor_id="user"), "test"
        )
    assert core_client.get(url).json()["approved_profile_version"] == 1


def test_migration_roundtrip_and_metadata(
    core_client, project_api, core_database, migration_config
):
    with core_database.engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.downgrade(migration_config, "0018_creative_exploration")
        assert "character_behavior_profiles" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT count(*) FROM projects")) == 1
        command.upgrade(migration_config, "head")
        assert "character_behavior_profiles" in inspect(connection).get_table_names()
        command.check(migration_config)


def test_natural_language_interpretation_only_creates_draft(core_client, project_api, monkeypatch):
    from novel_os import runtime_factory
    from novel_os.agents.provider import MockModelProvider
    from novel_os.agents.runtime import AgentRuntime

    monkeypatch.setattr(
        runtime_factory, "build_agent_runtime", lambda settings: AgentRuntime(MockModelProvider())
    )
    url = profile_url(project_api, character(core_client, project_api))
    source = "他会先行动，真正害怕时会用玩笑掩饰。"
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": source})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["status"] == "DRAFT" and saved["authority_level"] == "A7_AI_INFERENCE"
    assert saved["source_text"] == source and saved["approved_at"] is None
    assert core_client.get(url + "/approved").json() is None
    assert core_client.get(project_api + "/memory").json() == []


def test_stale_interpretation_rejected_before_provider(core_client, project_api, monkeypatch):
    from novel_os import runtime_factory
    from novel_os.agents.runtime import AgentRuntime

    class NoCalls:
        def generate(self, request):
            pytest.fail("A stale version must not call a Provider")

    monkeypatch.setattr(
        runtime_factory, "build_agent_runtime", lambda settings: AgentRuntime(NoCalls())
    )
    url = profile_url(project_api, character(core_client, project_api))
    draft(core_client, url)
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    assert len(core_client.get(url + "/versions").json()) == 1


def test_profile_edit_during_interpretation_rejected_after_provider(
    core_client, project_api, monkeypatch
):
    from novel_os import runtime_factory
    from novel_os.agents.provider import MockModelProvider
    from novel_os.agents.runtime import AgentRuntime

    url = profile_url(project_api, character(core_client, project_api))

    class ConcurrentEdit(MockModelProvider):
        def generate(self, request):
            draft(core_client, url, decision_tendency="Manual edit during Provider IO")
            return super().generate(request)

    monkeypatch.setattr(
        runtime_factory, "build_agent_runtime", lambda settings: AgentRuntime(ConcurrentEdit())
    )
    response = core_client.post(url + "/interpret", json={"expected_version": 0, "text": "Direct"})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"
    history = core_client.get(url + "/versions").json()
    assert len(history) == 1 and history[0]["decision_tendency"] == "Manual edit during Provider IO"
