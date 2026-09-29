"""Built-in exact extension reader. Review advice never gains Story Authority."""

from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceType
from novel_os.domain.enums import Authority, Status
from novel_os.domain.revision import RevisionCandidate
from novel_os.prompts.contracts import canonical
from novel_os.quality.policy import indexed_paragraphs
from novel_os.repositories.quality import QualityRepository
from novel_os.repositories.revision import RevisionRepository
from novel_os.repositories.workflows import WorkflowRepository

REVISION_SELECTORS = {
    "revision-contract",
    "source-quality-review",
    "revision-plan",
    "revision-candidate",
}


class RevisionContextReader:
    def __init__(self, session):
        self.session = session

    def query(self, request, selector):
        workflow = WorkflowRepository(self.session).get(request.workflow_id)
        if workflow.revision_request_id is None:
            return (), {"revision_request_id": None}
        repo = RevisionRepository(self.session)
        revision = repo.get(workflow.revision_request_id)
        if selector.selector_id == "revision-contract":
            record, payload = (
                revision,
                {
                    **revision.contract,
                    "source_chapter_version_id": str(revision.source_chapter_version_id),
                    "source_review_id": str(revision.source_review_id)
                    if revision.source_review_id
                    else None,
                },
            )
        elif selector.selector_id == "source-quality-review":
            if revision.source_review_id is None:
                return (), {"review_id": None}
            record = QualityRepository(self.session).get(revision.source_review_id)
            payload = record.body
        elif selector.selector_id == "revision-candidate":
            record = repo.evidence(revision.id, RevisionCandidate)
            if record is None:
                return (), {"candidate_id": None}
            payload = {**record.body, "candidate_id": str(record.id)}
            if record.body["content"] is not None:
                payload["paragraphs"] = indexed_paragraphs(record.body["content"])
        else:
            record = repo.evidence(revision.id)
            if record is None:
                return (), {"plan_id": None}
            payload = {**record.body, "revision_plan_id": str(record.id)}
        return (
            ContextItem(
                context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
                selector_id=selector.selector_id,
                source_type=SourceType.EXTENSION,
                source_id=record.id,
                logical_id=record.id,
                source_version=1,
                project_id=revision.project_id,
                chapter_id=revision.chapter_id,
                chapter_sequence=request.chapter_sequence,
                status=Status.ACTIVE,
                authority_level=Authority.A7_AI_INFERENCE,
                locked=False,
                priority=selector.priority,
                scope=selector.scope,
                payload_json=canonical(payload),
                selected_reason="Exact revision request evidence, not story authority",
                source_created_at=record.created_at,
                source_updated_at=record.created_at,
                provenance=("revision_request", str(revision.id)),
            ),
        ), {"revision_request_id": str(revision.id)}
