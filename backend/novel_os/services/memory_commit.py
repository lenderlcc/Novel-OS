"""Application-owned finalization, exact source checks and atomic memory writes."""

from dataclasses import asdict, replace
from uuid import UUID, uuid4

from novel_os.context.profiles import ContextProfile, ContextProfileRegistry
from novel_os.domain.agents import AgentId, AgentTask
from novel_os.domain.core import ObjectRef, now
from novel_os.domain.enums import AuditAction, ObjectType, Status
from novel_os.domain.errors import DomainError
from novel_os.domain.memory import (
    BLOCKING_CONFLICTS,
    MEMORY_TASK,
    CommittedMemory,
    MemoryCommitBatch,
    MemoryConflict,
    MemoryRequest,
    MemorySubject,
)
from novel_os.domain.workflow import ChapterState, WorkflowStatus
from novel_os.memory.policy import (
    comparable_value,
    normalize_candidates,
    normalized,
    validate_evidence,
)
from novel_os.memory.schemas import MemoryExtractionOutput
from novel_os.repositories.context_packages import ContextPackageRepository
from novel_os.repositories.memory import MemoryRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.workflows import WorkflowRepository
from novel_os.services.core_base import CoreService, validate_payload
from novel_os.services.quality_binding import QualityBindingService, supports_quality
from novel_os.services.versioning import ChapterVersionService


