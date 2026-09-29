"""Structured context candidate facade. Extension readers do not own final selection."""

from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from novel_os.context.inputs import task_item
from novel_os.context.profiles import ContextConfigurationError
from novel_os.context.serialization import ITEM_ADAPTER
from novel_os.domain.context import (
    CandidateBatch,
    ContextItem,
    ContextScope,
    SourceSnapshot,
    SourceType,
    VersionPolicy,
)
from novel_os.domain.enums import Authority, Status
from novel_os.domain.quality import QUALITY_TASKS
from novel_os.domain.revision import REVISION_TASKS
from novel_os.prompts.contracts import canonical, digest
from novel_os.repositories.context_sources import ContextSourceRepository

FIELDS = {
    SourceType.PROJECT: ("name", "description", "tags"),
    SourceType.CHAPTER: ("sequence", "title"),
    SourceType.REQUIREMENT: ("content", "requirement_type", "scope_type", "scope_id", "persistent"),
    SourceType.DECISION: ("question", "decision", "rationale", "affected_objects"),
    SourceType.CHAPTER_PLAN: (
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
    ),
    SourceType.CHAPTER_VERSION: ("content", "change_reason"),
    SourceType.LOCK: ("target_type", "target_id", "target_version", "scope", "reason"),
}


class ContextSourceReader(Protocol):
    """Return typed candidates for the given selector and source type, with provenance."""

    def query(self, request, selector) -> tuple[ContextItem, ...]: ...


