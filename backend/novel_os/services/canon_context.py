"""Committed memory adapter for NOVEL-006 with a fail-closed knowledge firewall."""

from dataclasses import asdict
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic_core import to_jsonable_python

from novel_os.domain.context import ContextItem, KnowledgeScope, SourceType
from novel_os.domain.enums import Authority, ObjectType, Status
from novel_os.domain.memory import CommittedMemory, MemoryCommitBatch, MemoryType
from novel_os.prompts.contracts import canonical
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.memory import MemoryRepository

MEMORY_SELECTORS = {"committed-memory", "memory-subjects"}


class CanonContextReader:
    def __init__(self, session):
        self.repo = MemoryRepository(session)
        self.core = CoreRepository(session)

    def query(self, request, selector):
        text = request.objective
        if request.task_type == "EXTRACT_CHAPTER_MEMORY":
            text = self.core.get_version(
                ObjectType.CHAPTER_VERSION,
                request.project_id,
                request.chapter_id,
                request.target_version,
            ).content
        elif request.approved_plan_version:
            plan = self.core.get_version(
                ObjectType.CHAPTER_PLAN,
                request.project_id,
                request.chapter_id,
                request.approved_plan_version,
            )
            text = canonical(
                {
                    "objective": plan.objective,
                    "scenes": plan.scene_plans,
                    "progression": plan.character_progression,
                }
            )
        subjects = self.repo.subjects_in_text(
            request.project_id, text, 100, before_sequence=request.chapter_sequence
        )
        ids = [s.id for s in subjects]
        writer = request.task_type == "WRITE_CHAPTER"
        if writer:
            # An unbound/multiple POV is not permission to reveal private or global knowledge.
            ids = [request.character_id] if request.character_id is not None else []
        if selector.selector_id == "memory-subjects":
            items = tuple(
                self.item(
                    s,
                    request,
                    selector,
                    {"subject": to_jsonable_python(asdict(s)), "role": "IDENTITY_ONLY"},
                )
                for s in subjects
            )
            return items, {}
        types = (
            [
                MemoryType.CHARACTER_KNOWLEDGE,
                MemoryType.CHARACTER_STATE,
                MemoryType.RELATIONSHIP_STATE,
            ]
            if writer
            else None
        )
        entries = self.repo.entries(
            request.project_id,
            subject_ids=ids,
            types=types,
            before_sequence=request.chapter_sequence,
            limit=selector.max_items + 1,
        )
        if writer:
            fact_ids = [
                UUID(e.body["known_fact_id"])
                for e in entries
                if e.memory_type == MemoryType.CHARACTER_KNOWLEDGE
                and e.epistemic_status == "KNOWS"
                and e.body.get("known_fact_id")
            ]
            entries.extend(
                self.repo.entries(
                    request.project_id,
                    entry_ids=fact_ids,
                    types=[MemoryType.CANON_FACT],
                    before_sequence=request.chapter_sequence,
                    limit=selector.max_items + 1,
                )
            )
        elif request.task_type == "PLAN_CHAPTER":
            # Summaries are derived retrieval hints, selected only from recent prior chapters.
            entries.extend(
                self.repo.entries(
                    request.project_id,
                    types=[MemoryType.DERIVED_CHAPTER_SUMMARY],
                    before_sequence=request.chapter_sequence,
                    limit=3,
                )
            )
        items = tuple(
            self.item(
                e,
                request,
                selector,
                {
                    "memory_type": e.memory_type,
                    "subject_id": str(e.subject_id) if e.subject_id else None,
                    "statement": e.statement,
                    "slot": e.slot,
                    "value": e.value,
                    "epistemic_status": e.epistemic_status,
                    "role": "DERIVED_HINT"
                    if e.authority_level == Authority.A6_DERIVED_MEMORY
                    else "COMMITTED_MEMORY",
                    "source_chapter_version_id": str(e.chapter_version_id),
                    "known_fact_id": e.body.get("known_fact_id"),
                },
            )
            for e in entries
        )
        return items, {}

    def item(self, record, request, selector, payload):
        entry = isinstance(record, CommittedMemory)
        knowledge = entry and record.memory_type == MemoryType.CHARACTER_KNOWLEDGE
        timestamp = (
            record.created_at
            if entry
            else self.repo.get(
                MemoryCommitBatch,
                record.batch_id,
            ).committed_at
        )
        return ContextItem(
            context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
            selector_id=selector.selector_id,
            source_type=SourceType.EXTENSION,
            source_id=record.id,
            logical_id=record.logical_id if entry else record.id,
            source_version=record.version if entry else 1,
            project_id=request.project_id,
            status=Status.ACTIVE,
            authority_level=Authority(record.authority_level) if entry else Authority.A3_CANON,
            locked=False,
            priority=selector.priority,
            scope=selector.scope,
            payload_json=canonical(payload),
            selected_reason="Committed, relevant, prior-chapter memory",
            source_created_at=timestamp,
            source_updated_at=timestamp,
            knowledge_scope=KnowledgeScope.CHARACTER_KNOWLEDGE
            if knowledge
            else KnowledgeScope.GLOBAL_ONLY,
            character_id=record.subject_id if knowledge else None,
            provenance=("committed_memory" if entry else "memory_subject", str(record.batch_id)),
        )
