"""Structural and source checks only. Literary judgments belong to the review model."""

import re
from dataclasses import fields

from novel_os.domain.context import KnowledgeScope, SourceType
from novel_os.domain.enums import Authority, RequirementType, Status
from novel_os.domain.quality import QualityCode, verdict_for
from novel_os.domain.writing_profile import WritingPreferences
from novel_os.quality.schemas import ChapterReviewResult, ChapterReviewResultV2, NarrativeReviewV2


def paragraphs(content):
    return [part.strip() for part in re.split(r"\n\s*\n", content.strip()) if part.strip()]


def indexed_paragraphs(content):
    return [{"paragraph_index": n, "text": text} for n, text in enumerate(paragraphs(content), 1)]


def check_evidence(evidence, content):
    indexed = paragraphs(content)
    for entry in evidence:
        if (
            entry.paragraph_index > len(indexed)
            or entry.excerpt not in indexed[entry.paragraph_index - 1]
        ):
            raise ValueError("Evidence must quote the identified Draft paragraph exactly")
        if entry.excerpt.strip() == content.strip():
            raise ValueError("Evidence must not duplicate the whole chapter")


def source_key(ref):
    return (ref.source_type, ref.source_id, ref.source_version)


def check_sources(refs, items):
    selected = {source_key(i): i for i in items}
    resolved = []
    for ref in refs:
        item = selected.get(source_key(ref))
        if item is None:
            raise ValueError("Review cites a source outside the selected ContextPackage")
        resolved.append((ref, item))
    return resolved


def proves_hard_constraint(ref, item, code):
    field, requirement_type = (
        ("must", RequirementType.MUST)
        if code == QualityCode.MISSING_MUST
        else ("forbidden", RequirementType.FORBIDDEN)
    )
    if item.source_type == SourceType.CREATIVE_BRIEF:
        return ref.field in {f"{field}.{c['id']}" for c in item.structured_payload[field]}
    return (
        item.source_type == SourceType.REQUIREMENT
        and (item.status, item.authority_level)
        in {
            (Status.APPROVED, Authority.A2_USER_APPROVED),
            (Status.LOCKED, Authority.A1_USER_LOCKED),
        }
        and item.structured_payload.get("requirement_type") == requirement_type
        and ref.field == "content"
    )


