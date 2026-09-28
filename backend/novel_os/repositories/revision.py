"""Flush-only append operations. Application services own transactions."""

from dataclasses import asdict, fields

from sqlalchemy import select

from novel_os.domain.errors import DomainError
from novel_os.domain.quality import QualityBinding
from novel_os.domain.revision import (
    RevisionCandidate,
    RevisionPlan,
    RevisionRequest,
    RevisionResult,
)
from novel_os.models.quality import QualityBindingModel
from novel_os.models.revision import (
    RevisionCandidateModel,
    RevisionPlanModel,
    RevisionRequestModel,
    RevisionResultModel,
)

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
            .join(
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
