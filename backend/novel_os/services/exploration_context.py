"""Bounded planning history and exact selected inference; rejected ideas stay in Debug."""

from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceRef, SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.domain.memory import MemoryType
from novel_os.prompts.contracts import canonical
from novel_os.repositories.context_sources import ContextSourceRepository
from novel_os.repositories.memory import MemoryRepository
from novel_os.repositories.planning import PlanningRepository
from novel_os.services.canon_context import CanonContextReader

SELECTED_CONCEPT_SELECTOR = "selected-creative-concept"
RECENT_SUMMARIES_SELECTOR = "recent-final-summaries"
EXPLORATION_SELECTORS = {SELECTED_CONCEPT_SELECTOR, RECENT_SUMMARIES_SELECTOR}


def selected_candidate(artifact):
    return next(
        (
            candidate
            for candidate in artifact.body["candidates"]
            if candidate["id"] == artifact.body["selected_candidate_id"]
        ),
        None,
    )


def selected_concept_refs(session, workflow):
    from novel_os.services.exploration_policy import ExplorationPolicy

    exploration = ExplorationPolicy(session).selected(workflow)
    if exploration is None:
        return (), ()
    return (SourceRef(source_type=SourceType.EXTENSION, logical_id=exploration.id, version=1),), ()


class ExplorationContextReader:
    def __init__(self, session):
        self.session = session
        self.planning = PlanningRepository(session)
        self.sources = ContextSourceRepository(session)

    def query(self, request, selector):
        if selector.selector_id == RECENT_SUMMARIES_SELECTOR:
            return self.recent_summaries(request, selector)
        return self.selected_concept(request, selector)

    def selected_concept(self, request, selector):
        if request.task_type != "PLAN_CHAPTER":
            return (), {}
        brief = self.planning.brief(request.workflow_id)
        current = self.planning.exploration(request.workflow_id, brief.id) if brief else None
        observed = {"current_exploration": str(current.id) if current else None}
        if current is None or current.status != "READY":
            return (), observed
        ref = SourceRef(source_type=SourceType.EXTENSION, logical_id=current.id, version=1)
        if ref not in request.explicit_refs:
            return (), observed
        artifact = self.planning.exploration_by_id(ref.logical_id)
        if artifact is None or (
            artifact.project_id,
            artifact.chapter_id,
            artifact.workflow_id,
            artifact.brief_id,
        ) != (request.project_id, request.chapter_id, request.workflow_id, brief.id):
            return (), observed
        selected = selected_candidate(artifact)
        if selected is None:
            return (), observed
        payload = {
            "creative_exploration_id": str(artifact.id),
            "brief_id": str(artifact.brief_id),
            "selected_candidate_id": artifact.body["selected_candidate_id"],
            "selected_candidate": selected,
            "role": "SELECTED_INFERENCE_NOT_PLAN",
        }
        return (
            ContextItem(
                context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{artifact.id}"),
                selector_id=selector.selector_id,
                source_type=SourceType.EXTENSION,
                source_id=artifact.id,
                logical_id=artifact.id,
                source_version=1,
                project_id=artifact.project_id,
                chapter_id=artifact.chapter_id,
                chapter_sequence=request.chapter_sequence,
                status=Status.ACTIVE,
                authority_level=Authority.A7_AI_INFERENCE,
                locked=False,
                priority=selector.priority,
                scope=selector.scope,
                payload_json=canonical(payload),
                selected_reason="Exact selected inference; not an approved Plan or Canon",
                source_created_at=artifact.created_at,
                source_updated_at=artifact.created_at,
                provenance=("creative_exploration", str(artifact.agent_run_id)),
            ),
        ), observed

    def recent_summaries(self, request, selector):
        memory = MemoryRepository(self.session)
        reader = CanonContextReader(self.session)
        items, observed = [], []
        for chapter in self.sources.recent_approved(
            request.project_id, request.chapter_sequence, min(selector.max_items, 3)
        ):
            batch = memory.batch(chapter.id)
            observed.append((str(chapter.id), str(batch.id) if batch else None))
            if batch is None:
                continue
            for entry in memory.entries(
                request.project_id,
                types=[MemoryType.DERIVED_CHAPTER_SUMMARY],
                before_sequence=request.chapter_sequence,
                batch_id=batch.id,
                limit=1,
            ):
                # Match committed-memory's compact shape: the same immutable entry
                # can also be selected there and must deduplicate without conflict.
                item = reader.item(
                    entry,
                    request,
                    selector,
                    {
                        "memory_type": entry.memory_type,
                        "subject_id": str(entry.subject_id) if entry.subject_id else None,
                        "statement": entry.statement,
                        "slot": entry.slot,
                        "value": entry.value,
                        "state_after": entry.body.get("state_after"),
                        "epistemic_status": entry.epistemic_status,
                        "role": "DERIVED_HINT",
                        "source_chapter_version_id": str(entry.chapter_version_id),
                        "known_fact_id": entry.body.get("known_fact_id"),
                    },
                )
                items.append(
                    replace(item, chapter_id=chapter.id, chapter_sequence=chapter.sequence)
                )
        return tuple(items), {"recent_final_chapters": observed}
