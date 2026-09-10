from dataclasses import replace
from uuid import UUID

from novel_os.domain.core import CommandContext, Lock, ObjectRef, VersionToken, now
from novel_os.domain.enums import AuditAction, Authority, ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.services.core_base import CoreService


class LockService(CoreService):
    def create(
        self,
        project_id: UUID,
        target: ObjectRef,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ) -> Lock:
        with self.mutation(project_id, context):
            record = self.resolve_target(project_id, target)
            VersionToken(expected_version).check(record.version)
            self.check_record_lock(record)
            if record.status not in {Status.ACTIVE, Status.PROPOSED, Status.DRAFT, Status.APPROVED}:
                raise DomainError("INVALID_STATE", "This state cannot be locked")
            lock = self.repo.add(
                Lock(
                    project_id=project_id,
                    target_type=target.object_type,
                    target_id=target.object_id,
                    target_version=record.version,
                    reason=reason,
                    locked_by=context.actor_id,
                    previous_status=record.status,
                    previous_authority=record.authority_level,
                )
            )
            version = record.version + (
                record.object_type in {ObjectType.PROJECT, ObjectType.CHAPTER}
            )
            locked = self.repo.save(
                replace(
                    record,
                    locked=True,
                    status=Status.LOCKED,
                    authority_level=Authority.A1_USER_LOCKED,
                    version=version,
                    updated_at=now(),
                )
            )
            self.audit(locked, AuditAction.LOCK, context, reason, record, {"lock_id": str(lock.id)})
            return lock

    def release(
        self,
        project_id: UUID,
        lock_id: UUID,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ) -> Lock:
        with self.mutation(project_id, context, allow_project_locked=True):
            lock = self.repo.get_lock(project_id, lock_id)
            if not lock.active:
                raise DomainError("INVALID_STATE", "Lock has already been released")
            if lock.target_type != ObjectType.PROJECT:
                self.check_lock(project_id, ObjectRef(ObjectType.PROJECT, project_id))
            record = self.resolve_target(project_id, ObjectRef(lock.target_type, lock.target_id))
            self.check_parent_locks(record)
            VersionToken(expected_version).check(record.version)
            released = self.repo.save(
                replace(
                    lock,
                    active=False,
                    released_at=now(),
                    released_by=context.actor_id,
                    release_reason=reason,
                )
            )
            version = record.version + (
                record.object_type in {ObjectType.PROJECT, ObjectType.CHAPTER}
            )
            unlocked = self.repo.save(
                replace(
                    record,
                    locked=False,
                    status=lock.previous_status,
                    authority_level=lock.previous_authority,
                    version=version,
                    updated_at=now(),
                )
            )
            self.audit(
                unlocked, AuditAction.UNLOCK, context, reason, record, {"lock_id": str(lock.id)}
            )
            return released

    def list(self, project_id: UUID, limit: int = 100, offset: int = 0) -> list[Lock]:
        self.repo.get_project(project_id)
        return self.repo.list_locks(project_id, limit, offset)
