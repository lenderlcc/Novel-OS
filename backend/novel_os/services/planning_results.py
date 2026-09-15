"""Application-owned business validation, immutable artifact creation and gate policy."""

from dataclasses import asdict

from novel_os.agents.planning_schemas import (
    ChapterPlanOutput,
    CreativeBriefOutput,
    HardGateIssue,
    PlanReviewOutput,
)
from novel_os.domain.agents import ResultStatus, TaskStatus
from novel_os.domain.context import SourceType
from novel_os.domain.core import AuditRecord, CommandContext, ObjectRef, VersionToken
from novel_os.domain.enums import ActorType, AuditAction, ObjectType
from novel_os.domain.errors import DomainError
from novel_os.domain.planning import (
    BriefStatus,
    CreativeBrief,
    PlanGeneration,
    PlanReviewReport,
    ReviewVerdict,
)
from novel_os.domain.workflow import ChapterState
from novel_os.repositories.planning import PlanningRepository
from novel_os.repositories.prompt_lineages import PromptLineageRepository
from novel_os.services.core_base import CoreService
from novel_os.services.planning_policy import (
    LOCKED_DEPENDENCY_TYPES,
    denied,
    locked_refs,
    ref_key,
    validate_brief_sources,
)
from novel_os.services.versioning import PlanningService


def validate_sources(output, package):
    selected = {ref_key(item.ref): item for item in package.items}
    if any(ref_key(ref) not in selected for ref in output.source_refs):
        denied("Result cites a source outside its exact context snapshot")
    return selected


def effective_verdict(review, brief, plan):
    """A nominal PASS cannot override structured hard evidence or absent mandatory coverage."""
    issues = list(review.hard_gate_issues)

    def add(code, message):
        if not any(item.code == code and item.description == message for item in issues):
            issues.append(HardGateIssue(code=code, description=message))

    mandatory = {item.id: item for item in brief.must + brief.preserve + brief.change_requests}
    coverage = {item.constraint_id: item for item in review.requirement_coverage}
    proposed = {item.constraint_id: item for item in plan.requirement_coverage}

    def covered(key, entries):
        entry = entries.get(key)
        if entry is None or not entry.covered:
            return False
        if entry.scope == "SCENE":
            return bool(entry.scene_ids)
        # Global narration/preservation constraints need plan-level evidence,
        # not an invented scene just to satisfy a coverage counter.
        return mandatory[key].text in plan.constraints + plan.preserved_elements

    for key in sorted(mandatory):
        if any(not covered(key, entries) for entries in (coverage, proposed)):
            add("MISSING_MUST", "Mandatory coverage missing: " + key)
    for field, code in (
        ("missing_requirements", "MISSING_MUST"),
        ("forbidden_violations", "FORBIDDEN_VIOLATION"),
        ("locked_conflicts", "LOCKED_CONFLICT"),
        ("direction_conflicts", "DIRECTION_CONFLICT"),
    ):
        for message in getattr(review, field):
            add(code, message)
    for risk in review.logic_risks:
        if risk.impact == "HIGH":
            add("MAJOR_LOGIC_BREAK", risk.description)
    if any(proposal.required_for_plan for proposal in plan.proposed_major_changes):
        add("DIRECTION_CONFLICT", "Executable plan requires an unapproved major change")
    if issues or review.verdict == ReviewVerdict.FAIL:
        verdict = ReviewVerdict.FAIL
    elif (
        review.quality_issues
        or review.over_specification_issues
        or review.logic_risks
        or review.recommendations
        or review.confidence < 0.6
        or review.verdict == ReviewVerdict.PASS_WITH_WARNINGS
    ):
        verdict = ReviewVerdict.PASS_WITH_WARNINGS
    else:
        verdict = ReviewVerdict.PASS
    return review.model_copy(update={"verdict": verdict, "hard_gate_issues": issues})


