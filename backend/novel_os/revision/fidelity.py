"""Structural proof around an independent semantic verdict, never similarity scoring."""

from novel_os.domain.revision import FidelityCode
from novel_os.prompts.contracts import digest
from novel_os.quality.policy import check_evidence, check_sources, paragraphs
from novel_os.revision.contracts import read_plan
from novel_os.revision.fidelity_schemas import REQUIRED_CHECKS


def preservation_ids(plan):
    return {
        *REQUIRED_CHECKS,
        *(s.strength_id for s in plan.strength_preservation),
        *(e.element_id for e in plan.preserve_scene_elements),
        *(e.element_id for e in plan.preserve_relationship_elements),
        *(e.element_id for e in plan.preserve_effective_details),
    }


class RevisionFidelityValidator:
    @staticmethod
    def plan(output, request, source):
        plan = read_plan(output.model_dump())
        strengths = {k for k in request.contract["preserve_items"] if k.startswith("strength:")}
        if {s.strength_id for s in plan.strength_preservation} != strengths:
            raise ValueError("Every source Review strength needs direct or functional preservation")
        for element in (
            plan.preserve_scene_elements
            + plan.preserve_relationship_elements
            + plan.preserve_effective_details
        ):
            check_evidence(element.evidence, source)
        for zone in plan.revision_zones:
            if zone.paragraph_end is not None and zone.paragraph_end > len(paragraphs(source)):
                raise ValueError("Revision zone extends beyond the source Draft")
        authorization = plan.structural_authorization
        if authorization:
            issue = request.contract["target_issues"][str(authorization.issue_id)]
            if authorization.review_root_cause != issue["description"]:
                raise ValueError("Structural authorization must quote the actual Review root cause")
        return plan

    @staticmethod
    def candidate(output, request, plan, package):
        draft = next((i for i in package.items if i.selector_id == "target-version"), None)
        if draft is None or draft.source_id != request.source_chapter_version_id:
            raise ValueError("The exact Source Draft must be present as EDIT_BASE")
        RevisionFidelityValidator.plan(
            read_plan(plan.body),
            request,
            draft.structured_payload["content"],
        )
        if output.content and not output.declared_changes:
            raise ValueError("Candidate changes must be declared")

    @staticmethod
    def semantic(output, request, plan, candidate, package):
        items = {i.selector_id: i for i in package.items}
        source = items.get("target-version")
        selected = items.get("revision-candidate")
        selected_plan = items.get("revision-plan")
        if (
            source is None
            or source.source_id != request.source_chapter_version_id
            or selected is None
            or selected.source_id != candidate.id
            or selected_plan is None
            or selected_plan.source_id != plan.id
            or output.source_chapter_version_id != request.source_chapter_version_id
            or output.source_review_id != request.source_review_id
            or output.revision_plan_id != plan.id
            or output.candidate_id != candidate.id
            or output.candidate_content_hash != digest(candidate.body["content"])
            or selected.structured_payload["content"] != candidate.body["content"]
        ):
            raise ValueError("Fidelity must bind the exact source, plan and candidate text")
        parsed = RevisionFidelityValidator.plan(
            read_plan(plan.body),
            request,
            source.structured_payload["content"],
        )
        if {c.check_id for c in output.checks} != preservation_ids(parsed):
            raise ValueError("Fidelity must cover all protected story elements and strengths")
        for check in output.checks:
            check_evidence(check.source_evidence, source.structured_payload["content"])
            check_evidence(check.revised_evidence, candidate.body["content"])
        for violation in output.violations:
            if (
                any(i.startswith("strength:") for i in violation.check_ids)
                and violation.code != FidelityCode.REVISION_STRENGTH_REGRESSION
            ):
                raise ValueError("Strength regression needs its dedicated fidelity code")
        check_sources(output.source_refs, package.items)
