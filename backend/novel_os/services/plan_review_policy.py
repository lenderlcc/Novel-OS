"""Evidence-bound constraints, consistent review decisions and bounded repair input."""

from novel_os.agents.planning_schemas import (
    REQUIREMENT_FIELDS,
    Coverage,
    HardGateIssue,
    PlanReviewOutput,
)
from novel_os.domain.planning import ReviewVerdict
from novel_os.services.planning_policy import denied

HARD_FIELDS = ("must", "forbidden", "preserve", "change_requests")
CATEGORY_BY_FIELD = {field: category for category, field in REQUIREMENT_FIELDS.items()}


def authoritative_constraints(brief):
    """A projection of sourced Brief categories, never new User/System authority."""
    return [
        {"category": CATEGORY_BY_FIELD[field], **item.model_dump(mode="json")}
        for field in HARD_FIELDS
        for item in getattr(brief, field)
    ]


def literal_entry(value, constraint, category):
    # Only an exact quote or its own display label is equivalent. Substrings,
    # paraphrases and Review prose are deliberately not authority evidence.
    return value in (constraint.text, f"[{category} {constraint.id}] {constraint.text}")


def canonical_plan_constraints(plan, brief):
    """Normalize display labels; reject attempts to persist invented hard constraints."""
    result = plan.model_dump()
    for destination, fields in (
        ("constraints", ("must", "forbidden", "change_requests")),
        ("preserved_elements", ("preserve",)),
    ):
        candidates = [
            (CATEGORY_BY_FIELD[field], item) for field in fields for item in getattr(brief, field)
        ]
        normalized = []
        for value in getattr(plan, destination):
            matched = next(
                (item for category, item in candidates if literal_entry(value, item, category)),
                None,
            )
            if matched is None:
                denied("Plan constraints must come from the Brief, not Review advice or inventions")
            if matched.text not in normalized:
                normalized.append(matched.text)
        result[destination] = normalized
    return type(plan).model_validate(result)


def effective_verdict(review, brief, plan):
    """Derive hard evidence without leaving coverage and missing ids contradictory."""
    issues = list(review.hard_gate_issues)
    coverage = {entry.constraint_id: entry for entry in review.requirement_coverage}
    proposed = {entry.constraint_id: entry for entry in plan.requirement_coverage}
    missing = set(review.missing_requirements)

    def add(code, message, constraint_id=None):
        issue = HardGateIssue(code=code, description=message, constraint_id=constraint_id)
        if issue not in issues:
            issues.append(issue)

    for field in HARD_FIELDS:
        entries = plan.preserved_elements if field == "preserve" else plan.constraints
        for constraint in getattr(brief, field):
            key = constraint.id
            if any(issue.constraint_id == key for issue in issues):
                continue  # Already has validated, uncovered hard evidence.
            stored = any(
                literal_entry(value, constraint, CATEGORY_BY_FIELD[field]) for value in entries
            )
            covered = all(
                entry is not None
                and entry.covered
                and (entry.scope == "PLAN_GLOBAL" or bool(entry.scene_ids))
                for entry in (coverage.get(key), proposed.get(key))
            )
            if not stored or not covered or key in missing:
                message = "Mandatory constraint has no stored evidence or valid coverage: " + key
                missing.add(key)
                if not any(i.code == "MISSING_MUST" and i.constraint_id == key for i in issues):
                    add("MISSING_MUST", message, key)
                coverage[key] = Coverage(
                    constraint_id=key,
                    covered=False,
                    scope="PLAN_GLOBAL",
                    scene_ids=[],
                    explanation=message,
                )
    for field, code in (
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
    if issues:
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
    return PlanReviewOutput.model_validate(
        {
            **review.model_dump(),
            "verdict": verdict,
            "hard_gate_issues": issues,
            "requirement_coverage": list(coverage.values()),
            "missing_requirements": sorted(missing),
        }
    )


def review_feedback(body):
    """Only the immediately preceding review is supplied; advice never becomes constraints."""
    return {
        "verdict": body["verdict"],
        "review_revision_targets": body["hard_gate_issues"] if body["verdict"] == "FAIL" else [],
        "recommendations": list(
            dict.fromkeys(
                body["recommendations"] + body["quality_issues"] + body["over_specification_issues"]
            )
        ),
    }
