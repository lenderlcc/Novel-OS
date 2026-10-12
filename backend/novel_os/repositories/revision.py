"""Flush-only append operations. Application services own transactions."""

from dataclasses import asdict, fields

from sqlalchemy import select
from sqlalchemy.orm import aliased

from novel_os.domain.core import ChapterVersion
from novel_os.domain.errors import DomainError
from novel_os.domain.quality import QualityBinding
from novel_os.domain.revision import (
    RevisionCandidate,
    RevisionPlan,
    RevisionRequest,
    RevisionResult,
)
from novel_os.models.core import ChapterVersionModel
from novel_os.models.quality import QualityBindingModel
from novel_os.models.revision import (
    RevisionCandidateModel,
    RevisionPlanModel,
    RevisionRequestModel,
    RevisionResultModel,
)
from novel_os.repositories.core import to_domain

MODELS = {
    RevisionRequest: RevisionRequestModel,
    RevisionPlan: RevisionPlanModel,
    RevisionResult: RevisionResultModel,
    RevisionCandidate: RevisionCandidateModel,
}


class RevisionRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def entity(row, kind):
        return kind(**{f.name: getattr(row, f.name) for f in fields(kind)}) if row else None

    def add(self, record):
        self.session.add(MODELS[type(record)](**asdict(record)))
        self.session.flush()
        return record

    def get(self, request_id):
        record = self.entity(self.session.get(RevisionRequestModel, request_id), RevisionRequest)
        if record is None:
            raise DomainError("NOT_FOUND", "Revision request not found")
        return record

    def evidence(self, request_id, kind=RevisionPlan):
        model = MODELS[kind]
        return self.entity(
            self.session.scalar(select(model).where(model.request_id == request_id)), kind
        )

    def review_evidence(self, project_id, chapter_id, workflow_id, target_version):
        """The revision that produced this exact Draft, regardless of active request."""
        source, target = aliased(ChapterVersionModel), aliased(ChapterVersionModel)
        rows = self.session.execute(
            select(RevisionRequestModel, RevisionPlanModel, RevisionResultModel, source)
            .join(RevisionPlanModel, RevisionPlanModel.request_id == RevisionRequestModel.id)
            .join(
                RevisionResultModel,
                (RevisionResultModel.request_id == RevisionRequestModel.id)
                & (RevisionResultModel.revision_plan_id == RevisionPlanModel.id),
            )
            .join(target, target.id == RevisionResultModel.chapter_version_id)
            .join(source, source.id == RevisionRequestModel.source_chapter_version_id)
            .where(
                RevisionRequestModel.project_id == project_id,
                RevisionRequestModel.chapter_id == chapter_id,
                RevisionRequestModel.workflow_id == workflow_id,
                target.project_id == project_id,
                target.chapter_id == chapter_id,
                target.version == target_version,
                source.project_id == project_id,
                source.chapter_id == chapter_id,
            )
        ).one_or_none()
        if rows is None:
            return None
        request, plan, result, source_row = rows
        return (
            self.entity(request, RevisionRequest),
            self.entity(plan, RevisionPlan),
            self.entity(result, RevisionResult),
            to_domain(source_row, ChapterVersion),
        )

    def history_bundles(self, workflow_id, limit, offset):
        query = (
            select(
                RevisionRequestModel,
                RevisionPlanModel,
                RevisionResultModel,
                QualityBindingModel,
                RevisionCandidateModel,
            )
            .outerjoin(RevisionPlanModel, RevisionPlanModel.request_id == RevisionRequestModel.id)
            .outerjoin(
                RevisionResultModel, RevisionResultModel.request_id == RevisionRequestModel.id
            )
            .outerjoin(
                RevisionCandidateModel, RevisionCandidateModel.request_id == RevisionRequestModel.id
            )
            .outerjoin(
                QualityBindingModel,
                QualityBindingModel.id == RevisionRequestModel.source_binding_id,
            )
            .where(RevisionRequestModel.workflow_id == workflow_id)
            .order_by(RevisionRequestModel.created_at.desc(), RevisionRequestModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            tuple(
                self.entity(row, kind)
                for row, kind in zip(
                    rows,
                    (
                        RevisionRequest,
                        RevisionPlan,
                        RevisionResult,
                        QualityBinding,
                        RevisionCandidate,
                    ),
                    strict=True,
                )
            )
            for rows in self.session.execute(query)
        ]
