from dataclasses import replace
from uuid import UUID, uuid4

from novel_os.domain.core import (
    ChapterPlan,
    ChapterVersion,
    CommandContext,
    Decision,
    ObjectRef,
    Requirement,
    VersionToken,
    now,
)
from novel_os.domain.enums import ActorType, AuditAction, Authority, ObjectType, ScopeType, Status
from novel_os.domain.errors import DomainError
from novel_os.services.core_base import CoreService, validate_payload

COMMON_FIELDS = {"tags", "metadata"}


class VersionService(CoreService):
    entity_type: type
    kind: ObjectType
    allowed: set[str]
    required: tuple[str, ...]

    def validate(self, project_id: UUID, payload: dict, previous=None) -> dict:
        validate_payload(
            payload, self.allowed | COMMON_FIELDS, self.required if previous is None else ()
        )
        for key in self.required:
            if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
                raise DomainError("VALIDATION_ERROR", "Required text cannot be empty")
        return payload

    def get(self, project_id: UUID, logical_id: UUID, version: int | None = None):
        self.repo.get_project(project_id)
        return self.repo.get_version(self.kind, project_id, logical_id, version)

    def list(
        self,
        project_id: UUID,
        logical_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
        *,
        effective: bool = False,
    ):
        self.repo.get_project(project_id)
        return self.repo.list_versions(
            self.kind, project_id, logical_id, limit, offset, effective=effective
        )

    def approve(
        self,
        project_id: UUID,
        logical_id: UUID,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ):
        with self.mutation(project_id, context):
            return self.approve_in_transaction(
                project_id, logical_id, expected_version, context, reason
            )

    def approve_in_transaction(
        self,
        project_id: UUID,
        logical_id: UUID,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ):
        self.require_transaction(project_id)
        context.require_user()
        record = self.repo.get_version(self.kind, project_id, logical_id)
        VersionToken(expected_version).check(record.version)
        self.check_record_lock(record)
        self.validate(project_id, {name: getattr(record, name) for name in self.allowed}, record)
        if record.status not in {Status.PROPOSED, Status.DRAFT}:
            raise DomainError("INVALID_STATE", "Only a draft or proposal can be approved")
        previous = self.repo.get_approved(self.kind, project_id, logical_id)
        if previous is not None:
            self.check_record_lock(previous)
            retired = self.repo.save(replace(previous, status=Status.SUPERSEDED, updated_at=now()))
            self.audit(retired, AuditAction.SUPERSEDE, context, reason, previous)
        authority = (
            Authority.A4_APPROVED_PLAN
            if self.kind == ObjectType.CHAPTER_PLAN
            else Authority.A2_USER_APPROVED
        )
        approved = self.repo.save(
            replace(
                record,
                status=Status.APPROVED,
                authority_level=authority,
                approved_by=context.actor_id,
                approved_at=now(),
                updated_at=now(),
            )
        )
        if self.kind == ObjectType.CHAPTER_PLAN:
            self.update_chapter_pointer(
                project_id, logical_id, context, reason, approved_plan_version=record.version
            )
        elif self.kind == ObjectType.CHAPTER_VERSION:
            self.update_chapter_pointer(
                project_id, logical_id, context, reason, approved_version=record.version
            )
        self.audit(approved, AuditAction.APPROVE, context, reason, record)
        return approved


