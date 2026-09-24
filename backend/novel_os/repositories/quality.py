"""Review persistence has no commit, update or delete operations."""

from dataclasses import asdict, fields

from sqlalchemy import func, select

from novel_os.domain.quality import ChapterQualityReview, QualityBinding, QualityPass
from novel_os.models.quality import ChapterQualityReviewModel, QualityBindingModel, QualityPassModel

MODELS = {
    QualityBinding: QualityBindingModel,
    QualityPass: QualityPassModel,
    ChapterQualityReview: ChapterQualityReviewModel,
}


class QualityRepository:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def entity(row, kind):
        return kind(**{f.name: getattr(row, f.name) for f in fields(kind)}) if row else None

    def add(self, record):
        self.session.add(MODELS[type(record)](**asdict(record)))
        self.session.flush()
        return record

    def binding(self, workflow_id, state_version):
        return self.entity(
            self.session.scalar(
                select(QualityBindingModel).where(
                    QualityBindingModel.workflow_id == workflow_id,
                    QualityBindingModel.state_version == state_version,
                )
            ),
            QualityBinding,
        )

    def binding_by_id(self, binding_id):
        return self.entity(self.session.get(QualityBindingModel, binding_id), QualityBinding)

    def latest_binding(self, workflow_id):
        return self.entity(
            self.session.scalar(
                select(QualityBindingModel)
                .where(QualityBindingModel.workflow_id == workflow_id)
                .order_by(QualityBindingModel.state_version.desc())
                .limit(1)
            ),
            QualityBinding,
        )

    def pass_for(self, binding_id, pass_name):
        return self.entity(
            self.session.scalar(
                select(QualityPassModel).where(
                    QualityPassModel.binding_id == binding_id,
                    QualityPassModel.pass_name == pass_name,
                )
            ),
            QualityPass,
        )

    def next_version(self, chapter_id):
        return (
            self.session.scalar(
                select(func.max(ChapterQualityReviewModel.version)).where(
                    ChapterQualityReviewModel.chapter_id == chapter_id
                )
            )
            or 0
        ) + 1

    def get(self, review_id):
        return self.entity(
            self.session.get(ChapterQualityReviewModel, review_id), ChapterQualityReview
        )

    def history(self, project_id, chapter_id, limit=100, offset=0):
        return [
            self.entity(r, ChapterQualityReview)
            for r in self.session.scalars(
                select(ChapterQualityReviewModel)
                .where(
                    ChapterQualityReviewModel.project_id == project_id,
                    ChapterQualityReviewModel.chapter_id == chapter_id,
                )
                .order_by(ChapterQualityReviewModel.version.desc())
                .limit(limit)
                .offset(offset)
            )
        ]
