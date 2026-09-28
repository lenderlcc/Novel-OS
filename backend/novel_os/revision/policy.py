"""Validate declared scope and evidence; prose semantics belong to independent A05."""

from uuid import uuid5

from novel_os.domain.context import SourceType
from novel_os.domain.enums import Authority
from novel_os.quality.policy import check_sources
from novel_os.quality.schemas import read_review


def contract_for(review, package):
    body = read_review(review.body)
    issues = body.hard_gate_issues + body.quality_issues
    priority = {p.issue_code: n for n, p in enumerate(body.revision_priorities)}
    ordered = sorted(
        enumerate(issues),
        key=lambda pair: (pair[1].severity, priority.get(pair[1].code, 100), pair[0]),
    )
    targets = {str(uuid5(review.id, f"issue:{n}")): i.model_dump(mode="json") for n, i in ordered}
    keep = {f"strength:{n}": s.model_dump(mode="json") for n, s in enumerate(body.strengths)}
    boundaries = {}
    for item in package.items:
        payload = item.structured_payload
        if item.source_type == SourceType.CREATIVE_BRIEF:
            value = {
                key: payload[key]
                for key in ("must", "forbidden", "preserve", "creative_freedom")
                if key in payload
            }
        elif (
            item.authority_level <= Authority.A5_USER_PREFERENCE
            and item.selector_id != "target-version"
            and item.source_type
            in {
                SourceType.CHAPTER_PLAN,
                SourceType.CHAPTER_VERSION,
                SourceType.DECISION,
                SourceType.REQUIREMENT,
                SourceType.LOCK,
                SourceType.PROJECT_WRITING_PROFILE,
            }
        ):
            value = payload
        else:
            continue
        key = f"{item.source_type}:{item.source_id}:v{item.source_version}"
        boundaries[key] = dict(
            source_type=item.source_type,
            source_id=str(item.source_id),
            source_version=item.source_version,
            authority=item.authority_level,
            value=value,
        )
        if item.source_type in {SourceType.CHAPTER_PLAN, SourceType.CREATIVE_BRIEF}:
            keep[key] = value
    return dict(
        target_issues=targets,
        preserve_items=keep,
        do_not_change=boundaries,
        review_authority="DIAGNOSIS_ONLY",
        default_scope="TARGETED",
        fidelity_version=1,
        edit_base={
            "role": "EDIT_BASE",
            "source_id": str(review.chapter_version_id),
            "selector_id": "target-version",
            "full_text_required": True,
        },
        preservation_default="Everything outside revision scope is implicitly preserved",
    )


def validate_plan(output, request, package):
    if (output.chapter_id, output.source_chapter_version_id, output.source_review_id) != (
        request.chapter_id,
        request.source_chapter_version_id,
        request.source_review_id,
    ):
        raise ValueError("Revision Plan source identity mismatch")
    contract = request.contract
    if set(map(str, output.target_issue_ids)) != set(contract["target_issues"]):
        raise ValueError("Revision target issues must belong to the exact source Review")
    if set(output.preserve_items) != set(contract["preserve_items"]) or len(
        output.preserve_items
    ) != len(contract["preserve_items"]):
        raise ValueError("Preservation must retain all exact source commitments")
    if set(output.do_not_change) != set(contract["do_not_change"]) or len(
        output.do_not_change
    ) != len(contract["do_not_change"]):
        raise ValueError("Authority boundaries cannot be removed or rewritten")
    for target in output.revision_targets:
        source = contract["target_issues"][str(target.issue_id)]
        if (
            target.issue_code != source["code"]
            or target.priority != source["severity"]
            or [e.model_dump(mode="json") for e in target.evidence_refs] != source["evidence"]
        ):
            raise ValueError("Revision target must retain exact issue identity and evidence")
    check_sources(output.source_refs, package.items)


def validate_result(output, request, plan, package):
    if (output.source_chapter_version_id, output.source_review_id, output.revision_plan_id) != (
        request.source_chapter_version_id,
        request.source_review_id,
        plan.id,
    ):
        raise ValueError("Revision execution source identity mismatch")
    addressed, unresolved = (
        list(map(str, output.addressed_issue_ids)),
        list(map(str, output.unresolved_issue_ids)),
    )
    safe = {str(t["issue_id"]) for t in plan.body["revision_targets"]}
    if (
        len(set(addressed + unresolved)) != len(addressed + unresolved)
        or set(addressed + unresolved) != set(request.contract["target_issues"])
        or not set(addressed) <= safe
    ):
        raise ValueError(
            "Every original issue must remain accounted for; blocked issues cannot be claimed fixed"
        )
    if set(output.preserved_items) != set(request.contract["preserve_items"]) or len(
        output.preserved_items
    ) != len(request.contract["preserve_items"]):
        raise ValueError("Revision must preserve the source commitments")
    if any(str(b.issue_id) not in unresolved for b in output.blocked_reasons):
        raise ValueError("Blocked issues must remain unresolved")
    if output.content is None and not output.blocked_reasons:
        raise ValueError("Missing prose needs a safe-block explanation")
    check_sources(output.source_refs, package.items)
