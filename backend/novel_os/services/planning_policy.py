"""Checkable source and authority rules for the planning vertical slice."""

from novel_os.agents.planning_schemas import REQUIREMENT_FIELDS
from novel_os.domain.context import SourceType
from novel_os.domain.errors import DomainError

LOCKED_DEPENDENCY_TYPES = {
    SourceType.REQUIREMENT,
    SourceType.DECISION,
    SourceType.CHAPTER_PLAN,
    SourceType.CHAPTER_VERSION,
}


def ref_key(ref):
    return ref.source_type, ref.logical_id, ref.version


def denied(message):
    raise DomainError("AUTHORITY_DENIED", message)


def validate_brief_sources(output, selected, source_keys):
    raw_refs = {key for key in selected if key[0] == SourceType.TASK_INPUT}
    if not raw_refs <= source_keys:
        denied("CreativeBrief must reference raw user input")
    for constraint in output.constraints + output.persistent_preference_candidates:
        key = ref_key(constraint.source_ref)
        item = selected.get(key)
        if (
            item is None
            or key not in source_keys
            or key[0] not in {SourceType.TASK_INPUT, SourceType.REQUIREMENT, SourceType.DECISION}
        ):
            denied("Constraint requires an explicit user source")
        field = {
            SourceType.TASK_INPUT: "objective",
            SourceType.REQUIREMENT: "content",
            SourceType.DECISION: "decision",
        }[key[0]]
        if constraint.quote not in item.structured_payload[field]:
            denied("Constraint quotation is not present in the cited source")
        if any(constraint.text == assumption.text for assumption in output.assumptions):
            denied("An assumption cannot masquerade as a user constraint")

    # Structured user requirements have a server-owned category. Preserve the full
    # content (including qualifiers/negation), not merely a convenient substring.
    represented = set()
    for category, field in REQUIREMENT_FIELDS.items():
        for constraint in getattr(output, field):
            key = ref_key(constraint.source_ref)
            if key[0] != SourceType.REQUIREMENT:
                continue
            payload = selected[key].structured_payload
            if payload["requirement_type"] != category or payload["content"] != constraint.text:
                denied("CreativeBrief changed an existing Requirement's category or wording")
            represented.add(key)
    required = {key for key in selected if key[0] == SourceType.REQUIREMENT}
    if not required <= represented:
        denied("CreativeBrief omitted an effective approved or locked Requirement")


def locked_refs(items, *, subject=None):
    """The reviewed plan is a subject, never its own pre-existing dependency."""
    return {
        ref_key(item.ref)
        for item in items
        if item.locked
        and item.source_type in LOCKED_DEPENDENCY_TYPES
        and ref_key(item.ref) != subject
    }
