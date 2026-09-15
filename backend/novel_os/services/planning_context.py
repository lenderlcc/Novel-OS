"""Exact structured planning sources; no semantic search or new Memory domain."""

from uuid import NAMESPACE_URL, uuid5

from novel_os.domain.context import ContextItem, SourceRef, SourceType
from novel_os.domain.enums import Authority, ObjectType, Status
from novel_os.domain.planning import BriefStatus
from novel_os.prompts.contracts import canonical
from novel_os.repositories.context_sources import ContextSourceRepository
from novel_os.repositories.core import CoreRepository
from novel_os.repositories.planning import PlanningRepository


def planning_refs(session, task_type, workflow):
    repo = PlanningRepository(session)
    brief = repo.brief(workflow.id)
    refs, missing = [], []
    if brief is None or brief.status != BriefStatus.READY:
        missing.append("workflow.current_creative_brief")
    else:
        refs.append(
            SourceRef(
                source_type=SourceType.CREATIVE_BRIEF, logical_id=workflow.id, version=brief.version
            )
        )
    if workflow.plan_version is not None:
        plan = CoreRepository(session).get_version(
            ObjectType.CHAPTER_PLAN, workflow.project_id, workflow.chapter_id, workflow.plan_version
        )
        generation = repo.generation(workflow.id, plan.id)
        if brief is None or generation is None or generation.brief_id != brief.id:
            if task_type == "REVIEW_CHAPTER_PLAN":
                missing.append("workflow.plan_for_current_brief")
            return tuple(refs), missing
        # Current draft is deliberately included only as the exact plan being reviewed/reworked.
        refs.append(
            SourceRef(
                source_type=SourceType.CHAPTER_PLAN,
                logical_id=workflow.chapter_id,
                version=plan.version,
            )
        )
        # A05 reviews a proposal, so generic approved-plan dependency expansion does
        # not apply. Only this workflow's validated generation can grant exact refs.
        if task_type == "REVIEW_CHAPTER_PLAN":
            from novel_os.agents.planning_schemas import ChapterPlanOutput

            sources = ContextSourceRepository(session)
            for dependency in ChapterPlanOutput.model_validate(generation.body).locked_dependencies:
                ref = SourceRef(
                    source_type=dependency.source_type,
                    logical_id=dependency.logical_id,
                    version=dependency.version,
                )
                refs.append(ref)
                lock = sources.lock(workflow.project_id, ref.source_type, ref.logical_id)
                if lock is None or lock.target_version != ref.version:
                    missing.append(
                        f"locked_dependency:{ref.source_type}:{ref.logical_id}:v{ref.version}"
                    )
        report = repo.review(workflow.id, plan.id)
        if report and task_type == "PLAN_CHAPTER":
            refs.append(
                SourceRef(
                    source_type=SourceType.PLAN_REVIEW_REPORT, logical_id=report.id, version=1
                )
            )
    elif task_type == "REVIEW_CHAPTER_PLAN":
        missing.append("workflow.plan_version")
    return tuple(refs), missing


class PlanningContextReader:
    def __init__(self, session):
        self.repo = PlanningRepository(session)

    def query(self, request, selector):
        current = self.repo.brief(request.workflow_id)
        observed = {
            "current_brief": str(current.id) if current else None,
            "status": current.status if current else None,
        }
        records = []
        if selector.source_type == SourceType.CREATIVE_BRIEF:
            for ref in request.explicit_refs:
                if (
                    ref.source_type == SourceType.CREATIVE_BRIEF
                    and ref.logical_id == request.workflow_id
                ):
                    record = self.repo.brief(request.workflow_id, ref.version)
                    if record and record.status == BriefStatus.READY and current.id == record.id:
                        records.append(record)
        else:
            ids = {
                ref.logical_id
                for ref in request.explicit_refs
                if ref.source_type == SourceType.PLAN_REVIEW_REPORT
            }
            records = self.repo.reports_by_ids(request.workflow_id, ids)
        items = []
        for record in records:
            brief = selector.source_type == SourceType.CREATIVE_BRIEF
            items.append(
                ContextItem(
                    context_item_id=uuid5(NAMESPACE_URL, f"{selector.selector_id}:{record.id}"),
                    selector_id=selector.selector_id,
                    source_type=selector.source_type,
                    source_id=record.id,
                    logical_id=record.workflow_id if brief else record.id,
                    source_version=record.version if brief else 1,
                    project_id=record.project_id,
                    chapter_id=record.chapter_id,
                    chapter_sequence=request.chapter_sequence,
                    status=Status.ACTIVE,
                    authority_level=Authority.A7_AI_INFERENCE,
                    locked=False,
                    priority=selector.priority,
                    scope=selector.scope,
                    payload_json=canonical(record.body),
                    selected_reason="Exact workflow-bound planning evidence",
                    source_created_at=record.created_at,
                    source_updated_at=record.created_at,
                    provenance=("planning_evidence", str(record.agent_run_id)),
                )
            )
        return tuple(items), observed
