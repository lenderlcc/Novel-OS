"""Deterministic identity, evidence and version comparisons; no narrative inference."""

import re
import unicodedata
from dataclasses import replace
from difflib import SequenceMatcher
from uuid import uuid5

from novel_os.domain.context import SourceType
from novel_os.domain.enums import Authority
from novel_os.domain.memory import (
    BLOCKING_CONFLICTS,
    DERIVED_TYPES,
    STATE_TYPES,
    MemoryConflict,
    MemorySubject,
    MemoryType,
)
from novel_os.quality.policy import paragraphs


def normalized(value):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


def comparable_value(value):
    """Keep semantic punctuation: 1.5 metres is not 15 metres."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def ref_key(ref):
    return ref.source_type, str(ref.logical_id), ref.version


def validate_evidence(output, request, content, boundaries):
    source = (SourceType.CHAPTER_VERSION, str(request.chapter_id), request.draft_version)
    indexed = paragraphs(content)
    for candidate in output.candidates:
        if [ref_key(r) for r in candidate.source_refs] != [source]:
            raise ValueError("Memory evidence must cite only the exact accepted ChapterVersion")
        for evidence in candidate.evidence:
            if (
                not 1 <= evidence.paragraph_index <= len(indexed)
                or (evidence.short_excerpt not in indexed[evidence.paragraph_index - 1])
                or not evidence.short_excerpt.strip()
            ):
                raise ValueError("Memory evidence must quote the exact numbered paragraph")
        checks = [ref_key(c.source_ref) for c in candidate.authority_checks]
        if set(checks) != set(boundaries) or len(checks) != len(set(checks)):
            raise ValueError(
                "Every supplied canon, approved or locked authority source needs one boundary check"
            )


def resolve_subject(candidate, subjects, project_id, content):
    ref = candidate.subject_ref
    if ref is None:
        return None, None
    compatible = [s for s in subjects if s.kind == ref.kind]
    names = {normalized(ref.name), *(normalized(n) for n in ref.aliases)}
    matches = [s for s in compatible if names & {s.normalized_name, *s.aliases}]
    if any(names & {s.normalized_name, *s.aliases} for s in subjects if s.kind != ref.kind):
        return None, "名称对应的实体类型无法确认。"
    if ref.resolution == "AMBIGUOUS" or len(matches) > 1:
        return None, "人物或对象的称呼无法唯一确认。"
    if ref.logical_id is not None:
        subject = next((s for s in compatible if s.id == ref.logical_id), None)
        if subject is None or subject not in matches:
            return None, "实体标识与已确认名称不一致。"
        return subject.id, None
    if matches:
        return matches[0].id, None
    # Unknown aliases are never guessed. A possible name variation needs human correction.
    if any(
        SequenceMatcher(None, normalized(ref.name), s.normalized_name).ratio() >= 0.75
        for s in compatible
    ):
        return None, "称呼可能对应已有实体，请返回正文确认，避免重复记忆。"
    if ref.name not in content or any(alias not in content for alias in ref.aliases):
        return None, "新实体及别名必须在已确认正文中明确出现。"
    return uuid5(project_id, f"memory-subject:{ref.kind}:{normalized(ref.name)}"), None


def classify(candidate, existing):
    if existing is None:
        return MemoryConflict.NONE
    if comparable_value(existing.value) == comparable_value(candidate.value) and (
        existing.epistemic_status == candidate.epistemic_status
        and existing.body.get("known_fact_id")
        == (str(candidate.known_fact_id) if candidate.known_fact_id else None)
        and (
            candidate.candidate_type != MemoryType.OPEN_THREAD
            or comparable_value(existing.statement) == comparable_value(candidate.statement)
        )
    ):
        return MemoryConflict.DUPLICATE
    if candidate.candidate_type in {MemoryType.CANON_FACT, MemoryType.OPEN_THREAD}:
        object_state = (
            candidate.candidate_type == MemoryType.CANON_FACT
            and candidate.subject_ref.kind == "OBJECT"
            and existing.body.get("state_after") == existing.value
        )
        if (
            (object_state or candidate.candidate_type == MemoryType.OPEN_THREAD)
            and candidate.state_before == existing.value
            and candidate.state_after == candidate.value
        ):
            return MemoryConflict.STATE_TRANSITION
        return MemoryConflict.CONTRADICTION
    if (
        candidate.candidate_type in STATE_TYPES
        and candidate.state_before is not None
        and (comparable_value(candidate.state_before) == comparable_value(existing.value))
    ):
        # A change from belief to knowledge also creates a new historical version.
        return MemoryConflict.STATE_TRANSITION
    return MemoryConflict.CONTRADICTION


def resolve_batch_subjects(output, subjects, project_id, content):
    resolved = list(subjects)
    identities = {}
    # Explicit aliases are considered before shorthand-only references in the same proposal.
    for candidate in sorted(
        output.candidates, key=lambda c: -len(c.subject_ref.aliases) if c.subject_ref else 0
    ):
        # An uncertain/blocked claim cannot establish another candidate's identity.
        if (
            candidate.uncertainty
            or candidate.confidence < 0.6
            or any(check.outcome != "COMPATIBLE" for check in candidate.authority_checks)
        ):
            identities[candidate.id] = None, "候选尚未确认，不能作为人物或对象的身份依据。"
            continue
        subject_id, error = resolve_subject(candidate, resolved, project_id, content)
        identities[candidate.id] = subject_id, error
        ref = candidate.subject_ref
        if subject_id is None or error or ref is None:
            continue
        existing = next((s for s in resolved if s.id == subject_id), None)
        if existing is None:
            resolved.append(
                MemorySubject(
                    id=subject_id,
                    project_id=project_id,
                    name=ref.name,
                    normalized_name=normalized(ref.name),
                    kind=ref.kind,
                    aliases=sorted({normalized(a) for a in ref.aliases}),
                    batch_id=project_id,
                )
            )
        elif existing not in subjects:
            aliases = (
                set(existing.aliases)
                | {normalized(ref.name), *(normalized(a) for a in ref.aliases)}
            ) - {existing.normalized_name}
            resolved[resolved.index(existing)] = replace(existing, aliases=sorted(aliases))
    return resolved, identities


def normalize_candidates(output, *, project_id, chapter_id, content, subjects, lookup):
    resolved, identities = resolve_batch_subjects(output, subjects, project_id, content)
    results = []
    groups = {}
    for candidate in output.candidates:
        subject_id, ambiguity = identities[candidate.id]
        subject = next((s for s in resolved if s.id == subject_id), None)
        slot = normalized(candidate.slot)
        if not slot or not normalized(candidate.value):
            raise ValueError("Memory attribute and value cannot consist only of punctuation")
        # Summary identity belongs to its chapter; it must not overwrite another chapter's summary.
        if candidate.candidate_type == MemoryType.DERIVED_CHAPTER_SUMMARY:
            slot = str(chapter_id)
        previous = lookup(subject_id, candidate.candidate_type, slot) if subject_id else None
        conflict = classify(candidate, previous)
        reason = {
            MemoryConflict.NONE: "新记忆，等待用户确认。",
            MemoryConflict.DUPLICATE: "已有相同记忆，将跳过重复项。",
            MemoryConflict.STATE_TRANSITION: "正文明确描述状态变化，将保留旧版本。",
            MemoryConflict.CONTRADICTION: "发现与已有设定不一致的内容。",
        }[conflict]
        if candidate.existing_entry_id and (
            previous is None or previous.id != candidate.existing_entry_id
        ):
            ambiguity = "引用的记忆与实体、类型或属性不一致。"
        if candidate.uncertainty or candidate.confidence < 0.6:
            ambiguity = candidate.uncertainty or "提取确定性不足。"
        if ambiguity:
            conflict, reason = MemoryConflict.AMBIGUOUS, ambiguity
        checks = candidate.authority_checks
        if any(c.outcome == "UNCERTAIN" for c in checks):
            conflict, reason = MemoryConflict.AMBIGUOUS, "无法确认与已批准设定是否一致。"
        if any(c.outcome == "CONFLICT" and c.source_ref.source_type == "EXTENSION" for c in checks):
            conflict, reason = (
                MemoryConflict.CONTRADICTION,
                "这项内容与已有 Canon 不一致，暂时不能写入。",
            )
        if any(c.outcome == "CONFLICT" and c.source_ref.source_type != "EXTENSION" for c in checks):
            conflict, reason = (
                MemoryConflict.AUTHORITY_CONFLICT,
                "这项内容与已批准或锁定设定冲突，暂时不能写入。",
            )
        key = (subject_id, candidate.candidate_type, slot)
        result = {
            **candidate.model_dump(mode="json"),
            "subject_id": str(subject_id) if subject_id else None,
            "normalized_subject": {
                "name": subject.name,
                "kind": subject.kind,
                "normalized_name": subject.normalized_name,
                "aliases": subject.aliases,
            }
            if subject
            else None,
            "slot": slot,
            "conflict_status": conflict.value,
            "conflict_reason": reason,
            "authority_level": (
                Authority.A6_DERIVED_MEMORY
                if candidate.candidate_type in DERIVED_TYPES
                else Authority.A3_CANON
            ).value,
            "previous_entry_id": str(previous.id) if previous else None,
            "previous_statement": previous.statement if previous else None,
        }
        results.append(result)
        groups.setdefault(key, []).append(result)
    for group in groups.values():
        eligible = [row for row in group if row["conflict_status"] not in BLOCKING_CONFLICTS]
        claims = {
            (
                comparable_value(row["value"]),
                row["epistemic_status"],
                row["known_fact_id"],
                comparable_value(row["statement"])
                if row["candidate_type"] == MemoryType.OPEN_THREAD
                else None,
                row["state_after"] == row["value"]
                if row["candidate_type"] == MemoryType.CANON_FACT
                and row["subject_ref"]["kind"] == "OBJECT"
                else None,
            )
            for row in eligible
        }
        if len(claims) > 1:
            for row in eligible:
                row["conflict_status"] = MemoryConflict.CONTRADICTION.value
                row["conflict_reason"] = "同一提案包含互相冲突的状态。"
        else:
            for row in eligible[1:]:
                # Keep transitions executable when the user selects only a duplicate.
                # The commit's selected_keys already prevents writing two successors.
                if row["conflict_status"] == MemoryConflict.NONE:
                    row["conflict_status"] = MemoryConflict.DUPLICATE.value
                    row["conflict_reason"] = "同一提案中已有相同候选项。"
    return results