class PlanningResultService:
    def __init__(self, session):
        self.session = session
        self.repo = PlanningRepository(session)
        self.core = CoreService(session)

    def current_brief(self, workflow):
        from novel_os.services.planning_freshness import PlanningFreshness

        return PlanningFreshness(self.session).current_brief(workflow)

    def check_transition(self, workflow, target):
        if target == ChapterState.C01_REQUIREMENT_INTAKE:
            return
        brief = self.current_brief(workflow)
        if target in {ChapterState.C06_PLAN_APPROVAL, ChapterState.C07_WRITING}:
            plan = PlanningService(self.session).get(
                workflow.project_id, workflow.chapter_id, workflow.plan_version
            )
            report = self.repo.review(workflow.id, plan.id)
            if (
                report is None
                or report.brief_id != brief.id
                or report.verdict == ReviewVerdict.FAIL
            ):
                raise DomainError("INVALID_STATE", "An exact passing plan review is required")
            if target == ChapterState.C06_PLAN_APPROVAL:
                from novel_os.services.planning_freshness import PlanningFreshness

                PlanningFreshness(self.session).check_review(report)

    def validate(self, task, run, result, package, workflow):
        if workflow.simulation:
            denied("Formal business tasks require a planning workflow")
        self.core.require_transaction(task.project_id)
        self.core.check_record_lock(self.core.repo.get_chapter(task.project_id, task.target_ref))
        if task.task_type == "PLAN_CHAPTER":
            self.core.check_lock(
                task.project_id, ObjectRef(ObjectType.CHAPTER_PLAN, task.target_ref)
            )
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        if (
            lineage is None
            or lineage.task_id != task.task_id
            or lineage.output_schema_id + ".v" + str(lineage.output_schema_version)
            != task.expected_output_schema
        ):
            denied("Business artifacts require the exact prompt lineage")
        output = result.result
        selected = validate_sources(output, package)
        source_keys = {ref_key(ref) for ref in output.source_refs}
        if task.task_type == "PARSE_CHAPTER_REQUIREMENT":
            validate_brief_sources(output, selected, source_keys)
            needs_human = any(a.requires_decision for a in output.unresolved_ambiguities)
            if (
                result.status != (ResultStatus.NEEDS_HUMAN if needs_human else ResultStatus.SUCCESS)
                or bool(result.escalation and result.escalation.required) != needs_human
            ):
                denied("Clarification requires high impact, low confidence and unsafe inference")
            return
        brief = self.current_brief(workflow)
        if (SourceType.CREATIVE_BRIEF, workflow.id, brief.version) not in source_keys:
            denied("Result must cite the exact current CreativeBrief")
        if result.status != ResultStatus.SUCCESS or (
            result.escalation and result.escalation.required
        ):
            denied("A planning artifact requires a successful bounded result")
        parsed_brief = CreativeBriefOutput.model_validate(brief.body)
        known_ids = {item.id for item in parsed_brief.constraints}
        if any(item.constraint_id not in known_ids for item in output.requirement_coverage):
            denied("Coverage cites an unknown Brief constraint")
        chapter = self.core.repo.get_chapter(workflow.project_id, workflow.chapter_id)
        VersionToken(workflow.plan_version or 0).check(chapter.current_plan_version or 0)
        if task.task_type == "PLAN_CHAPTER":
            freedom = output.creative_freedom
            baseline = parsed_brief.creative_freedom
            levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            if levels[freedom.level] > levels[baseline.level] or set(
                freedom.allowed_operations
            ) - set(baseline.allowed_operations):
                denied("Planning expanded its granted creative scope")
            for ref in output.locked_dependencies:
                item = selected.get(ref_key(ref))
                if item is None or not item.locked or ref_key(ref) not in source_keys:
                    denied("Locked dependencies must cite actual locks in this context")
                if item.source_type not in LOCKED_DEPENDENCY_TYPES:
                    denied("Unsupported locked dependency")
            if locked_refs(package.items) != {ref_key(ref) for ref in output.locked_dependencies}:
                denied("Plan omitted a locked context dependency")
        else:
            if (
                SourceType.CHAPTER_PLAN,
                workflow.chapter_id,
                workflow.plan_version,
            ) not in source_keys:
                denied("Review must cite the exact workflow Plan")
            plan = PlanningService(self.session).get(
                workflow.project_id, workflow.chapter_id, workflow.plan_version
            )
            generation = self.repo.generation(workflow.id, plan.id)
            if generation is None or generation.brief_id != brief.id:
                denied("Plan and review must share the exact Brief")
            scene_ids = {scene["id"] for scene in generation.body["scenes"]}
            if any(set(item.scene_ids) - scene_ids for item in output.requirement_coverage):
                denied("Review coverage references an unknown scene")

    def persist(self, task, run, result, package, workflow):
        self.core.require_transaction(task.project_id)
        chapter = self.core.repo.get_chapter(task.project_id, task.target_ref)
        self.core.check_record_lock(chapter)
        lineage = PromptLineageRepository(self.session).for_run(run.run_id)
        evidence = dict(
            project_id=task.project_id,
            chapter_id=task.target_ref,
            workflow_id=workflow.id,
            agent_run_id=run.run_id,
            prompt_lineage_id=lineage.lineage_id,
            context_package_id=package.context_package_id,
            source_versions=[
                asdict(item.ref)
                | {"logical_id": str(item.logical_id), "source_id": str(item.source_id)}
                for item in package.items
            ],
        )
        output = result.result
        event, payload, terminal = "AGENT_SUCCEEDED", {}, TaskStatus.SUCCEEDED
        if task.task_type == "PARSE_CHAPTER_REQUIREMENT":
            previous = self.repo.brief(workflow.id)
            if previous:
                self.repo.supersede(previous)
            input_event = self.repo.input_event(workflow.id)
            needs_human = result.status == ResultStatus.NEEDS_HUMAN
            artifact = self.repo.add(
                CreativeBrief(
                    **evidence,
                    version=previous.version + 1 if previous else 1,
                    raw_requirement=input_event.payload["raw_requirement"],
                    input_event_id=input_event.event_id,
                    status=BriefStatus.NEEDS_HUMAN if needs_human else BriefStatus.READY,
                    body=output.model_dump(mode="json"),
                    supersedes_id=previous.id if previous else None,
                )
            )
            if needs_human:
                event, terminal = "BLOCK", TaskStatus.BLOCKED
                payload = {"reason": "User decision required; inspect CreativeBrief ambiguities"}
        elif task.task_type == "PLAN_CHAPTER":
            brief = self.current_brief(workflow)
            body = output.model_dump(mode="json")
            plan_payload = dict(
                objective=output.objective,
                required_outcome=output.required_outcome,
                scene_plans=body["scenes"],
                character_progression={"items": body["character_progression"]},
                plot_progression={"items": body["plot_progression"]},
                information_release=body["information_release"],
                ending_state={"description": output.ending_state},
                constraints=body["constraints"],
                locked_dependencies=[
                    {"object_type": ref.source_type.value, "object_id": str(ref.logical_id)}
                    for ref in output.locked_dependencies
                ],
                risks=body["risks"],
            )
            plan = PlanningService(self.session).create_version_in_transaction(
                task.project_id,
                task.target_ref,
                plan_payload,
                workflow.plan_version or 0,
                CommandContext(str(run.run_id), task.agent_id.value, ActorType.AGENT),
                "Agent proposed a new ChapterPlan version",
            )
            artifact = self.repo.add(
                PlanGeneration(
                    **evidence,
                    plan_id=plan.id,
                    brief_id=brief.id,
                    planning_iteration=workflow.planning_iteration_count,
                    body=body,
                )
            )
            event, payload = "PLAN_READY", {"plan_id": str(plan.id), "plan_version": plan.version}
        else:
            brief = self.current_brief(workflow)
            plan = PlanningService(self.session).get(
                workflow.project_id, workflow.chapter_id, workflow.plan_version
            )
            generation = self.repo.generation(workflow.id, plan.id)
            reviewed = effective_verdict(
                output,
                CreativeBriefOutput.model_validate(brief.body),
                ChapterPlanOutput.model_validate(generation.body),
            )
            issues = list(reviewed.hard_gate_issues)
            parsed_brief = CreativeBriefOutput.model_validate(brief.body)
            for constraint in (
                parsed_brief.must + parsed_brief.forbidden + parsed_brief.change_requests
            ):
                if constraint.text not in generation.body["constraints"]:
                    issues.append(
                        HardGateIssue(
                            code="MISSING_MUST",
                            description="Plan omitted a mandatory constraint: " + constraint.id,
                        )
                    )
            for constraint in parsed_brief.preserve:
                if constraint.text not in generation.body["preserved_elements"]:
                    issues.append(
                        HardGateIssue(
                            code="MISSING_MUST",
                            description="Plan omitted a preservation constraint: " + constraint.id,
                        )
                    )
            declared = {
                ref_key(ref)
                for ref in ChapterPlanOutput.model_validate(generation.body).locked_dependencies
            }
            subject = (SourceType.CHAPTER_PLAN, workflow.chapter_id, workflow.plan_version)
            for source_type, logical_id, version in sorted(
                locked_refs(package.items, subject=subject) - declared
            ):
                issues.append(
                    HardGateIssue(
                        code="LOCKED_CONFLICT",
                        description=f"Plan omitted locked {source_type} {logical_id} v{version}",
                    )
                )
            if issues:
                reviewed = reviewed.model_copy(
                    update={"verdict": ReviewVerdict.FAIL, "hard_gate_issues": issues}
                )
            artifact = self.repo.add(
                PlanReviewReport(
                    **evidence,
                    plan_id=plan.id,
                    brief_id=brief.id,
                    verdict=reviewed.verdict,
                    body=PlanReviewOutput.model_validate(reviewed.model_dump()).model_dump(
                        mode="json"
                    ),
                )
            )
            event = (
                "PLAN_REVIEW_FAILED"
                if reviewed.verdict == ReviewVerdict.FAIL
                else "PLAN_REVIEW_PASSED"
            )
        self.core.repo.add(
            AuditRecord(
                project_id=task.project_id,
                target_type=ObjectType.CHAPTER,
                target_id=task.target_ref,
                target_version=chapter.version,
                action=AuditAction.VERSION_CREATE,
                actor_type=ActorType.AGENT,
                actor_id=task.agent_id.value,
                request_id=str(run.run_id),
                reason="Persist validated " + type(artifact).__name__,
                after={
                    "artifact_id": str(artifact.id),
                    "agent_run_id": str(run.run_id),
                    "prompt_lineage_id": str(lineage.lineage_id),
                    "context_package_id": str(package.context_package_id),
                },
            )
        )
        return event, payload, terminal
