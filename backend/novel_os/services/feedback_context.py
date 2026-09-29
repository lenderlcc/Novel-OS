"""Exact feedback projection; optional Review remains diagnosis, never authority."""

from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.prompts.contracts import canonical
from novel_os.repositories.feedback import FeedbackRepository
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.repositories.workflows import WorkflowRepository

FEEDBACK_SELECTORS = {"human-feedback", "feedback-review", "revision-human-feedback"}


class FeedbackContextReader:
    def __init__(self, session):
        self.session = session

    def query(self, request, selector):
        workflow = WorkflowRepository(self.session).get(request.workflow_id)
        feedback_id = workflow.human_feedback_id
        if selector.selector_id == "revision-human-feedback":
            revision = RevisionRepository(self.session).get(workflow.revision_request_id)
            feedback_id = revision.source_feedback_id
        if feedback_id is None:
            return (), {"feedback_id": None}
        repo = FeedbackRepository(self.session)
        feedback = repo.get(feedback_id)
        record = feedback
        payload = {
            "feedback_id": str(feedback.id),
            "source_chapter_version_id": str(feedback.source_chapter_version_id),
            "raw_feedback": feedback.raw_feedback,
            "source": "USER",
            "role": "EXPLICIT_REVISION_DIRECTION",
        }
        if feedback.reply_to_feedback_id is not None:
            payload["clarifications"] = repo.clarifications(feedback)
        if selector.selector_id == "feedback-review":
            record = (
                QualityRepository(self.session).get(feedback.source_review_id)
                if feedback.source_review_id
                else None
            )
            if record is None:
                return (), {"review_id": None}
            from novel_os.revision.policy import review_targets

            payload = {
                "review_id": str(record.id),
                "body": record.body,
                "target_issues": review_targets(record),
                "role": "DIAGNOSIS_ONLY",
            }
        elif selector.selector_id == "revision-human-feedback":
            interpretation = repo.interpretation(feedback.id)
            if interpretation is None:
                return (), {"interpretation_id": None}
            payload["interpretation"] = interpretation.body
            payload["interpretation_id"] = str(interpretation.id)
        return (
            ContextItem(
                context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
                selector_id=selector.selector_id,
                source_type=SourceType.EXTENSION,
                source_id=record.id,
                logical_id=record.id,
                source_version=1,
                project_id=feedback.project_id,
                chapter_id=feedback.chapter_id,
                chapter_sequence=request.chapter_sequence,
                status=Status.ACTIVE,
                authority_level=Authority.A7_AI_INFERENCE,
                locked=False,
                priority=selector.priority,
                scope=selector.scope,
                payload_json=canonical(payload),
                selected_reason=payload["role"],
                source_created_at=record.created_at,
                source_updated_at=record.created_at,
                provenance=("human_feedback", str(feedback.id)),
            ),
        ), {"feedback_id": str(feedback.id)}
