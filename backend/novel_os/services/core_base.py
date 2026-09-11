from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from novel_os.domain.core import AuditRecord, CommandContext, ObjectRef, Project, Record, now
from novel_os.domain.enums import AuditAction, ObjectType, ScopeType, Status
from novel_os.domain.errors import DomainError
from novel_os.repositories.core import CoreRepository


def validate_payload(payload: dict, allowed: set[str], required: tuple[str, ...] = ()) -> dict:
    if payload.keys() - allowed:
        raise DomainError("VALIDATION_ERROR", "Unexpected or server-owned fields")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise DomainError("VALIDATION_ERROR", "Required text cannot be empty")
    return payload


class CoreService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CoreRepository(session)

    def resolve_target(self, project_id: UUID, target: ObjectRef):
        if target.object_type == ObjectType.PROJECT:
            if target.object_id != project_id:
                raise DomainError("NOT_FOUND", "Project target not found")
            return self.repo.get_project(project_id)
        if target.object_type == ObjectType.CHAPTER:
            return self.repo.get_chapter(project_id, target.object_id)
        if target.object_type in {
            ObjectType.REQUIREMENT,
            ObjectType.DECISION,
            ObjectType.CHAPTER_PLAN,
            ObjectType.CHAPTER_VERSION,
        }:
            return self.repo.get_version(target.object_type, project_id, target.object_id)
        raise DomainError("VALIDATION_ERROR", "Unsupported reference target")

    def validate_references(
        self, project_id: UUID, references: list[dict], *, require_locked: bool = False
    ) -> list[dict]:
        normalized = []
        for value in references:
            try:
                if set(value) != {"object_type", "object_id"}:
                    raise ValueError
                reference = ObjectRef(
                    ObjectType(value["object_type"]), UUID(str(value["object_id"]))
                )
            except (ValueError, TypeError, KeyError):
                raise DomainError("VALIDATION_ERROR", "Invalid object reference") from None
            record = self.resolve_target(project_id, reference)
            if require_locked:
                if self.repo.active_lock(project_id, reference) is None:
                    raise DomainError("INVALID_STATE", "A declared locked dependency is not locked")
            else:
                self.check_lock(project_id, reference)
                self.check_parent_locks(record)
            normalized.append(
                {"object_type": reference.object_type.value, "object_id": str(reference.object_id)}
            )
        return normalized

    @contextmanager
    def mutation(
        self, project_id: UUID, context: CommandContext, *, allow_project_locked: bool = False
    ) -> Iterator[Project]:
        context.require_user()
        try:
            with self.session.begin():
                project = self.repo.get_project(project_id, for_update=True)
                if project.status == Status.ARCHIVED:
                    raise DomainError("INVALID_STATE", "Project is archived")
                if not allow_project_locked:
                    self.check_lock(project_id, ObjectRef(ObjectType.PROJECT, project_id))
                yield project
        except IntegrityError as exc:
            # Do not expose SQL, constraint payloads or database exception messages.
            raise DomainError(
                "VERSION_CONFLICT", "A concurrent or conflicting write was rejected"
            ) from exc

    def require_transaction(self, project_id: UUID) -> None:
        """Join an application-owned transaction, retaining the shared root lock/checks."""
        if not self.session.in_transaction():
            raise RuntimeError("An application transaction is required")
        project = self.repo.get_project(project_id, for_update=True)
        if project.status == Status.ARCHIVED:
            raise DomainError("INVALID_STATE", "Project is archived")
        self.check_lock(project_id, ObjectRef(ObjectType.PROJECT, project_id))

    def check_lock(self, project_id: UUID, target: ObjectRef) -> None:
        if self.repo.active_lock(project_id, target) is not None:
            raise DomainError("LOCKED_OBJECT", "The object or its parent is locked")

    def check_record_lock(self, record: Record) -> None:
        target_id = getattr(record, "logical_id", record.id)
        self.check_lock(record.project_id, ObjectRef(record.object_type, target_id))
        self.check_parent_locks(record)

    def check_parent_locks(self, record: Record) -> None:
        chapter_id = getattr(record, "chapter_id", None)
        if getattr(record, "scope_type", None) == ScopeType.CHAPTER:
            chapter_id = record.scope_id
        if chapter_id is not None:
            self.check_lock(record.project_id, ObjectRef(ObjectType.CHAPTER, chapter_id))

    def audit(
        self,
        record: Record,
        action: AuditAction,
        context: CommandContext,
        reason: str,
        before: Record | None = None,
        extra: dict | None = None,
    ) -> None:
        def snapshot(value):
            if value is None:
                return {}
            result = {
                "id": str(value.id),
                "version": value.version,
                "status": value.status.value,
                "authority_level": value.authority_level.value,
                "locked": value.locked,
            }
            for name in (
                "logical_id",
                "current_version",
                "approved_version",
                "current_plan_version",
                "approved_plan_version",
            ):
                if hasattr(value, name):
                    item = getattr(value, name)
                    result[name] = str(item) if isinstance(item, UUID) else item
            return result

        self.repo.add(
            AuditRecord(
                project_id=record.project_id,
                target_type=record.object_type,
                target_id=record.id,
                target_version=record.version,
                action=action,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason=reason,
                before=snapshot(before),
                after={**snapshot(record), **(extra or {})},
            )
        )

    def update_chapter_pointer(
        self, project_id: UUID, chapter_id: UUID, context: CommandContext, reason: str, **pointers
    ) -> None:
        chapter = self.repo.get_chapter(project_id, chapter_id)
        updated = self.repo.save(
            replace(chapter, **pointers, version=chapter.version + 1, updated_at=now())
        )
        self.audit(updated, AuditAction.UPDATE, context, reason, chapter)

    def list_audit(self, project_id: UUID, limit: int = 100, offset: int = 0):
        self.repo.get_project(project_id)
        return self.repo.list_audit(project_id, limit, offset)
