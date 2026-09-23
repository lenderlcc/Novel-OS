from dataclasses import replace

from novel_os.domain.core import AuditRecord, VersionToken, now
from novel_os.domain.enums import AuditAction, ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.writing_profile import ProjectWritingProfile, WritingPreferences
from novel_os.repositories.writing_profiles import WritingProfileRepository
from novel_os.services.core_base import CoreService


class WritingProfileService(CoreService):
    def __init__(self, session):
        super().__init__(session)
        self.profiles = WritingProfileRepository(session)

    def state(self, project_id):
        self.repo.get_project(project_id)
        # One SELECT keeps the derived current/approved pointers mutually consistent.
        return self.profiles.state(project_id)

    def versions(self, project_id, limit=100, offset=0):
        self.repo.get_project(project_id)
        return self.profiles.versions(project_id, limit, offset)

    def record_audit(self, project, profile, action, context, reason, before=None):
        self.repo.add(
            AuditRecord(
                project_id=project.id,
                target_type=ObjectType.PROJECT,
                target_id=project.id,
                target_version=project.version,
                action=action,
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                request_id=context.request_id,
                reason=reason,
                before=({**before.binding(), "status": before.status} if before else {}),
                after={
                    **profile.binding(),
                    "profile_record_id": str(profile.id),
                    "status": profile.status,
                    "authority_level": profile.authority_level,
                },
            )
        )

    def create_draft(self, project_id, payload, expected_version, context, reason):
        preferences = WritingPreferences.from_payload(payload)
        with self.mutation(project_id, context) as project:
            current = self.profiles.get(project_id)
            VersionToken(expected_version).check(current.version if current else 0)
            profile = self.profiles.add(
                ProjectWritingProfile(
                    project_id=project_id,
                    version=expected_version + 1,
                    preferences=preferences,
                    created_by=context.actor_id,
                )
            )
            self.record_audit(
                project, profile, AuditAction.VERSION_CREATE, context, reason, current
            )
            return profile

    def approve(self, project_id, expected_version, context, reason):
        with self.mutation(project_id, context) as project:
            current = self.profiles.get(project_id)
            VersionToken(expected_version).check(current.version if current else 0)
            if current is None or current.status != Status.DRAFT:
                raise DomainError("INVALID_STATE", "Only the current profile draft can be approved")
            previous = self.profiles.get(project_id, approved=True)
            if previous:
                retired = self.profiles.lifecycle(replace(previous, status=Status.SUPERSEDED))
                self.record_audit(
                    project, retired, AuditAction.SUPERSEDE, context, reason, previous
                )
            approved = self.profiles.lifecycle(
                replace(
                    current, status=Status.APPROVED, approved_at=now(), approved_by=context.actor_id
                )
            )
            self.record_audit(project, approved, AuditAction.APPROVE, context, reason, current)
            return approved
