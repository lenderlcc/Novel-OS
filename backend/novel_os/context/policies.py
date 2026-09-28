"""Deterministic filtering, authority resolution, ranking and whole-item budgeting."""

from dataclasses import replace

from novel_os.context.serialization import ContextSerializer
from novel_os.domain.context import (
    AuthorityConflict,
    ContextScope,
    ExcludedItem,
    ExclusionReason,
    FutureKnowledgePolicy,
    KnowledgeScope,
    Priority,
    SourceType,
    VersionPolicy,
)
from novel_os.domain.enums import Status
from novel_os.prompts.contracts import canonical
from novel_os.providers.tokens import Utf8TokenEstimator

INACTIVE = {Status.STALE, Status.SUPERSEDED, Status.DEPRECATED, Status.CANCELLED, Status.ARCHIVED}


def exclude(item, reason):
    return ExcludedItem(
        source_type=item.source_type,
        source_id=item.source_id,
        source_version=item.source_version,
        selector_id=item.selector_id,
        reason=reason,
    )


class ContextFilter:
    def reason(self, item, selector, request, profile):
        if item.project_id != request.project_id:
            return ExclusionReason.OUT_OF_SCOPE
        if selector.scope == ContextScope.TARGET_CHAPTER and item.chapter_id not in {
            None,
            request.chapter_id,
        }:
            return ExclusionReason.OUT_OF_SCOPE
        if selector.scope in {
            ContextScope.PREVIOUS_CHAPTER,
            ContextScope.RECENT_APPROVED_CHAPTERS,
        } and (item.chapter_sequence is None or item.chapter_sequence >= request.chapter_sequence):
            return ExclusionReason.OUT_OF_SCOPE
        if selector.scope == ContextScope.EXPLICIT and item.ref not in request.explicit_refs:
            return ExclusionReason.OUT_OF_SCOPE
        if item.status in INACTIVE or item.status not in selector.allowed_statuses:
            return ExclusionReason.STATUS_FILTERED
        if item.authority_level > selector.authority_floor:
            return ExclusionReason.AUTHORITY_SUPERSEDED
        if item.source_type not in {SourceType.CHAPTER, SourceType.TASK_INPUT} and item.status in {
            Status.DRAFT,
            Status.PROPOSED,
        }:
            exact = item.ref in request.explicit_refs or (
                item.source_type == SourceType.CHAPTER_VERSION
                and item.chapter_id == request.chapter_id
                and item.source_version == request.target_version
            )
            if (
                selector.version_policy not in {VersionPolicy.EXACT, VersionPolicy.TARGET_VERSION}
                or not exact
            ):
                return ExclusionReason.VERSION_FILTERED
        if selector.version_policy == VersionPolicy.LOCKED and not item.locked:
            return ExclusionReason.VERSION_FILTERED
        if request.knowledge_scope == KnowledgeScope.CHARACTER_KNOWLEDGE:
            if (
                item.knowledge_scope != KnowledgeScope.CHARACTER_KNOWLEDGE
                or item.character_id != request.character_id
                or request.character_id is None
            ):
                return ExclusionReason.CHARACTER_KNOWLEDGE
        elif item.knowledge_scope == KnowledgeScope.CHARACTER_KNOWLEDGE:
            return ExclusionReason.CHARACTER_KNOWLEDGE
        future = item.future_knowledge or (
            item.chapter_sequence is not None and item.chapter_sequence > request.chapter_sequence
        )
        if future:
            policy = profile.future_knowledge_policy
            if policy == FutureKnowledgePolicy.NONE:
                return ExclusionReason.FUTURE_KNOWLEDGE
            if (
                policy == FutureKnowledgePolicy.REQUIRED_ONLY
                and item.ref not in request.required_future_refs
            ):
                return ExclusionReason.FUTURE_KNOWLEDGE
            if policy == FutureKnowledgePolicy.LIMITED and (
                item.ref not in request.explicit_refs
                or item.chapter_sequence is None
                or item.chapter_sequence > request.chapter_sequence + profile.future_horizon
            ):
                return ExclusionReason.FUTURE_KNOWLEDGE
        return None


class ContextRanker:
    @staticmethod
    def key(item):
        return (
            item.priority,
            item.authority_level,
            -item.relevance_score,
            item.scope != ContextScope.TARGET_CHAPTER,
            -item.source_updated_at.timestamp(),
            item.source_type,
            str(item.logical_id),
            item.source_version,
            str(item.source_id),
            item.selector_id,
        )

    def rank(self, items):
        return tuple(sorted(items, key=self.key))


class AuthorityResolver:
    def resolve(self, items):
        groups = {}
        for item in ContextRanker().rank(items):
            groups.setdefault((item.source_type, item.logical_id), []).append(item)
        selected, excluded, conflicts = [], [], []
        for (source_type, logical_id), group in sorted(
            groups.items(), key=lambda pair: str(pair[0])
        ):
            authority = min(item.authority_level for item in group)
            strongest = [item for item in group if item.authority_level == authority]
            if len({item.payload_json for item in strongest}) > 1:
                conflicts.append(
                    AuthorityConflict(
                        source_type=source_type,
                        logical_id=logical_id,
                        source_ids=tuple(sorted({item.source_id for item in strongest}, key=str)),
                    )
                )
                continue
            winner = min(strongest, key=ContextRanker().key)
            selected.append(replace(winner, priority=min(item.priority for item in group)))
            excluded.extend(
                exclude(
                    item,
                    ExclusionReason.DUPLICATE
                    if item.authority_level == authority
                    else ExclusionReason.AUTHORITY_SUPERSEDED,
                )
                for item in group
                if item is not winner
            )
        return tuple(selected), tuple(excluded), tuple(conflicts)


class TokenBudgetService:
    def __init__(self, estimator=None):
        self.estimator = estimator or Utf8TokenEstimator()

    def cost(self, request, profile, items):
        payload = ContextSerializer.payload(request, profile, items)
        return self.estimator.estimate(canonical({"trust": "UNTRUSTED_DATA_ONLY", "data": payload}))

    def select(
        self, request, profile, items, prompt_overhead, output_reservation, *, token_budget=None
    ):
        budget = (
            profile.token_budget
            if token_budget is None
            else min(profile.token_budget, token_budget)
        )
        available = budget - prompt_overhead - output_reservation
        ordered = ContextRanker().rank(items)
        selected = [item for item in ordered if item.priority == Priority.P0]
        cost = self.cost(request, profile, selected)
        if cost > available:
            return tuple(selected), (), cost, True
        excluded = []
        for item in ordered:
            if item.priority == Priority.P0:
                continue
            next_cost = self.cost(request, profile, [*selected, item])
            if next_cost <= available:
                selected.append(item)
                cost = next_cost
            else:
                excluded.append(exclude(item, ExclusionReason.TOKEN_BUDGET))
        return tuple(selected), tuple(excluded), cost, False
