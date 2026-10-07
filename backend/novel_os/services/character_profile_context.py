"""Relevant approved character tendencies use the existing Context snapshot and lineage."""

import json
from uuid import NAMESPACE_URL, uuid5

from novel_os.characters.schemas import CharacterBehaviorProfileBody
from novel_os.domain.context import ContextItem, SourceType
from novel_os.domain.enums import Status
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import canonical
from novel_os.repositories.character_profiles import CharacterProfileRepository
from novel_os.services.canon_context import CanonContextReader

PROFILE_SELECTOR = "approved-character-behavior-profiles"
BINDING_TYPE = "CHARACTER_PROFILE_BINDING"
PLANNING_TASKS = {"PLAN_CHAPTER", "EXPLORE_CHAPTER_CONCEPTS", "REVIEW_CHAPTER_PLAN"}


class CharacterProfileContext:
    def __init__(self, session):
        self.session = session
        self.repo = CharacterProfileRepository(session)
        self.canon = CanonContextReader(session)

    def relevant(self, request):
        subjects = {
            subject.id: subject
            for subject in self.canon.subjects(request, limit=501)
            if subject.kind == "CHARACTER" and subject.project_id == request.project_id
        }
        records = self.repo.approved_for_characters(request.project_id, subjects)
        records = [
            record
            for record in records
            if record.project_id == request.project_id
            and record.character_id in subjects
            and record.status == Status.APPROVED
        ]
        return subjects, records

    def query(self, request, selector):
        subjects, records = self.relevant(request)
        items = []
        for record in records:
            body = CharacterBehaviorProfileBody.model_validate(record.body)
            profile = body.model_dump(mode="json")
            profile["relationship_modifiers"] = [
                modifier.model_dump(mode="json")
                for modifier in body.relationship_modifiers
                if modifier.other_character_id in subjects
            ]
            items.append(
                ContextItem(
                    context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
                    selector_id=selector.selector_id,
                    source_type=SourceType.EXTENSION,
                    source_id=record.id,
                    logical_id=record.logical_id,
                    source_version=record.version,
                    project_id=record.project_id,
                    chapter_id=request.chapter_id,
                    status=record.status,
                    authority_level=record.authority_level,
                    locked=False,
                    priority=selector.priority,
                    scope=selector.scope,
                    payload_json=canonical(
                        {
                            **record.binding(),
                            "kind": "CHARACTER_BEHAVIOR_PROFILE",
                            "character_profile_record_id": str(record.id),
                            "character_id": str(record.character_id),
                            "character_name": subjects[record.character_id].name,
                            "relationship_modifier_version": record.version,
                            "profile": profile,
                            "role": "BEHAVIOR_TENDENCY",
                        }
                    ),
                    selected_reason="Approved character tendency; task-involved relationships only",
                    source_created_at=record.created_at,
                    source_updated_at=record.approved_at or record.created_at,
                    character_id=record.character_id,
                    relevance_score=100,
                    provenance=("character_behavior_profile", "version_policy:APPROVED"),
                )
            )
        return tuple(items), {
            "involved_character_ids": sorted(str(identity) for identity in subjects),
            "approved_character_profiles": [record.binding() for record in records],
        }

    def binding(self, task, workflow):
        from novel_os.services.context import ContextService

        context = ContextService(self.session)
        request = context.request_for_task(task, workflow, context.task_profile(task))
        subjects, records = self.relevant(request)
        return {
            "involved_character_ids": sorted(str(identity) for identity in subjects),
            "approved_character_profiles": [record.binding() for record in records],
        }

    def scheduling_input(self, task, workflow):
        return canonical({"type": BINDING_TYPE, "binding": self.binding(task, workflow)})

    def check_scheduled(self, task, workflow):
        if task.task_type not in PLANNING_TASKS:
            return
        for entry in task.requirements:
            try:
                value = json.loads(entry)
            except ValueError:
                continue
            if (
                isinstance(value, dict)
                and value.get("type") == BINDING_TYPE
                and value["binding"] != self.binding(task, workflow)
            ):
                raise DomainError(
                    "CONTEXT_STALE", "Approved character profiles changed after scheduling"
                )

    def check_plan(self, generation):
        from novel_os.context.profiles import ContextProfile
        from novel_os.repositories.context_packages import ContextPackageRepository
        from novel_os.services.memory_query import MemoryQueryService

        package = ContextPackageRepository(self.session).get(generation.context_package_id)
        original = next(
            (stamp for stamp in package.source_snapshots if stamp.selector_id == PROFILE_SELECTOR),
            None,
        )
        if original is None:
            return  # Historical Plan contexts retain their original inputs.
        profile = ContextProfile.model_validate_json(package.profile_json)
        profile = profile.model_copy(
            update={
                "selectors": tuple(
                    selector
                    for selector in profile.selectors
                    if selector.selector_id == PROFILE_SELECTOR
                )
            }
        )
        current = MemoryQueryService(self.session).query(
            package.request, profile, package.created_at, package.created_at
        )
        if current.snapshots != (original,):
            raise DomainError("CONTEXT_STALE", "Plan character profiles changed; replan explicitly")