def validate_pass(output, package):
    draft = next((i for i in package.items if i.selector_id == "target-version"), None)
    if draft is None or (output.chapter_id, output.chapter_version_id) != (
        package.request.chapter_id,
        draft.source_id,
    ):
        raise ValueError("Review targets a different Draft")
    content = draft.structured_payload["content"]
    check_sources(output.source_refs, package.items)
    issues = getattr(output, "hard_gate_issues", getattr(output, "quality_issues", []))
    for strength in output.strengths:
        check_evidence(strength.evidence, content)
    for issue in issues:
        check_evidence(issue.evidence, content)
        cited = check_sources(issue.source_refs, package.items)
        if not {source_key(r) for r in issue.source_refs} <= {
            source_key(r) for r in output.source_refs
        }:
            raise ValueError("Issue references must appear in the pass source list")
        code = issue.code
        # A SHOULD/preference/reviewer suggestion can never satisfy this proof.
        if code in {QualityCode.MISSING_MUST, QualityCode.FORBIDDEN_VIOLATION} and not any(
            proves_hard_constraint(r, i, code) for r, i in cited
        ):
            raise ValueError(
                "Hard constraint requires an exact Brief constraint or approved Requirement"
            )
        if code == QualityCode.MAJOR_DIRECTION_VIOLATION and not any(
            i.selector_id == "approved-plan" for _, i in cited
        ):
            raise ValueError("Major direction requires the approved Plan")
        if code == QualityCode.LOCKED_CONFLICT and not any(
            i.locked and i.authority_level == Authority.A1_USER_LOCKED for _, i in cited
        ):
            raise ValueError("Locked conflict requires an actual locked source")
        if code == QualityCode.CANON_CONFLICT and not any(
            i.source_type
            in {SourceType.REQUIREMENT, SourceType.DECISION, SourceType.CHAPTER_VERSION}
            and i.authority_level
            in {Authority.A1_USER_LOCKED, Authority.A2_USER_APPROVED, Authority.A3_CANON}
            and i.source_id != draft.source_id
            for _, i in cited
        ):
            raise ValueError("Canon conflict cannot be inferred from absence of canon evidence")
        if code == QualityCode.CHARACTER_KNOWLEDGE_LEAK and not any(
            i.knowledge_scope == KnowledgeScope.CHARACTER_KNOWLEDGE and i.character_id is not None
            for _, i in cited
        ):
            raise ValueError("Global facts do not establish character knowledge")
        if code in {QualityCode.NARRATIVE_POV_MISMATCH, QualityCode.AUDIENCE_STYLE_MISMATCH}:
            profile_refs = [
                (r, i)
                for r, i in cited
                if i.source_type == SourceType.PROJECT_WRITING_PROFILE
                and i.authority_level == Authority.A5_USER_PREFERENCE
            ]
            if not profile_refs:
                raise ValueError("Profile mismatch requires an exact approved A5 profile")
            for ref, item in profile_refs:
                value = item.structured_payload
                for key in (ref.field or "").split("."):
                    value = value.get(key) if isinstance(value, dict) else None
                if value in (None, "", [], "UNSPECIFIED"):
                    raise ValueError("Profile claim requires a populated approved preference field")
                if code == QualityCode.NARRATIVE_POV_MISMATCH and not ref.field.startswith(
                    "narrative_perspective"
                ):
                    raise ValueError("POV claim requires an approved narrative perspective field")
        if code == QualityCode.SAFE_GENERIC_CREATIVE_CHOICE:
            previous = {
                i.chapter_id
                for _, i in cited
                if i.source_type in {SourceType.CHAPTER_VERSION, SourceType.CHAPTER_PLAN}
                and i.chapter_sequence is not None
                and i.chapter_sequence < package.request.chapter_sequence
            }
            if len(previous) < 2:
                raise ValueError(
                    "Repeated safe choices require at least two earlier chapter sources"
                )
    if isinstance(output, NarrativeReviewV2):
        preference_fields = {f.name for f in fields(WritingPreferences)}
        for evidence in output.audience_evidence:
            _, profile = check_sources([evidence.profile_ref], package.items)[0]
            if (
                profile.status != Status.APPROVED
                or profile.authority_level != Authority.A5_USER_PREFERENCE
                or evidence.profile_field not in preference_fields
            ):
                raise ValueError("Audience evidence requires a selected approved A5 preference")
            actual = profile.structured_payload.get(evidence.profile_field)
            if actual in (None, "", [], "UNSPECIFIED") or actual != evidence.expected:
                raise ValueError("Audience expected value must equal the exact approved field")


def aggregate(compliance, narrative, compliance_pass, narrative_pass, created_at):
    issues = compliance.hard_gate_issues + narrative.quality_issues
    refs = {r.model_dump_json(): r for r in compliance.source_refs + narrative.source_refs}
    current = isinstance(narrative, NarrativeReviewV2)
    model = ChapterReviewResultV2 if current else ChapterReviewResult
    return model(
        chapter_id=compliance.chapter_id,
        chapter_version_id=compliance.chapter_version_id,
        overall_verdict=verdict_for(issues),
        compliance_verdict=compliance.compliance_verdict,
        narrative_verdict=narrative.narrative_verdict,
        audience_fit_verdict=narrative.audience_fit_verdict,
        hard_gate_issues=compliance.hard_gate_issues,
        quality_issues=narrative.quality_issues,
        strengths=list(
            {s.model_dump_json(): s for s in compliance.strengths + narrative.strengths}.values()
        )[:10],
        revision_priorities=(compliance.revision_priorities + narrative.revision_priorities)[:10],
        source_refs=list(refs.values()),
        confidence=min(compliance.confidence, narrative.confidence),
        reviewer_version="A05-quality.v2" if current else "A05-quality.v1",
        **({"audience_evidence": narrative.audience_evidence} if current else {}),
        prompt_lineage_id=narrative_pass.prompt_lineage_id,
        context_package_id=narrative_pass.context_package_id,
        compliance_prompt_lineage_id=compliance_pass.prompt_lineage_id,
        compliance_context_package_id=compliance_pass.context_package_id,
        created_at=created_at,
    )
