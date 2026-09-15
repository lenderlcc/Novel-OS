"""Exact/structured context reads. Never infer an artifact version from its maximum."""

from sqlalchemy import String, and_, cast, func, literal_column, or_, select

from novel_os.domain.context import ContextScope, SourceType, VersionPolicy
from novel_os.domain.core import Chapter, ChapterPlan, ChapterVersion, Decision, Lock, Requirement
from novel_os.domain.enums import ObjectType, ScopeType, Status
from novel_os.models.core import (
    ChapterModel,
    ChapterPlanModel,
    ChapterVersionModel,
    DecisionModel,
    LockModel,
    RequirementModel,
)
from novel_os.repositories.core import CoreRepository, to_domain


class ContextSourceRepository:
    def __init__(self, session):
        self.session = session
        self.core = CoreRepository(session)

    def chapter(self, project_id, chapter_id):
        return self.core.get_chapter(project_id, chapter_id)

    def previous(self, project_id, sequence):
        row = self.session.scalar(
            select(ChapterModel)
            .where(
                ChapterModel.project_id == project_id,
                ChapterModel.sequence < sequence,
                ChapterModel.approved_version.is_not(None),
                ChapterModel.status.not_in([Status.ARCHIVED, Status.CANCELLED, Status.DEPRECATED]),
            )
            .order_by(ChapterModel.sequence.desc())
            .limit(1)
        )
        return to_domain(row, Chapter) if row else None

    def artifact(self, source_type, project_id, chapter_id, version):
        if version is None:
            return None
        model, domain = (
            (ChapterPlanModel, ChapterPlan)
            if source_type == SourceType.CHAPTER_PLAN
            else (ChapterVersionModel, ChapterVersion)
        )
        row = self.session.scalar(
            select(model).where(
                model.project_id == project_id,
                model.chapter_id == chapter_id,
                model.version == version,
            )
        )
        return to_domain(row, domain) if row else None

    def lock(self, project_id, kind, logical_id):
        from novel_os.domain.core import ObjectRef

        return self.core.active_lock(project_id, ObjectRef(ObjectType(kind), logical_id))

    def effective(self, source_type, request, selector, timestamp):
        model, domain = (
            (RequirementModel, Requirement)
            if source_type == SourceType.REQUIREMENT
            else (DecisionModel, Decision)
        )
        statement = select(model).where(model.project_id == request.project_id)
        locked = (
            select(LockModel.id)
            .where(
                LockModel.project_id == request.project_id,
                LockModel.target_type == ObjectType(source_type),
                LockModel.target_id == model.logical_id,
                LockModel.target_version == model.version,
                LockModel.active.is_(True),
            )
            .exists()
        )
        explicit = selector.scope == ContextScope.EXPLICIT
        if explicit:
            refs = [ref for ref in request.explicit_refs if ref.source_type == source_type]
            if not refs:
                return ()
            statement = statement.where(
                or_(
                    *(
                        and_(model.logical_id == ref.logical_id, model.version == ref.version)
                        for ref in refs
                    )
                )
            )
        if selector.version_policy == VersionPolicy.LOCKED:
            statement = statement.where(model.status == Status.LOCKED, locked)
        elif selector.version_policy in {VersionPolicy.APPROVED, VersionPolicy.EFFECTIVE}:
            statement = statement.where(
                or_(
                    and_(model.status == Status.APPROVED, model.approved_at.is_not(None)),
                    and_(model.status == Status.LOCKED, locked),
                )
            )
            if selector.version_policy == VersionPolicy.APPROVED:
                statement = statement.where(model.approved_at.is_not(None))
        elif selector.version_policy in {VersionPolicy.EXACT, VersionPolicy.TARGET_VERSION}:
            refs = [ref for ref in request.explicit_refs if ref.source_type == source_type]
            if not refs:
                return ()
            statement = statement.where(
                or_(
                    *(
                        and_(model.logical_id == ref.logical_id, model.version == ref.version)
                        for ref in refs
                    )
                )
            )
        else:
            raise ValueError("CURRENT requires a domain pointer; proposal records have none")
        if source_type == SourceType.REQUIREMENT and not explicit:
            statement = statement.where(
                or_(
                    and_(
                        model.scope_type == ScopeType.PROJECT, model.scope_id == request.project_id
                    ),
                    and_(
                        model.scope_type == ScopeType.CHAPTER, model.scope_id == request.chapter_id
                    ),
                ),
                or_(model.effective_from.is_(None), model.effective_from <= timestamp),
                or_(model.effective_until.is_(None), model.effective_until > timestamp),
            )
            if selector.requirement_types:
                statement = statement.where(model.requirement_type.in_(selector.requirement_types))
        elif source_type == SourceType.DECISION and not explicit:
            requirement_ref = func.jsonb_build_array(
                func.jsonb_build_object(
                    literal_column("'object_type'"),
                    literal_column("'REQUIREMENT'"),
                    literal_column("'object_id'"),
                    cast(RequirementModel.logical_id, String),
                )
            )
            related_requirement = (
                select(RequirementModel.id)
                .where(
                    RequirementModel.project_id == request.project_id,
                    RequirementModel.scope_id.in_([request.project_id, request.chapter_id]),
                    RequirementModel.status.in_([Status.APPROVED, Status.LOCKED]),
                    model.affected_objects.contains(requirement_ref),
                )
                .exists()
            )
            refs = [
                {"object_type": "PROJECT", "object_id": str(request.project_id)},
                *(
                    {"object_type": kind, "object_id": str(request.chapter_id)}
                    for kind in ("CHAPTER", "CHAPTER_PLAN", "CHAPTER_VERSION")
                ),
            ]
            statement = statement.where(
                or_(
                    model.affected_objects == [],
                    related_requirement,
                    *(model.affected_objects.contains([ref]) for ref in refs),
                )
            )
        rows = self.session.scalars(
            statement.order_by(
                model.authority_level,
                model.updated_at.desc(),
                model.logical_id,
                model.version,
                model.id,
            ).limit(selector.max_items + 1)
        )
        return tuple(to_domain(row, domain) for row in rows)

    def dependency_chapter(self, source_type, record):
        ids = []
        if source_type == SourceType.REQUIREMENT and record.scope_type == ScopeType.CHAPTER:
            ids = [record.scope_id]
        elif source_type == SourceType.DECISION:
            ids = [
                ref["object_id"]
                for ref in record.affected_objects
                if ref.get("object_type") in {"CHAPTER", "CHAPTER_PLAN", "CHAPTER_VERSION"}
            ]
        if not ids:
            return None
        row = self.session.scalar(
            select(ChapterModel)
            .where(ChapterModel.project_id == record.project_id, ChapterModel.id.in_(ids))
            .order_by(ChapterModel.sequence.desc())
            .limit(1)
        )
        return to_domain(row, Chapter) if row else None

    def locks(self, request, selector):
        rows = self.session.scalars(
            select(LockModel)
            .where(
                LockModel.project_id == request.project_id,
                LockModel.active.is_(True),
                LockModel.target_id.in_(
                    [
                        request.project_id,
                        request.chapter_id,
                        *(ref.logical_id for ref in request.explicit_refs),
                    ]
                ),
            )
            .order_by(LockModel.id)
            .limit(selector.max_items + 1)
        )
        return tuple(to_domain(row, Lock) for row in rows)