class MemoryCommitService:
    def __init__(self, session):
        self.session = session
        self.repo = MemoryRepository(session)
        self.core = CoreService(session)

    def snapshot(self, workflow, profile, timestamp):
        task = AgentTask(
            project_id=workflow.project_id,
            workflow_instance_id=workflow.id,
            workflow_state=ChapterState.C14_MEMORY_PREPARATION,
            workflow_state_version=workflow.state_version,
            agent_id=AgentId.A07_MEMORY,
            task_type=MEMORY_TASK,
            target_ref=workflow.chapter_id,
            objective="Extract only future-relevant information from the accepted chapter",
            expected_output_schema="chapter-memory-result.v1",
            created_at=timestamp,
        )
        data = QualityBindingService(self.session).current(task, workflow, profile)
        data.pop("state_version")
        locks = self.core.repo.list_locks(workflow.project_id, 1001, 0)
        if len(locks) > 1000:
            raise DomainError("CONTEXT_RETRIEVAL_LIMIT", "Memory lock snapshot exceeds capacity")
        data["locks"] = [asdict(lock) for lock in locks if lock.active]
        from pydantic_core import to_jsonable_python

        return to_jsonable_python(data)

    def prepare(self, workflow, command, context):
        context.require_user()
        validate_payload(command.payload, {"chapter_version_id", "reason"})
        if (
            not supports_quality(workflow)
            or workflow.status != WorkflowStatus.WAITING_HUMAN
            or workflow.current_state
            not in {ChapterState.C10_REVISION, ChapterState.C11_INTERNAL_PASS}
            or workflow.revision_request_id
            or workflow.human_feedback_id
            or workflow.memory_request_id
        ):
            raise DomainError("INVALID_STATE", "Completion requires an idle current Draft")
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        self.core.check_record_lock(chapter)
        draft = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION, chapter.project_id, chapter.id, chapter.current_version
        )
        if str(draft.id) != command.payload["chapter_version_id"]:
            raise DomainError("VERSION_CONFLICT", "Completion must bind the exact current Draft")
        self.check_review(chapter.project_id, chapter.id, draft.id)
        if chapter.approved_version != draft.version:
            ChapterVersionService(self.session).approve_in_transaction(
                chapter.project_id,
                chapter.id,
                draft.version,
                context,
                "User accepted chapter for memory extraction",
            )
        profile = ContextProfileRegistry().for_task(MEMORY_TASK)
        timestamp = now()
        return self.repo.add(
            MemoryRequest(
                id=command.event_id,
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                workflow_id=workflow.id,
                chapter_version_id=draft.id,
                draft_version=draft.version,
                return_state=workflow.current_state,
                profile_json=profile.model_dump_json(),
                authority_snapshot=self.snapshot(
                    replace(workflow, draft_version=draft.version), profile, timestamp
                ),
                canon_revision=self.repo.revision(chapter.project_id),
                accepted_by=context.actor_id,
                created_at=timestamp,
            )
        )

    def check_review(self, project_id, chapter_id, draft_id):
        reviews = QualityRepository(self.session).history(project_id, chapter_id, 100)
        review = next((r for r in reviews if r.chapter_version_id == draft_id), None)
        if review:
            # Review cannot grant authority; only actual blocking authority findings matter.
            issues = review.body.get("hard_gate_issues", [])
            if any(
                i.get("severity") == "P0"
                and i.get("code")
                in {"LOCKED_CONFLICT", "MAJOR_DIRECTION_VIOLATION", "AUTHORITY_CONFLICT"}
                for i in issues
            ):
                raise DomainError(
                    "AUTHORITY_DENIED",
                    "Resolve the blocking story authority conflict before completion",
                )

    def check(self, request, workflow):
        if (request.project_id, request.chapter_id, request.workflow_id) != (
            workflow.project_id,
            workflow.chapter_id,
            workflow.id,
        ):
            raise DomainError("AUTHORITY_DENIED", "Memory request belongs to another workflow")
        chapter = self.core.repo.get_chapter(request.project_id, request.chapter_id)
        self.core.check_record_lock(chapter)
        self.core.check_lock(request.project_id, ObjectRef(ObjectType.CHAPTER_VERSION, chapter.id))
        if (
            chapter.current_version != request.draft_version
            or chapter.approved_version != request.draft_version
        ):
            raise DomainError(
                "CONTEXT_STALE", "Accepted ChapterVersion changed; extract memory again"
            )
        profile = ContextProfile.model_validate_json(request.profile_json)
        ContextProfileRegistry().resolve(
            profile.profile_id, profile.version, expected_hash=profile.profile_hash
        )
        if (
            self.repo.revision(request.project_id) != request.canon_revision
            or self.snapshot(
                replace(workflow, draft_version=request.draft_version), profile, request.created_at
            )
            != request.authority_snapshot
        ):
            raise DomainError(
                "CONTEXT_STALE", "Canon, approved inputs or locks changed; extract memory again"
            )
        self.check_review(request.project_id, chapter.id, request.chapter_version_id)
        return request

    def for_task(self, task, workflow):
        if task.task_type != MEMORY_TASK or not workflow.memory_request_id:
            raise DomainError("CONTEXT_STALE", "Memory extraction is no longer active")
        return self.check(self.repo.get(MemoryRequest, workflow.memory_request_id), workflow)

    def normalize(self, output, request, package):
        draft = self.core.repo.get_version(
            ObjectType.CHAPTER_VERSION,
            request.project_id,
            request.chapter_id,
            request.draft_version,
        )
        boundaries = {
            (item.source_type, str(item.logical_id), item.source_version)
            for item in package.items
            if (
                item.source_type in {"REQUIREMENT", "DECISION", "CHAPTER_PLAN", "CHAPTER_VERSION"}
                and item.source_id != draft.id
                and (item.locked or item.authority_level.value <= "A4_APPROVED_PLAN")
            )
            or (
                item.source_type == "EXTENSION"
                and item.provenance[0] == "committed_memory"
                and item.authority_level.value == "A3_CANON"
            )
        }
        validate_evidence(output, request, draft.content, boundaries)
        chapter = self.core.repo.get_chapter(request.project_id, request.chapter_id)
        for candidate in output.candidates:
            if candidate.known_fact_id is not None:
                facts = self.repo.entries(
                    request.project_id,
                    entry_ids=[candidate.known_fact_id],
                    types=["CANON_FACT"],
                    before_sequence=chapter.sequence,
                    limit=1,
                )
                if not facts or comparable_value(facts[0].value) != comparable_value(
                    candidate.value
                ):
                    raise ValueError(
                        "Known fact must be a matching committed fact from an earlier chapter"
                    )
        subjects = self.repo.subjects(request.project_id)
        if len(subjects) > 500:
            raise DomainError(
                "CONTEXT_RETRIEVAL_LIMIT", "Subject resolution requires a narrower extraction scope"
            )

        def lookup(subject_id, kind, slot):
            values = self.repo.entries(
                request.project_id, subject_ids=[subject_id], types=[kind], slot=slot, limit=2
            )
            if len(values) > 1:
                raise ValueError("Memory attribute has multiple current versions")
            if (
                values
                and self.core.repo.get_chapter(request.project_id, values[0].chapter_id).sequence
                >= chapter.sequence
            ):
                raise DomainError(
                    "CONTEXT_STALE",
                    "Later state exists; reconcile before committing an earlier chapter",
                )
            return values[0] if values else None

        candidates = normalize_candidates(
            output,
            project_id=request.project_id,
            chapter_id=request.chapter_id,
            content=draft.content,
            subjects=subjects,
            lookup=lookup,
        )
        used_ids = {c["subject_id"] for c in candidates}
        for subject in subjects:
            if str(subject.id) in used_ids:
                batch = self.repo.get(MemoryCommitBatch, subject.batch_id)
                if (
                    self.core.repo.get_chapter(request.project_id, batch.chapter_id).sequence
                    >= chapter.sequence
                ):
                    raise DomainError(
                        "CONTEXT_STALE", "Later chapter identity requires reconciliation"
                    )
        return candidates

    def commit(self, workflow, command, context):
        context.require_user()
        validate_payload(command.payload, {"proposal_id", "selected_candidate_ids", "reason"})
        request = self.check(self.repo.get(MemoryRequest, workflow.memory_request_id), workflow)
        proposal = self.repo.proposal(request.id)
        if proposal is None or str(proposal.id) != command.payload["proposal_id"]:
            raise DomainError("VERSION_CONFLICT", "Confirm the active memory proposal")
        selected = command.payload["selected_candidate_ids"]
        if (
            not isinstance(selected, list)
            or any(not isinstance(i, str) for i in selected)
            or len(selected) != len(set(selected))
        ):
            raise DomainError("VALIDATION_ERROR", "Select unique candidate identifiers")
        package = ContextPackageRepository(self.session).get(proposal.context_package_id)
        output = MemoryExtractionOutput.model_validate(proposal.raw_output)
        candidates = self.normalize(output, request, package)
        if candidates != proposal.candidates:
            raise DomainError(
                "CONTEXT_STALE", "Memory proposal needs revalidation and renewed confirmation"
            )
        chosen = [c for c in candidates if c["id"] in selected]
        if len(chosen) != len(selected):
            raise DomainError("VALIDATION_ERROR", "Unknown memory candidate")
        if any(c["conflict_status"] in BLOCKING_CONFLICTS for c in chosen):
            raise DomainError(
                "CONTEXT_AUTHORITY_CONFLICT", "Selected memory contains unresolved conflicts"
            )
        selected_candidates = self.normalize(
            output.model_copy(
                update={"candidates": [c for c in output.candidates if c.id in selected]}
            ),
            request,
            package,
        )
        if any(
            candidate["subject_id"] != selected_candidate["subject_id"]
            or candidate["normalized_subject"] != selected_candidate["normalized_subject"]
            for candidate, selected_candidate in zip(chosen, selected_candidates, strict=True)
        ):
            raise DomainError(
                "CONTEXT_AUTHORITY_CONFLICT",
                "所选记忆的身份依赖未选候选，请调整选择或返回正文重新整理。",
            )
        skipped, selected_keys = [], set()
        for candidate in chosen:
            key = (candidate["subject_id"], candidate["candidate_type"], candidate["slot"])
            if (
                candidate["conflict_status"] == MemoryConflict.DUPLICATE
                and candidate["previous_entry_id"]
            ) or key in selected_keys:
                skipped.append(candidate["id"])
            selected_keys.add(key)
        batch = self.repo.add(
            MemoryCommitBatch(
                id=command.event_id,
                project_id=request.project_id,
                chapter_id=request.chapter_id,
                workflow_id=workflow.id,
                chapter_version_id=request.chapter_version_id,
                proposal_id=proposal.id,
                canon_revision=request.canon_revision + 1,
                selected_candidate_ids=selected,
                skipped_candidate_ids=skipped,
                expected_source_versions={
                    "canon_revision": request.canon_revision,
                    "authority_snapshot": request.authority_snapshot,
                },
                confirmed_by=context.actor_id,
            )
        )
        subjects = {s.id for s in self.repo.subjects(request.project_id)}
        for candidate in chosen:
            if candidate["id"] in skipped:
                continue
            subject_id = UUID(candidate["subject_id"]) if candidate["subject_id"] else None
            if subject_id and subject_id not in subjects:
                ref = candidate["normalized_subject"]
                self.repo.add(
                    MemorySubject(
                        id=subject_id,
                        project_id=request.project_id,
                        name=ref["name"],
                        normalized_name=normalized(ref["name"]),
                        kind=ref["kind"],
                        aliases=[normalized(a) for a in ref["aliases"]],
                        batch_id=batch.id,
                    )
                )
                subjects.add(subject_id)
            previous = (
                self.repo.get(CommittedMemory, UUID(candidate["previous_entry_id"]))
                if candidate["previous_entry_id"]
                else None
            )
            self.repo.add(
                CommittedMemory(
                    project_id=request.project_id,
                    chapter_id=request.chapter_id,
                    chapter_version_id=request.chapter_version_id,
                    batch_id=batch.id,
                    candidate_id=candidate["id"],
                    subject_id=subject_id,
                    logical_id=previous.logical_id if previous else uuid4(),
                    version=previous.version + 1 if previous else 1,
                    supersedes_id=previous.id if previous else None,
                    memory_type=candidate["candidate_type"],
                    slot=candidate["slot"],
                    value=candidate["value"],
                    statement=candidate["statement"],
                    epistemic_status=candidate["epistemic_status"],
                    authority_level=candidate["authority_level"],
                    body=candidate,
                )
            )
        chapter = self.core.repo.get_chapter(request.project_id, request.chapter_id)
        completed = self.core.repo.save(
            replace(chapter, status=Status.COMPLETED, version=chapter.version + 1, updated_at=now())
        )
        self.core.audit(
            completed,
            AuditAction.UPDATE,
            context,
            "User confirmed chapter memory",
            chapter,
            {
                "batch_id": str(batch.id),
                "proposal_id": str(proposal.id),
                "selected_candidate_ids": selected,
                "skipped_candidate_ids": skipped,
                "index": "transactional PostgreSQL indexes",
            },
        )
        return batch

    def history(self, workflow_id, limit=50, offset=0):
        workflow = WorkflowRepository(self.session).get(workflow_id)
        result = []
        batch = self.repo.batch(workflow.chapter_id)
        for request in self.repo.history(workflow.id, limit, offset):
            proposal = self.repo.proposal(request.id)
            committed = batch if proposal and batch and batch.proposal_id == proposal.id else None
            status = (
                "COMMITTED"
                if committed
                else "CANCELLED"
                if request.id != workflow.memory_request_id
                else "PROPOSED"
                if proposal
                else "EXTRACTING"
            )
            if status in {"EXTRACTING", "PROPOSED"}:
                try:
                    self.check(request, workflow)
                except DomainError:
                    status = "STALE"
            result.append(
                dict(
                    request=asdict(request),
                    proposal=asdict(proposal) if proposal else None,
                    status=status,
                    batch=asdict(committed) if committed else None,
                    entries=[
                        asdict(e)
                        for e in self.repo.entries(
                            request.project_id, batch_id=committed.id, historical=True
                        )
                    ]
                    if committed
                    else [],
                )
            )
        return result

    def memories(
        self,
        project_id,
        *,
        subject_id=None,
        memory_type=None,
        historical=False,
        limit=100,
        offset=0,
    ):
        self.core.repo.get_project(project_id)
        return self.repo.entries(
            project_id,
            subject_ids=[subject_id] if subject_id else None,
            types=[memory_type] if memory_type else None,
            historical=historical,
            limit=limit,
            offset=offset,
        )
