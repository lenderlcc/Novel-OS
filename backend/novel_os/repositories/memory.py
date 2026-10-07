"""Bounded SQL retrieval and flush-only persistence. No model/API dependencies."""

from dataclasses import asdict

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import aliased

from novel_os.domain.errors import DomainError
from novel_os.domain.memory import (
    CommittedMemory,
    MemoryCommitBatch,
    MemoryCommitProposal,
    MemoryRequest,
    MemorySubject,
)
from novel_os.memory.policy import normalized
from novel_os.models.core import ChapterModel
from novel_os.models.memory import (
    MemoryBatchModel,
    MemoryEntryModel,
    MemoryProposalModel,
    MemoryRequestModel,
    MemorySubjectModel,
)
from novel_os.repositories.revision import RevisionRepository

MODELS = {
    MemoryRequest: MemoryRequestModel,
    MemoryCommitProposal: MemoryProposalModel,
    MemoryCommitBatch: MemoryBatchModel,
    MemorySubject: MemorySubjectModel,
    CommittedMemory: MemoryEntryModel,
}


class MemoryRepository:
    def __init__(self, session):
        self.session = session

    def add(self, record):
        self.session.add(MODELS[type(record)](**asdict(record)))
        self.session.flush()
        return record

    def get(self, kind, record_id):
        result = RevisionRepository.entity(self.session.get(MODELS[kind], record_id), kind)
        if result is None:
            raise DomainError("NOT_FOUND", "Memory record not found")
        return result

    def proposal(self, request_id):
        return RevisionRepository.entity(
            self.session.scalar(
                select(MemoryProposalModel).where(MemoryProposalModel.request_id == request_id)
            ),
            MemoryCommitProposal,
        )

    def batch(self, chapter_id):
        return RevisionRepository.entity(
            self.session.scalar(
                select(MemoryBatchModel).where(MemoryBatchModel.chapter_id == chapter_id)
            ),
            MemoryCommitBatch,
        )

    def revision(self, project_id):
        return (
            self.session.scalar(
                select(func.max(MemoryBatchModel.canon_revision)).where(
                    MemoryBatchModel.project_id == project_id
                )
            )
            or 0
        )

    def subjects(self, project_id, *, kind=None, limit=501, offset=0):
        query = select(MemorySubjectModel).where(MemorySubjectModel.project_id == project_id)
        if kind:
            query = query.where(MemorySubjectModel.kind == kind)
        return [
            RevisionRepository.entity(row, MemorySubject)
            for row in self.session.scalars(
                query.order_by(MemorySubjectModel.normalized_name, MemorySubjectModel.id)
                .limit(limit)
                .offset(offset)
            )
        ]

    def entries(
        self,
        project_id,
        *,
        subject_ids=None,
        types=None,
        historical=False,
        before_sequence=None,
        batch_id=None,
        slot=None,
        entry_ids=None,
        limit=100,
        offset=0,
    ):
        model = MemoryEntryModel
        query = select(model).where(model.project_id == project_id)
        if not historical:
            successor = aliased(model)
            successors = select(successor.id).where(successor.supersedes_id == model.id)
            if before_sequence is not None:
                successor_chapter = aliased(ChapterModel)
                successors = successors.join(
                    successor_chapter, successor_chapter.id == successor.chapter_id
                ).where(successor_chapter.sequence < before_sequence)
            query = query.where(~exists(successors))
        if subject_ids is not None:
            query = query.where(model.subject_id.in_(subject_ids))
        if types is not None:
            query = query.where(model.memory_type.in_(types))
        if before_sequence is not None:
            query = query.join(ChapterModel, ChapterModel.id == model.chapter_id).where(
                ChapterModel.sequence < before_sequence
            )
        if batch_id:
            query = query.where(model.batch_id == batch_id)
        if entry_ids is not None:
            query = query.where(model.id.in_(entry_ids))
        if slot:
            query = query.where(model.slot == slot)
        query = query.order_by(model.created_at.desc(), model.id).limit(limit).offset(offset)
        return [
            RevisionRepository.entity(row, CommittedMemory) for row in self.session.scalars(query)
        ]

    def subjects_in_text(
        self, project_id, text, limit=50, before_sequence=None, *, explicit_ids=()
    ):
        # A project-scoped name lookup, not retrieval of every memory or a vector search.
        # Structured story leaves stay separate; their boundary cannot invent a name.
        search_text = "\n".join(normalized(part) for part in text.splitlines())
        alias = (
            func.jsonb_array_elements_text(MemorySubjectModel.aliases)
            .table_valued("value")
            .alias("subject_alias")
        )
        query = (
            select(MemorySubjectModel)
            .where(
                MemorySubjectModel.project_id == project_id,
                or_(
                    MemorySubjectModel.id.in_(explicit_ids),
                    func.strpos(search_text, MemorySubjectModel.normalized_name) > 0,
                    exists(
                        select(1)
                        .select_from(alias)
                        .where(func.strpos(search_text, alias.c.value) > 0)
                    ),
                ),
                or_(
                    MemorySubjectModel.batch_id.is_(None),
                    MemorySubjectModel.batch_id.in_(
                        select(MemoryBatchModel.id)
                        .join(ChapterModel, ChapterModel.id == MemoryBatchModel.chapter_id)
                        .where(ChapterModel.sequence < before_sequence)
                    ),
                )
                if before_sequence is not None
                else True,
            )
            .order_by(MemorySubjectModel.normalized_name)
            .limit(limit)
        )
        return [
            RevisionRepository.entity(row, MemorySubject) for row in self.session.scalars(query)
        ]

    def history(self, workflow_id, limit=50, offset=0):
        requests = self.session.scalars(
            select(MemoryRequestModel)
            .where(MemoryRequestModel.workflow_id == workflow_id)
            .order_by(MemoryRequestModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [RevisionRepository.entity(row, MemoryRequest) for row in requests]
