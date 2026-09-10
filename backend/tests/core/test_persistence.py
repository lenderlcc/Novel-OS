from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from novel_os.domain.core import CommandContext, ObjectRef, Project
from novel_os.domain.enums import ObjectType
from novel_os.models.core import ChapterVersionModel, ProjectModel
from novel_os.repositories.core import CoreRepository
from novel_os.services.locks import LockService
from novel_os.services.projects import ChapterService, ProjectService
from novel_os.services.versioning import (
    ChapterVersionService,
    DecisionService,
    PlanningService,
    RequirementService,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def seed(core_database):
    context = CommandContext("persistence-seed", "test-user")
    with core_database.session() as session:
        project = ProjectService(session).create({"name": "Persistence"}, context)
        requirement = RequirementService(session).create(project.id, {"content": "Must"}, context)
        RequirementService(session).approve(
            project.id, requirement.logical_id, 1, context, "Approve"
        )
        decision = DecisionService(session).create(
            project.id, {"question": "Why?", "decision": "Yes"}, context
        )
        chapter = ChapterService(session).create(
            project.id, {"sequence": 1, "title": "First"}, context
        )
        plan = PlanningService(session).create_version(
            project.id,
            chapter.id,
            {
                "objective": "Meet",
                "required_outcome": "Discover",
            },
            0,
            context,
            "Plan",
        )
        version = ChapterVersionService(session).create_version(
            project.id,
            chapter.id,
            {
                "content": "Original text",
                "change_reason": "Draft",
            },
            0,
            context,
            "Draft",
        )
        lock = LockService(session).create(
            project.id, ObjectRef(ObjectType.DECISION, decision.logical_id), 1, context, "Keep"
        )
    return {
        "projects": project,
        "requirements": requirement,
        "decisions": decision,
        "chapters": chapter,
        "chapter_plans": plan,
        "chapter_versions": version,
        "locks": lock,
    }


@pytest.mark.parametrize("mode", ["sql", "orm"])
def test_chapter_version_content_is_immutable_even_before_approval(core_database, seed, mode):
    version = seed["chapter_versions"]
    with core_database.session() as session, pytest.raises(IntegrityError):
        if mode == "sql":
            session.execute(
                text("UPDATE chapter_versions SET content = :value WHERE id = :id"),
                {"value": "Overwrite", "id": version.id},
            )
        else:
            row = session.get(ChapterVersionModel, version.id)
            row.content = "Overwrite"
            session.flush()
    with core_database.session() as session:
        assert session.get(ChapterVersionModel, version.id).content == "Original text"


@pytest.mark.parametrize("table,column", [("requirements", "content"), ("decisions", "decision")])
def test_approved_or_locked_payload_has_database_guard(core_database, seed, table, column):
    with core_database.session() as session, pytest.raises(IntegrityError):
        session.execute(
            text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
            {"value": "Overwrite", "id": seed[table].id},
        )


@pytest.mark.parametrize("transition", ["approve", "lock"])
def test_approval_or_lock_cannot_change_payload_in_same_statement(core_database, transition):
    context = CommandContext("transition-guard", "test-user")
    with core_database.session() as session:
        project = ProjectService(session).create({"name": "Guard"}, context)
        if transition == "approve":
            record = RequirementService(session).create(project.id, {"content": "Keep"}, context)
            sql = """UPDATE requirements SET content = 'Changed', status = 'APPROVED',
                     authority_level = 'A2_USER_APPROVED', approved_by = 'test-user',
                     approved_at = now() WHERE id = :id"""
        else:
            record = DecisionService(session).create(
                project.id, {"question": "Voice?", "decision": "Keep"}, context
            )
            sql = """UPDATE decisions SET decision = 'Changed', status = 'LOCKED',
                     authority_level = 'A1_USER_LOCKED', locked = true WHERE id = :id"""
    with pytest.raises(IntegrityError), core_database.session() as session:
        session.execute(text(sql), {"id": record.id})
        session.commit()
    with core_database.session() as session:
        assert (
            CoreRepository(session).get_version(record.object_type, project.id, record.logical_id)
            == record
        )


@pytest.mark.parametrize(
    "table",
    [
        "projects",
        "requirements",
        "decisions",
        "chapters",
        "chapter_plans",
        "chapter_versions",
        "locks",
        "audit_records",
    ],
)
def test_core_records_cannot_be_hard_deleted(core_database, seed, table):
    with core_database.session() as session, pytest.raises(IntegrityError):
        session.execute(text(f"DELETE FROM {table}"))


def test_audit_is_append_only(core_database, seed):
    with core_database.session() as session, pytest.raises(IntegrityError):
        session.execute(text("UPDATE audit_records SET reason = 'Rewritten'"))


def test_active_lock_and_version_numbers_are_unique(core_database, seed):
    with core_database.session() as session, pytest.raises(IntegrityError):
        CoreRepository(session).add(replace(seed["locks"], id=uuid4()))
    with core_database.session() as session, pytest.raises(IntegrityError):
        CoreRepository(session).add(replace(seed["chapter_versions"], id=uuid4()))


def test_chapter_pointer_must_reference_its_own_existing_version(core_database, seed):
    with pytest.raises(IntegrityError), core_database.engine.begin() as connection:
        connection.execute(
            text("UPDATE chapters SET approved_version = 999 WHERE id = :id"),
            {"id": seed["chapters"].id},
        )


def test_repository_does_not_commit_and_returns_domain_snapshots(core_database, monkeypatch):
    project_id = uuid4()
    entity = Project(id=project_id, project_id=project_id, name="Uncommitted", created_by="test")
    with core_database.session() as session:
        monkeypatch.setattr(session, "commit", lambda: pytest.fail("Repository attempted commit"))
        repository = CoreRepository(session)
        repository.add(entity)
        assert isinstance(repository.get_project(project_id), Project)
        assert session.in_transaction()
        with core_database.session() as observer:
            assert (
                observer.scalar(select(ProjectModel.id).where(ProjectModel.id == project_id))
                is None
            )
    with core_database.session() as observer:
        assert observer.get(ProjectModel, project_id) is None