class ProposalService(VersionService):
    def create(self, project_id: UUID, payload: dict, context: CommandContext):
        with self.mutation(project_id, context):
            payload = self.validate(project_id, payload)
            record = self.repo.add(
                self.entity_type(project_id=project_id, created_by=context.actor_id, **payload)
            )
            self.audit(record, AuditAction.VERSION_CREATE, context, "Create proposal")
            return record

    def revise(
        self,
        project_id: UUID,
        logical_id: UUID,
        payload: dict,
        expected_version: int,
        context: CommandContext,
        reason: str,
        *,
        direct_edit: bool = False,
    ):
        with self.mutation(project_id, context):
            previous = self.repo.get_version(self.kind, project_id, logical_id)
            VersionToken(expected_version).check(previous.version)
            self.check_record_lock(previous)
            if direct_edit:
                previous.require_editable()
            elif previous.status not in {Status.PROPOSED, Status.DRAFT, Status.APPROVED}:
                raise DomainError("INVALID_STATE", "This state cannot create a new proposal")
            payload = self.validate(project_id, payload, previous)
            timestamp = now()
            record = self.repo.add(
                replace(
                    previous,
                    **payload,
                    id=uuid4(),
                    version=previous.version + 1,
                    supersedes_id=previous.id,
                    status=Status.PROPOSED,
                    locked=False,
                    authority_level=Authority.A5_USER_PREFERENCE,
                    created_by=context.actor_id,
                    approved_by=None,
                    approved_at=None,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            self.audit(record, AuditAction.VERSION_CREATE, context, reason, previous)
            return record


class RequirementService(ProposalService):
    entity_type = Requirement
    kind = ObjectType.REQUIREMENT
    required = ("content",)
    allowed = {
        "content",
        "requirement_type",
        "scope_type",
        "scope_id",
        "priority",
        "persistent",
        "effective_from",
        "effective_until",
    }

    def validate(self, project_id: UUID, payload: dict, previous=None) -> dict:
        payload = dict(super().validate(project_id, payload, previous))
        scope_type = payload.get(
            "scope_type", previous.scope_type if previous else ScopeType.PROJECT
        )
        scope_id = payload.get("scope_id", previous.scope_id if previous else project_id)
        if scope_id is None and scope_type == ScopeType.PROJECT:
            scope_id = project_id
        if scope_type == ScopeType.PROJECT:
            if scope_id != project_id:
                raise DomainError(
                    "VALIDATION_ERROR", "Requirement scope must belong to this project"
                )
        elif scope_type == ScopeType.CHAPTER:
            self.repo.get_chapter(project_id, scope_id)
            self.check_lock(project_id, ObjectRef(ObjectType.CHAPTER, scope_id))
        else:
            raise DomainError("VALIDATION_ERROR", "Unsupported requirement scope")
        start = payload.get("effective_from", previous.effective_from if previous else None)
        end = payload.get("effective_until", previous.effective_until if previous else None)
        if start is not None and end is not None and end < start:
            raise DomainError("VALIDATION_ERROR", "Invalid effective date range")
        priority = payload.get("priority", previous.priority if previous else 1)
        if not isinstance(priority, int) or not 1 <= priority <= 5:
            raise DomainError("VALIDATION_ERROR", "Priority must be between 1 and 5")
        payload["scope_id"] = scope_id
        return payload


class DecisionService(ProposalService):
    entity_type = Decision
    kind = ObjectType.DECISION
    required = ("question", "decision")
    allowed = {"question", "decision", "rationale", "affected_objects"}

    def validate(self, project_id: UUID, payload: dict, previous=None) -> dict:
        payload = dict(super().validate(project_id, payload, previous))
        references = payload.get("affected_objects", previous.affected_objects if previous else [])
        payload["affected_objects"] = self.validate_references(project_id, references)
        return payload

    def check_record_lock(self, record) -> None:
        # Only direct affected scopes are checked; this is not an impact-propagation engine.
        super().check_record_lock(record)
        if isinstance(record, Decision):
            for value in record.affected_objects:
                target = ObjectRef(ObjectType(value["object_type"]), UUID(value["object_id"]))
                super().check_record_lock(self.resolve_target(record.project_id, target))


class ChapterArtifactService(VersionService):
    def list(
        self,
        project_id: UUID,
        logical_id: UUID,
        limit: int = 100,
        offset: int = 0,
        *,
        effective: bool = False,
    ):
        self.repo.get_chapter(project_id, logical_id)
        return super().list(project_id, logical_id, limit, offset, effective=effective)

    def create_version(
        self,
        project_id: UUID,
        chapter_id: UUID,
        payload: dict,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ):
        with self.mutation(project_id, context):
            return self.create_version_in_transaction(
                project_id, chapter_id, payload, expected_version, context, reason
            )

    def create_version_in_transaction(
        self,
        project_id: UUID,
        chapter_id: UUID,
        payload: dict,
        expected_version: int,
        context: CommandContext,
        reason: str,
    ):
        self.require_transaction(project_id)
        chapter = self.repo.get_chapter(project_id, chapter_id)
        self.check_record_lock(chapter)
        self.check_lock(project_id, ObjectRef(self.kind, chapter_id))
        current = (
            chapter.current_plan_version
            if self.kind == ObjectType.CHAPTER_PLAN
            else chapter.current_version
        ) or 0
        VersionToken(expected_version).check(current)
        payload = self.validate(project_id, payload)
        previous = self.repo.get_version(self.kind, project_id, chapter_id) if current else None
        extra = {}
        if self.kind == ObjectType.CHAPTER_VERSION:
            extra = {
                "parent_version_id": previous.id if previous else None,
                "status": Status.DRAFT,
            }
        record = self.repo.add(
            self.entity_type(
                project_id=project_id,
                logical_id=chapter_id,
                chapter_id=chapter_id,
                version=current + 1,
                supersedes_id=previous.id if previous else None,
                created_by=context.actor_id,
                source=context.actor_type,
                authority_level=(
                    Authority.A5_USER_PREFERENCE
                    if context.actor_type == ActorType.USER
                    else Authority.A7_AI_INFERENCE
                ),
                **payload,
                **extra,
            )
        )
        pointer = (
            "current_plan_version" if self.kind == ObjectType.CHAPTER_PLAN else "current_version"
        )
        self.update_chapter_pointer(
            project_id, chapter_id, context, reason, **{pointer: record.version}
        )
        self.audit(record, AuditAction.VERSION_CREATE, context, reason, previous)
        return record


class PlanningService(ChapterArtifactService):
    entity_type = ChapterPlan
    kind = ObjectType.CHAPTER_PLAN
    required = ("objective", "required_outcome")
    allowed = {
        "objective",
        "required_outcome",
        "scene_plans",
        "character_progression",
        "plot_progression",
        "information_release",
        "ending_state",
        "constraints",
        "locked_dependencies",
        "risks",
    }

    def validate(self, project_id: UUID, payload: dict, previous=None) -> dict:
        payload = dict(super().validate(project_id, payload, previous))
        references = payload.get(
            "locked_dependencies", previous.locked_dependencies if previous else []
        )
        payload["locked_dependencies"] = self.validate_references(
            project_id, references, require_locked=True
        )
        return payload


class ChapterVersionService(ChapterArtifactService):
    entity_type = ChapterVersion
    kind = ObjectType.CHAPTER_VERSION
    required = ("content", "change_reason")
    allowed = {"content", "change_reason"}
