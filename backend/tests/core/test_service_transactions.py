from uuid import uuid4

import pytest
from sqlalchemy import text

from novel_os.domain.core import AuditRecord, CommandContext
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.domain.errors import DomainError
from novel_os.repositories.core import CoreRepository
from novel_os.services.projects import ChapterService, ProjectService
from novel_os.services.versioning import ChapterVersionService, RequirementService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "failing_action", [AuditAction.VERSION_CREATE, AuditAction.APPROVE, AuditAction.UPDATE]
)
def test_audit_failure_rolls_back_payload_pointer_and_supersession(
    core_database, monkeypatch, failing_action
):
    context = CommandContext("transaction", "test-user")
    with core_database.session() as session:
        project = ProjectService(session).create({"name": "Rollback"}, context)
        chapter = ChapterService(session).create(
            project.id, {"sequence": 1, "title": "First"}, context
        )
        service = ChapterVersionService(session)
        service.create_version(
            project.id, chapter.id, {"content": "v1", "change_reason": "Draft"}, 0, context, "Draft"
        )
        service.approve(project.id, chapter.id, 1, context, "Approve")
        if failing_action == AuditAction.APPROVE:
            service.create_version(
                project.id,
                chapter.id,
                {"content": "v2", "change_reason": "Draft"},
                1,
                context,
                "Draft",
            )

    def snapshot():
        with core_database.session() as session:
            repo = CoreRepository(session)
            chapter_row = repo.get_chapter(project.id, chapter.id)
            versions = repo.list_versions(
                ObjectType.CHAPTER_VERSION, project.id, chapter.id, 100, 0
            )
            audit = repo.list_audit(project.id, 100, 0)
            return chapter_row, versions, audit

    before = snapshot()
    original_add = CoreRepository.add

    def fail_audit(repository, entity):
        if isinstance(entity, AuditRecord) and entity.action == failing_action:
            raise RuntimeError("Simulated audit storage failure")
        return original_add(repository, entity)

    monkeypatch.setattr(CoreRepository, "add", fail_audit)
    with core_database.session() as session, pytest.raises(RuntimeError, match="audit storage"):
        service = ChapterVersionService(session)
        if failing_action == AuditAction.APPROVE:
            service.approve(project.id, chapter.id, 2, context, "Approve")
        else:
            service.create_version(
                project.id,
                chapter.id,
                {"content": "v2", "change_reason": "Draft"},
                1,
                context,
                "Draft",
            )
    assert snapshot() == before


@pytest.mark.parametrize("actor", [ActorType.AGENT, ActorType.SYSTEM])
def test_non_user_service_context_cannot_approve(core_database, actor):
    user = CommandContext("create", "test-user")
    with core_database.session() as session:
        project = ProjectService(session).create({"name": "Authority"}, user)
        requirement = RequirementService(session).create(project.id, {"content": "Must"}, user)
        with pytest.raises(DomainError) as error:
            RequirementService(session).approve(
                project.id,
                requirement.logical_id,
                1,
                CommandContext("fake", "fake-system", actor),
                "Bypass",
            )
        assert error.value.code == "AUTHORITY_DENIED"
    with core_database.session() as session:
        assert (
            session.scalar(text("SELECT count(*) FROM audit_records WHERE action='APPROVE'")) == 0
        )


def test_service_rejects_forged_metadata_fields(core_database):
    with core_database.session() as session, pytest.raises(DomainError) as error:
        ProjectService(session).create(
            {"name": "Bad", "status": "APPROVED"}, CommandContext(str(uuid4()), "test-user")
        )
    assert error.value.code == "VALIDATION_ERROR"
