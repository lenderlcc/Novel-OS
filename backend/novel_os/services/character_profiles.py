"""User-owned character definitions; no memory or revision learning writes here."""

from contextlib import nullcontext
from dataclasses import replace
from uuid import UUID, uuid5

from pydantic import ValidationError

from novel_os.characters.schemas import CharacterBehaviorProfileBody
from novel_os.domain.character_profile import CharacterBehaviorProfile
from novel_os.domain.core import AuditRecord, VersionToken, now
from novel_os.domain.enums import AuditAction, Authority, ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.memory import MemorySubject
from novel_os.memory.policy import normalized
from novel_os.repositories.character_profiles import CharacterProfileRepository
from novel_os.repositories.memory import MemoryRepository
from novel_os.services.core_base import CoreService


class CharacterProfileService(CoreService):
    def __init__(self, session):
        super().__init__(session)
        self.profiles = CharacterProfileRepository(session)
        self.memory = MemoryRepository(session)

    def get_subject(self, project_id, character_id):
        subject = self.memory.get(MemorySubject, character_id)
        if subject.project_id != project_id or subject.kind != "CHARACTER":
            raise DomainError("NOT_FOUND", "Character not found in this project")
        return subject

    def characters(self, project_id, limit=100, offset=0):
        self.repo.get_project(project_id)
        return self.memory.subjects(project_id, kind="CHARACTER", limit=limit, offset=offset)

    def create_character(self, project_id, name, aliases, context, reason):
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 200 or "\x00" in name:
            raise DomainError("VALIDATION_ERROR", "Invalid character name")
        if (
            not isinstance(aliases, list)
            or len(aliases) > 10
            or any(
                not isinstance(alias, str) or not 0 < len(alias.strip()) <= 200 or "\x00" in alias
                for alias in aliases
            )
        ):
            raise DomainError("VALIDATION_ERROR", "Invalid character aliases")
        normalized_name = normalized(name)
        normalized_aliases = [normalized(alias) for alias in aliases]
        names = [normalized_name, *normalized_aliases]
        if not all(names) or len(set(names)) != len(names):
            raise DomainError("VALIDATION_ERROR", "Character names and aliases must be distinct")
        with self.mutation(project_id, context) as project:
            subjects = self.memory.subjects(project_id)
            if len(subjects) >= 500:
                raise DomainError("INVALID_STATE", "The project subject limit has been reached")
            if any(set(names) & {s.normalized_name, *s.aliases} for s in subjects):
                raise DomainError("VERSION_CONFLICT", "A character name or alias already exists")
            subject = self.memory.add(
                MemorySubject(
                    id=uuid5(project_id, f"memory-subject:CHARACTER:{normalized_name}"),
                    project_id=project_id,
                    name=name.strip(),
                    normalized_name=normalized_name,
                    kind="CHARACTER",
                    aliases=normalized_aliases,
                    batch_id=None,
                    created_by=context.actor_id,
                )
            )
            self.repo.add(
                AuditRecord(
                    project_id=project_id,
                    target_type=ObjectType.PROJECT,
                    target_id=project_id,
                    target_version=project.version,
                    action=AuditAction.CREATE,
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    request_id=context.request_id,
                    reason=reason,
                    after={"character_id": str(subject.id), "name": subject.name},
                )
            )
            return subject

    def state(self, project_id, character_id):
        self.repo.get_project(project_id)
        self.get_subject(project_id, character_id)
        return self.profiles.state(project_id, character_id)

    def versions(self, project_id, character_id, limit=100, offset=0):
        self.repo.get_project(project_id)
        self.get_subject(project_id, character_id)
        return self.profiles.versions(project_id, character_id, limit, offset)

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
                    "character_id": str(profile.character_id),
                    "status": profile.status,
                    "authority_level": profile.authority_level,
                },
            )
        )

    def create_draft(
        self,
        project_id,
        character_id,
        payload,
        expected_version,
        context,
        reason,
        *,
        source_text=None,
        in_transaction=False,
    ):
        try:
            body = CharacterBehaviorProfileBody.model_validate(payload).model_dump(mode="json")
        except ValidationError:
            raise DomainError("VALIDATION_ERROR", "Invalid character behavior profile") from None
        if source_text is not None and (
            not isinstance(source_text, str)
            or not 0 < len(source_text.strip()) <= 10000
            or "\x00" in source_text
        ):
            raise DomainError("VALIDATION_ERROR", "Invalid character profile source text")
        with nullcontext() if in_transaction else self.mutation(project_id, context) as project:
            if in_transaction:
                context.require_user()
                self.require_transaction(project_id)
                project = self.repo.get_project(project_id)
            self.get_subject(project_id, character_id)
            for modifier in body["relationship_modifiers"]:
                other_id = modifier["other_character_id"]
                if str(character_id) == other_id:
                    raise DomainError(
                        "VALIDATION_ERROR", "A relationship requires another character"
                    )
                # Validation is project scoped even when the supplied UUID exists elsewhere.
                self.get_subject(project_id, UUID(other_id))
            current = self.profiles.get(project_id, character_id)
            VersionToken(expected_version).check(current.version if current else 0)
            profile = self.profiles.add(
                CharacterBehaviorProfile(
                    project_id=project_id,
                    character_id=character_id,
                    version=expected_version + 1,
                    body=body,
                    created_by=context.actor_id,
                    supersedes_id=current.id if current else None,
                    source_text=source_text,
                )
            )
            self.record_audit(
                project, profile, AuditAction.VERSION_CREATE, context, reason, current
            )
            return profile

    def approve(self, project_id, character_id, expected_version, context, reason):
        with self.mutation(project_id, context) as project:
            self.get_subject(project_id, character_id)
            current = self.profiles.get(project_id, character_id)
            VersionToken(expected_version).check(current.version if current else 0)
            if current is None or current.status != Status.DRAFT:
                raise DomainError(
                    "INVALID_STATE", "Only the current character profile draft can be approved"
                )
            previous = self.profiles.get(project_id, character_id, approved=True)
            if previous:
                retired = self.profiles.lifecycle(replace(previous, status=Status.SUPERSEDED))
                self.record_audit(
                    project, retired, AuditAction.SUPERSEDE, context, reason, previous
                )
            approved = self.profiles.lifecycle(
                replace(
                    current,
                    status=Status.APPROVED,
                    authority_level=Authority.A3_CANON,
                    approved_at=now(),
                    approved_by=context.actor_id,
                )
            )
            self.record_audit(project, approved, AuditAction.APPROVE, context, reason, current)
            return approved
