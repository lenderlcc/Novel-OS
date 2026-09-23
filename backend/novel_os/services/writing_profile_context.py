"""Exact approved preferences and scheduling pins; preferences never become requirements."""

import json
from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceType
from novel_os.domain.errors import DomainError
from novel_os.prompts.contracts import canonical
from novel_os.repositories.writing_profiles import WritingProfileRepository

BINDING_TYPE = "PROJECT_WRITING_PROFILE_BINDING"
PROFILE_SELECTOR = "approved-project-writing-profile"


def model_requirements(requirements):
    """Scheduling pins are server metadata, not model-visible story requirements."""
    visible = []
    for entry in requirements:
        try:
            value = json.loads(entry)
        except ValueError:
            value = None
        if isinstance(value, dict) and value.get("type") == BINDING_TYPE:
            continue
        visible.append(entry)
    return tuple(visible)


class WritingProfileContext:
    def __init__(self, session):
        self.session = session
        self.repo = WritingProfileRepository(session)

    def binding(self, project_id):
        record = self.repo.get(project_id, approved=True)
        return record.binding() if record else None

    def scheduling_input(self, project_id):
        return canonical({"type": BINDING_TYPE, "binding": self.binding(project_id)})

    def check_scheduled(self, task):
        if task.task_type not in {"PLAN_CHAPTER", "REVIEW_CHAPTER_PLAN"}:
            return
        for entry in task.requirements:
            try:
                value = json.loads(entry)
            except ValueError:
                continue
            if (
                isinstance(value, dict)
                and value.get("type") == BINDING_TYPE
                and value["binding"] != self.binding(task.project_id)
            ):
                raise DomainError(
                    "CONTEXT_STALE", "Project writing profile changed after scheduling"
                )

    def check_plan(self, generation):
        from novel_os.repositories.context_packages import ContextPackageRepository

        package = ContextPackageRepository(self.session).get(generation.context_package_id)
        # Pre-STYLE historical plans have no selector and retain their original semantics.
        if not any(s.selector_id == PROFILE_SELECTOR for s in package.source_snapshots):
            return
        selected = next(
            (i for i in package.items if i.source_type == SourceType.PROJECT_WRITING_PROFILE), None
        )
        pinned = (
            {
                key: selected.structured_payload[key]
                for key in (
                    "writing_profile_id",
                    "writing_profile_version",
                    "writing_profile_hash",
                )
            }
            if selected
            else None
        )
        if pinned != self.binding(generation.project_id):
            raise DomainError(
                "CONTEXT_STALE", "Plan writing preferences changed; replan explicitly"
            )

    def query(self, request, selector):
        record = self.repo.get(request.project_id, approved=True)
        binding = record.binding() if record else None
        observed = {"approved_writing_profile": binding}
        if record is None:
            return (), observed
        return (
            ContextItem(
                context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
                selector_id=selector.selector_id,
                source_type=SourceType.PROJECT_WRITING_PROFILE,
                source_id=record.id,
                logical_id=record.profile_id,
                source_version=record.version,
                project_id=record.project_id,
                status=record.status,
                authority_level=record.authority_level,
                locked=False,
                priority=selector.priority,
                scope=selector.scope,
                payload_json=canonical({**record.preferences.payload(), **binding}),
                selected_reason="Exact approved A5 preference; no story authority",
                source_created_at=record.created_at,
                source_updated_at=record.approved_at,
                relevance_score=100,
                provenance=("structured_database", "project_preference", "version_policy:APPROVED"),
            ),
        ), observed
