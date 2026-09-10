from copy import deepcopy
from dataclasses import asdict, fields
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_os.domain import core as domain
from novel_os.domain.enums import ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.models import core as orm

MAPPINGS = {
    domain.Project: orm.ProjectModel,
    domain.Requirement: orm.RequirementModel,
    domain.Decision: orm.DecisionModel,
    domain.Chapter: orm.ChapterModel,
    domain.ChapterPlan: orm.ChapterPlanModel,
    domain.ChapterVersion: orm.ChapterVersionModel,
    domain.Lock: orm.LockModel,
    domain.AuditRecord: orm.AuditRecordModel,
}
VERSION_TYPES = {
    ObjectType.REQUIREMENT: domain.Requirement,
    ObjectType.DECISION: domain.Decision,
    ObjectType.CHAPTER_PLAN: domain.ChapterPlan,
    ObjectType.CHAPTER_VERSION: domain.ChapterVersion,
}


def to_domain(model, entity_type):
    return entity_type(
        **{
            field.name: deepcopy(
                getattr(model, "metadata_" if field.name == "metadata" else field.name)
            )
            for field in fields(entity_type)
        }
    )


class CoreRepository:
    """Explicit persistence operations; flush is allowed, commit/rollback are not."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity):
        values = asdict(entity)
        if "metadata" in values:
            values["metadata_"] = values.pop("metadata")
        if isinstance(entity, domain.Project):
            values.pop("project_id")
        self.session.add(MAPPINGS[type(entity)](**values))
        self.session.flush()
        return entity

    def save(self, entity):
        model = self.session.get(MAPPINGS[type(entity)], entity.id)
        if model is None:
            raise DomainError("NOT_FOUND", "Object not found")
        for name, value in asdict(entity).items():
            if name == "project_id" and isinstance(entity, domain.Project):
                continue
            setattr(model, "metadata_" if name == "metadata" else name, value)
        self.session.flush()
        return entity

    def get_project(self, project_id: UUID, *, for_update: bool = False) -> domain.Project:
        statement = select(orm.ProjectModel).where(orm.ProjectModel.id == project_id)
        if for_update:
            # All writes for a project take this row lock before checking any child.
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = self.session.scalar(statement)
        if row is None:
            raise DomainError("NOT_FOUND", "Project not found")
        return to_domain(row, domain.Project)

    def list_projects(self, limit: int, offset: int) -> list[domain.Project]:
        rows = self.session.scalars(
            select(orm.ProjectModel)
            .order_by(orm.ProjectModel.created_at, orm.ProjectModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, domain.Project) for row in rows]

    def get_chapter(self, project_id: UUID, chapter_id: UUID) -> domain.Chapter:
        row = self.session.scalar(
            select(orm.ChapterModel).where(
                orm.ChapterModel.project_id == project_id,
                orm.ChapterModel.id == chapter_id,
            )
        )
        if row is None:
            raise DomainError("NOT_FOUND", "Chapter not found")
        return to_domain(row, domain.Chapter)

    def list_chapters(self, project_id: UUID, limit: int, offset: int) -> list[domain.Chapter]:
        rows = self.session.scalars(
            select(orm.ChapterModel)
            .where(
                orm.ChapterModel.project_id == project_id,
            )
            .order_by(orm.ChapterModel.sequence)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, domain.Chapter) for row in rows]

    def chapter_sequence_exists(self, project_id: UUID, sequence: int) -> bool:
        return (
            self.session.scalar(
                select(orm.ChapterModel.id).where(
                    orm.ChapterModel.project_id == project_id,
                    orm.ChapterModel.sequence == sequence,
                )
            )
            is not None
        )

    def get_version(
        self, kind: ObjectType, project_id: UUID, logical_id: UUID, version: int | None = None
    ):
        entity_type = VERSION_TYPES[kind]
        model = MAPPINGS[entity_type]
        statement = select(model).where(
            model.project_id == project_id, model.logical_id == logical_id
        )
        if version is not None:
            statement = statement.where(model.version == version)
        row = self.session.scalar(statement.order_by(model.version.desc()).limit(1))
        if row is None:
            raise DomainError("NOT_FOUND", "Versioned object not found")
        return to_domain(row, entity_type)

    def list_versions(
        self,
        kind: ObjectType,
        project_id: UUID,
        logical_id: UUID | None,
        limit: int,
        offset: int,
        *,
        effective: bool = False,
    ):
        entity_type = VERSION_TYPES[kind]
        model = MAPPINGS[entity_type]
        statement = select(model).where(model.project_id == project_id)
        if logical_id is not None:
            statement = statement.where(model.logical_id == logical_id)
        if effective:
            statement = statement.where(
                model.status.in_([Status.APPROVED, Status.LOCKED]), model.approved_at.is_not(None)
            )
        if logical_id is None and not effective:
            statement = statement.distinct(model.logical_id).order_by(
                model.logical_id, model.version.desc()
            )
        else:
            statement = statement.order_by(model.created_at, model.version, model.id)
        rows = self.session.scalars(statement.limit(limit).offset(offset))
        return [to_domain(row, entity_type) for row in rows]

    def get_approved(self, kind: ObjectType, project_id: UUID, logical_id: UUID):
        rows = self.list_versions(kind, project_id, logical_id, 1, 0, effective=True)
        return rows[0] if rows else None

    def active_lock(self, project_id: UUID, target: domain.ObjectRef) -> domain.Lock | None:
        row = self.session.scalar(
            select(orm.LockModel).where(
                orm.LockModel.project_id == project_id,
                orm.LockModel.target_type == target.object_type,
                orm.LockModel.target_id == target.object_id,
                orm.LockModel.active.is_(True),
            )
        )
        return to_domain(row, domain.Lock) if row is not None else None

    def get_lock(self, project_id: UUID, lock_id: UUID) -> domain.Lock:
        row = self.session.scalar(
            select(orm.LockModel).where(
                orm.LockModel.project_id == project_id,
                orm.LockModel.id == lock_id,
            )
        )
        if row is None:
            raise DomainError("NOT_FOUND", "Lock not found")
        return to_domain(row, domain.Lock)

    def list_locks(self, project_id: UUID, limit: int, offset: int) -> list[domain.Lock]:
        rows = self.session.scalars(
            select(orm.LockModel)
            .where(
                orm.LockModel.project_id == project_id,
            )
            .order_by(orm.LockModel.created_at, orm.LockModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, domain.Lock) for row in rows]

    def list_audit(self, project_id: UUID, limit: int, offset: int) -> list[domain.AuditRecord]:
        rows = self.session.scalars(
            select(orm.AuditRecordModel)
            .where(
                orm.AuditRecordModel.project_id == project_id,
            )
            .order_by(orm.AuditRecordModel.created_at, orm.AuditRecordModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [to_domain(row, domain.AuditRecord) for row in rows]
