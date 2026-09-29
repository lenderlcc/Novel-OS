"""Structured routing and exact source checks; no keyword interpretation."""

from uuid import uuid5

from novel_os.domain.feedback import FeedbackAction, RevisionSource
from novel_os.quality.policy import check_sources
from novel_os.revision.policy import contract_for, review_targets


def validate_interpretation(output, feedback, package, review):
    if (output.feedback_id, output.source_chapter_version_id) != (
        feedback.id,
        feedback.source_chapter_version_id,
    ):
        raise ValueError("Interpretation must bind the exact feedback and source Draft")
    feedback_item = next(i for i in package.items if i.selector_id == "human-feedback")
    clarifications = feedback_item.structured_payload.get("clarifications", [])
    user_messages = [feedback.raw_feedback, *(c["raw_feedback"] for c in clarifications)]
    if any(
        not any(quote in message for message in user_messages) for quote in output.feedback_evidence
    ):
        raise ValueError("Feedback evidence must quote the user's actual words")
    available = review_targets(review) if review else {}
    if not set(map(str, output.supporting_review_issue_ids)) <= set(available):
        raise ValueError("Diagnostic support must refer to the selected Review")
    if output.supporting_review_issue_ids and not any(
        i.selector_id == "feedback-review" for i in package.items
    ):
        raise ValueError("Excluded Review cannot be used as diagnostic support")
    check_sources(output.source_refs, package.items)


def directed_contract(feedback, interpretation, package):
    output = interpretation
    if output.action != FeedbackAction.REVISION:
        raise ValueError("Only safe Revision intent can reach A06")
    # Human direction owns KEEP. Review strengths remain advice, not mandatory
    # commitments; approved authority and source Fidelity still apply unchanged.
    contract = contract_for(None, package, source_id=feedback.source_chapter_version_id)
    # Review is diagnostic support, never an additional list of edits to perform.
    contract["target_issues"] = {
        str(uuid5(feedback.id, f"change:{n}")): {
            "code": "HUMAN_FEEDBACK",
            "severity": "P1",
            "description": change.description,
            "evidence": [],
            "target_regions": change.target_regions,
        }
        for n, change in enumerate(output.requested_changes)
    }
    contract["preserve_items"].update(
        {f"feedback-preserve:{n}": value for n, value in enumerate(output.preserve_requests)}
    )
    contract["do_not_change"].update(
        {f"feedback-boundary:{n}": value for n, value in enumerate(output.do_not_change)}
    )
    contract.update(
        revision_source=RevisionSource.BOTH
        if output.supporting_review_issue_ids
        else RevisionSource.HUMAN_FEEDBACK,
        source_feedback_id=str(feedback.id),
        human_scope=output.scope,
        human_target_regions=output.target_regions,
        raw_feedback=feedback.raw_feedback,
        interpretation=output.model_dump(mode="json"),
        human_scope_priority="EXPLICIT_USER_SCOPE_OVER_REVIEW; NO_AUTHORITY_OVERRIDE",
    )
    feedback_item = next(i for i in package.items if i.selector_id == "human-feedback")
    if clarifications := feedback_item.structured_payload.get("clarifications"):
        contract["clarifications"] = clarifications
    return contract


def check_directed_plan(plan, contract):
    if not contract.get("source_feedback_id"):
        return
    if contract["human_scope"] != "CHAPTER_WIDE" and (
        plan.scope == "FULL_PASS"
        or plan.allowed_structural_change == "CHAPTER_WIDE"
        or plan.change_budget == "BROAD"
    ):
        raise ValueError("Revision cannot expand explicit human scope")
    for zone in plan.revision_zones:
        for target_id in zone.issue_ids:
            if (
                zone.semantic_range
                not in contract["target_issues"][str(target_id)]["target_regions"]
            ):
                raise ValueError(
                    "Revision zones must retain the user's interpreted semantic regions"
                )


def human_fidelity_checks(contract):
    if not contract.get("source_feedback_id"):
        return set()
    return {
        "HUMAN_SCOPE",
        *(k for k in contract["preserve_items"] if k.startswith("feedback-preserve:")),
        *(k for k in contract["do_not_change"] if k.startswith("feedback-boundary:")),
    }
