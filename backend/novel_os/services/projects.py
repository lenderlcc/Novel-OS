from dataclasses import replace
from uuid import UUID, uuid4

from novel_os.domain.core import (
    MAX_CHAPTER_SEQUENCE,
    Chapter,
    CommandContext,
    Project,
    VersionToken,
    now,
)
from novel_os.domain.enums import AuditAction, Status
from novel_os.domain.errors import DomainError
from novel_os.services.core_base import CoreService, validate_payload


class ProjectService(CoreService):
    def create(self, payload: dict, context: CommandContext) -> Project:
        context.require_user()
        validate_payload(payload, {"name", "description", "tags", "metadata"}, ("name",))
        with self.session.begin():
            project_id = uuid4()
            project = self.repo.add(
                Project(
                    id=project_id, project_id=project_id, created_by=context.actor_id, **payload
                )
            )
            self.audit(project, AuditAction.CREATE, context, "Create project")
            return project

    def get(self, project_id: UUID) -> Project:
        return self.repo.get_project(project_id)

    def list(self, limit: int = 100, offset: int = 0) -> list[Project]:
        return self.repo.list_projects(limit, offset)

    def update(
        self,
        project_id: UUID,
        payload: dict,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ) -> Project:
        validate_payload(payload, {"name", "description", "tags", "metadata"})
        if "name" in payload:
            validate_payload(payload, set(payload), ("name",))
        with self.mutation(project_id, context) as project:
            VersionToken(expected_version).check(project.version)
            updated = self.repo.save(
                replace(project, **payload, version=project.version + 1, updated_at=now())
            )
            self.audit(updated, AuditAction.UPDATE, context, reason, project)
            return updated

    def archive(
        self, project_id: UUID, expected_version: int, context: CommandContext, reason: str
    ) -> Project:
        with self.mutation(project_id, context) as project:
            VersionToken(expected_version).check(project.version)
            updated = self.repo.save(
                replace(
                    project, status=Status.ARCHIVED, version=project.version + 1, updated_at=now()
                )
            )
            self.audit(updated, AuditAction.ARCHIVE, context, reason, project)
            return updated


class ChapterService(CoreService):
    def create(self, project_id: UUID, payload: dict, context: CommandContext) -> Chapter:
        validate_payload(payload, {"sequence", "title", "tags", "metadata"}, ("title",))
        sequence = payload.get("sequence")
        if type(sequence) is not int or not 1 <= sequence <= MAX_CHAPTER_SEQUENCE:
            raise DomainError("VALIDATION_ERROR", "Chapter sequence is outside the supported range")
        with self.mutation(project_id, context):
            if self.repo.chapter_sequence_exists(project_id, payload["sequence"]):
                raise DomainError("DUPLICATE_CHAPTER_SEQUENCE", "Chapter sequence already exists")
            chapter = self.repo.add(
                Chapter(project_id=project_id, created_by=context.actor_id, **payload)
            )
            self.audit(chapter, AuditAction.CREATE, context, "Create chapter")
            return chapter

    def get(self, project_id: UUID, chapter_id: UUID) -> Chapter:
        self.repo.get_project(project_id)
        return self.repo.get_chapter(project_id, chapter_id)

    def list(self, project_id: UUID, limit: int = 100, offset: int = 0) -> list[Chapter]:
        self.repo.get_project(project_id)
        return self.repo.list_chapters(project_id, limit, offset)
