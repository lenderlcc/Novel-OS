from dataclasses import asdict

from sqlalchemy import select

from novel_os.domain.errors import DomainError
from novel_os.domain.feedback import HumanFeedback, HumanFeedbackInterpretation
from novel_os.models.feedback import FeedbackInterpretationModel, HumanFeedbackModel
from novel_os.repositories.revision import RevisionRepository


class FeedbackRepository:
    def __init__(self, session):
        self.session = session

    def add(self, record):
        model = (
            HumanFeedbackModel if isinstance(record, HumanFeedback) else FeedbackInterpretationModel
        )
        self.session.add(model(**asdict(record)))
        self.session.flush()
        return record

    def get(self, feedback_id):
        record = RevisionRepository.entity(
            self.session.get(HumanFeedbackModel, feedback_id), HumanFeedback
        )
        if record is None:
            raise DomainError("NOT_FOUND", "Human feedback not found")
        return record

    def interpretation(self, feedback_id):
        row = self.session.scalar(
            select(FeedbackInterpretationModel).where(
                FeedbackInterpretationModel.feedback_id == feedback_id
            )
        )
        return RevisionRepository.entity(row, HumanFeedbackInterpretation)

    def clarifications(self, feedback):
        """Only this immutable reply chain, oldest first; never unrelated feedback."""
        chain = []
        while feedback.reply_to_feedback_id is not None:
            feedback = self.get(feedback.reply_to_feedback_id)
            interpretation = self.interpretation(feedback.id)
            chain.append(
                {
                    "feedback_id": str(feedback.id),
                    "raw_feedback": feedback.raw_feedback,
                    "decision_question": interpretation.body["decision_question"],
                }
            )
        return list(reversed(chain))

    def history(self, workflow_id, limit, offset):
        rows = self.session.execute(
            select(HumanFeedbackModel, FeedbackInterpretationModel)
            .outerjoin(
                FeedbackInterpretationModel,
                FeedbackInterpretationModel.feedback_id == HumanFeedbackModel.id,
            )
            .where(HumanFeedbackModel.workflow_id == workflow_id)
            .order_by(HumanFeedbackModel.source_state_version.desc(), HumanFeedbackModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            (
                RevisionRepository.entity(f, HumanFeedback),
                RevisionRepository.entity(i, HumanFeedbackInterpretation),
            )
            for f, i in rows
        ]