class MemoryQueryService:
    def __init__(self, session, *, extensions=None):
        self.session = session
        self.repo = ContextSourceRepository(session)
        self.extensions = extensions or {}

    def query(self, request, profile, timestamp, task_created_at):
        items, excluded, stamps, overflow = [], [], [], []
        for selector in profile.selectors:
            candidates, observed = self._query(request, selector, timestamp, task_created_at)
            # Candidate fingerprints also detect additions, disappearance and approval changes.
            values = sorted(
                (ITEM_ADAPTER.dump_python(item, mode="json") for item in candidates), key=canonical
            )
            if (
                request.task_type
                in {"WRITE_CHAPTER", "INTERPRET_CHAPTER_FEEDBACK", *QUALITY_TASKS, *REVISION_TASKS}
                and selector.source_type == SourceType.CHAPTER
            ):
                # Unapproved Plan edits increment Chapter metadata but do not change
                # the exact Draft or approved Plan consumed by Writing/Review.
                for value in values:
                    for key in ("context_item_id", "source_version", "source_updated_at"):
                        value.pop(key)
            stamps.append(
                SourceSnapshot(
                    selector_id=selector.selector_id,
                    fingerprint=digest(canonical({"items": values, "pointers": observed})),
                )
            )
            if len(candidates) > selector.max_items and selector.priority.value == "P0":
                overflow.append(selector.selector_id)
            items.extend(candidates)
        return CandidateBatch(tuple(items), tuple(excluded), tuple(stamps), tuple(overflow))

    def _query(self, request, selector, timestamp, task_created_at):
        source = selector.source_type
        if source == SourceType.PROJECT_WRITING_PROFILE:
            from novel_os.services.writing_profile_context import WritingProfileContext

            return WritingProfileContext(self.session).query(request, selector)
        if source in {SourceType.CREATIVE_BRIEF, SourceType.PLAN_REVIEW_REPORT}:
            from novel_os.services.planning_context import PlanningContextReader

            return PlanningContextReader(self.session).query(request, selector)
        if source == SourceType.TASK_INPUT:
            return (task_item(request, selector, task_created_at),), {}
        if source == SourceType.EXTENSION:
            from novel_os.services.feedback_context import FEEDBACK_SELECTORS, FeedbackContextReader

            if selector.selector_id in FEEDBACK_SELECTORS:
                return FeedbackContextReader(self.session).query(request, selector)
            from novel_os.services.revision_context import REVISION_SELECTORS, RevisionContextReader

            if selector.selector_id in REVISION_SELECTORS:
                return RevisionContextReader(self.session).query(request, selector)
            reader = self.extensions.get(selector.selector_id)
            candidates = tuple(reader.query(request, selector)) if reader else ()
            if any(
                not isinstance(item, ContextItem)
                or item.selector_id != selector.selector_id
                or item.source_type != source
                for item in candidates
            ):
                raise ContextConfigurationError("Context reader returned an incompatible candidate")
            return candidates, {}
        if source == SourceType.PROJECT:
            return (
                self._item(self.repo.core.get_project(request.project_id), request, selector),
            ), {}
        if source == SourceType.CHAPTER:
            return (
                self._item(
                    self.repo.chapter(request.project_id, request.chapter_id), request, selector
                ),
            ), {}
        if source in {SourceType.REQUIREMENT, SourceType.DECISION}:
            records = self.repo.effective(source, request, selector, timestamp)
            return tuple(
                self._item(
                    record,
                    request,
                    selector,
                    self.repo.dependency_chapter(source, record)
                    if selector.scope == ContextScope.EXPLICIT
                    else None,
                )
                for record in records
            ), {}
        if source == SourceType.LOCK:
            return tuple(
                self._item(record, request, selector)
                for record in self.repo.locks(request, selector)
            ), {}
        if selector.scope == ContextScope.RECENT_APPROVED_CHAPTERS:
            if (
                source != SourceType.CHAPTER_VERSION
                or selector.version_policy != VersionPolicy.APPROVED
            ):
                raise ContextConfigurationError("Recent review context requires approved chapters")
            records, observed = [], []
            for chapter in self.repo.recent_approved(
                request.project_id, request.chapter_sequence, selector.max_items
            ):
                observed.append((str(chapter.id), chapter.approved_version))
                record = self.repo.artifact(
                    source, request.project_id, chapter.id, chapter.approved_version
                )
                if (
                    record
                    and record.approved_at
                    and record.status in {Status.APPROVED, Status.LOCKED}
                ):
                    records.append(self._item(record, request, selector, chapter))
            return tuple(records), {"recent_approved": observed}
        chapters = [self.repo.chapter(request.project_id, request.chapter_id)]
        if selector.scope == ContextScope.PREVIOUS_CHAPTER:
            chapters = [self.repo.previous(request.project_id, request.chapter_sequence)]
        if selector.scope == ContextScope.EXPLICIT:
            result = []
            for ref in request.explicit_refs:
                if ref.source_type == source:
                    record = self.repo.artifact(
                        source, request.project_id, ref.logical_id, ref.version
                    )
                    if record is None:
                        continue
                    chapter = self.repo.chapter(request.project_id, record.chapter_id)
                    if selector.version_policy in {VersionPolicy.APPROVED, VersionPolicy.EFFECTIVE}:
                        approved = (
                            chapter.approved_plan_version
                            if source == SourceType.CHAPTER_PLAN
                            else chapter.approved_version
                        )
                        if (
                            record.approved_at is None
                            or record.status not in {Status.APPROVED, Status.LOCKED}
                            or approved != ref.version
                        ):
                            continue
                    elif selector.version_policy == VersionPolicy.LOCKED:
                        lock = self.repo.lock(request.project_id, source, ref.logical_id)
                        if (
                            record.status != Status.LOCKED
                            or lock is None
                            or lock.target_version != ref.version
                        ):
                            continue
                    elif selector.version_policy not in {
                        VersionPolicy.EXACT,
                        VersionPolicy.TARGET_VERSION,
                    }:
                        raise ContextConfigurationError(
                            "Explicit artifacts require a version policy"
                        )
                    result.append(self._item(record, request, selector, chapter))
            return tuple(result), {}
        chapter = chapters[0]
        if chapter is None:
            return (), {"previous_approved_chapter": None}
        plan = source == SourceType.CHAPTER_PLAN
        approved = chapter.approved_plan_version if plan else chapter.approved_version
        current = chapter.current_plan_version if plan else chapter.current_version
        if selector.version_policy in {VersionPolicy.APPROVED, VersionPolicy.EFFECTIVE}:
            version = approved
            if (
                plan
                and request.approved_plan_version is not None
                and approved != request.approved_plan_version
            ):
                return (), {"approved_pointer": approved, "expected": request.approved_plan_version}
        elif selector.version_policy == VersionPolicy.CURRENT:
            version = current
        elif selector.version_policy in {VersionPolicy.TARGET_VERSION, VersionPolicy.EXACT}:
            version = request.approved_plan_version if plan else request.target_version
        elif selector.version_policy == VersionPolicy.LOCKED:
            lock = self.repo.lock(request.project_id, source, chapter.id)
            version = lock.target_version if lock else None
        else:
            raise ValueError("Unknown version policy")
        record = self.repo.artifact(source, request.project_id, chapter.id, version)
        observed = {"chapter_id": str(chapter.id), "selected_version": version}
        if selector.version_policy == VersionPolicy.TARGET_VERSION:
            observed["current_pointer"] = current
        if record is None:
            return (), observed
        if selector.version_policy == VersionPolicy.APPROVED and (
            record.approved_at is None or record.status not in {Status.APPROVED, Status.LOCKED}
        ):
            return (), observed
        return (self._item(record, request, selector, chapter),), observed

    def _item(self, record, request, selector, chapter=None):
        source = selector.source_type
        logical_id = getattr(record, "logical_id", record.id)
        version = getattr(record, "version", getattr(record, "target_version", 1))
        locked = getattr(record, "locked", source == SourceType.LOCK)
        provenance = ["structured_database", f"version_policy:{selector.version_policy}"]
        if locked and source != SourceType.LOCK:
            lock = self.repo.lock(request.project_id, source, logical_id)
            locked = lock is not None and lock.target_version == version
            if lock:
                provenance.append(f"lock:{lock.id}")
        payload = {name: getattr(record, name) for name in FIELDS[source]}
        if source == SourceType.CHAPTER_VERSION and (
            request.task_type in QUALITY_TASKS
            or request.task_type in REVISION_TASKS | {"INTERPRET_CHAPTER_FEEDBACK"}
            and selector.selector_id == "target-version"
        ):
            from novel_os.quality.policy import indexed_paragraphs

            payload["paragraphs"] = indexed_paragraphs(record.content)
        if source == SourceType.CHAPTER and request.task_type in {
            "PLAN_CHAPTER",
            "REVIEW_CHAPTER_PLAN",
        }:
            # Pin both pointers for review/rework freshness without retrieving any latest draft.
            payload["current_plan_version"] = record.current_plan_version
            payload["approved_plan_version"] = record.approved_plan_version
        if source == SourceType.CHAPTER and request.task_type == "WRITE_CHAPTER":
            payload["approved_plan_version"] = record.approved_plan_version
            payload["current_version"] = record.current_version
        if source == SourceType.CHAPTER_PLAN and request.task_type in {
            "PLAN_CHAPTER",
            "REVIEW_CHAPTER_PLAN",
            "WRITE_CHAPTER",
            *QUALITY_TASKS,
            *REVISION_TASKS,
            "INTERPRET_CHAPTER_FEEDBACK",
        }:
            from novel_os.repositories.planning import PlanningRepository

            generation = PlanningRepository(self.session).generation(request.workflow_id, record.id)
            if generation:
                payload["planning"] = generation.body
        # UUIDs in typed relational fields are serialized explicitly, never generic config.
        payload = {
            name: str(value) if hasattr(value, "hex") else value for name, value in payload.items()
        }
        chapter_id = getattr(
            record, "chapter_id", record.id if source == SourceType.CHAPTER else None
        )
        sequence = chapter.sequence if chapter else getattr(record, "sequence", None)
        return ContextItem(
            context_item_id=uuid5(
                NAMESPACE_URL, f"{selector.selector_id}:{source}:{record.id}:{version}"
            ),
            selector_id=selector.selector_id,
            source_type=source,
            source_id=record.id,
            logical_id=logical_id,
            source_version=version,
            project_id=record.project_id,
            status=getattr(record, "status", Status.ACTIVE),
            authority_level=getattr(record, "authority_level", Authority.A1_USER_LOCKED),
            locked=locked,
            priority=selector.priority,
            scope=selector.scope,
            payload_json=canonical(payload),
            selected_reason=f"{selector.scope}/{selector.version_policy}",
            source_created_at=record.created_at,
            source_updated_at=getattr(record, "updated_at", record.created_at),
            chapter_id=chapter_id,
            chapter_sequence=sequence,
            relevance_score=100 if chapter_id == request.chapter_id else 50,
            future_knowledge=sequence is not None and sequence > request.chapter_sequence,
            is_plan=source == SourceType.CHAPTER_PLAN,
            provenance=tuple(provenance),
        )
