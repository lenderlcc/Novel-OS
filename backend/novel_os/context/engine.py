"""Context selection is pure policy. Retrieval and transactions belong to application services."""

from dataclasses import replace

from novel_os.context.policies import (
    AuthorityResolver,
    ContextFilter,
    ContextRanker,
    TokenBudgetService,
    exclude,
)
from novel_os.context.serialization import ContextSerializer
from novel_os.domain.context import (
    ContextBuildResult,
    ContextPackage,
    ContextStatus,
    ExclusionReason,
    Priority,
)
from novel_os.prompts.contracts import canonical


class ContextEngine:
    def __init__(self, estimator=None):
        self.budget = TokenBudgetService(estimator)

    def build(self, request, profile, batch, *, prompt_overhead=0, output_reservation=0):
        if prompt_overhead < 0 or output_reservation < 0:
            raise ValueError("Invalid context budget reservation")
        if request.task_type not in profile.allowed_task_types:
            return ContextBuildResult(
                status=ContextStatus.FAILED, error_code="CONTEXT_PROFILE_MISMATCH"
            )
        selectors = {s.selector_id: s for s in profile.selectors}
        candidates, excluded = [], list(batch.excluded)
        for item in batch.items:
            selector = selectors[item.selector_id]
            reason = ContextFilter().reason(item, selector, request, profile)
            if reason:
                excluded.append(exclude(item, reason))
            else:
                # Candidate readers provide facts; the profile owns selection priority.
                candidates.append(
                    replace(
                        item,
                        priority=Priority.P0
                        if item.ref in request.required_refs
                        else selector.priority,
                        scope=selector.scope,
                    )
                )
        missing = list(request.missing_bindings) + [
            selector.selector_id
            for selector in profile.selectors
            if selector.required
            and not any(item.selector_id == selector.selector_id for item in candidates)
        ]
        resolved, authority_excluded, conflicts = AuthorityResolver().resolve(candidates)
        missing.extend(
            f"{ref.source_type}:{ref.logical_id}:v{ref.version}"
            for ref in request.required_refs
            if not any(item.ref == ref for item in resolved)
        )
        limited = []
        for selector in profile.selectors:
            group = sorted(
                (i for i in resolved if i.selector_id == selector.selector_id),
                key=ContextRanker.key,
            )
            mandatory = [i for i in group if i.priority == Priority.P0]
            optional = [i for i in group if i.priority != Priority.P0]
            remaining = max(0, selector.max_items - len(mandatory))
            excluded.extend(exclude(i, ExclusionReason.LOW_PRIORITY) for i in optional[remaining:])
            group = mandatory + optional[:remaining]
            limited.extend(group)
        resolved = tuple(limited)
        selected, budget_excluded, estimated, overflow = self.budget.select(
            request, profile, resolved, prompt_overhead, output_reservation
        )
        missing.extend(
            f"{ref.source_type}:{ref.logical_id}:v{ref.version}"
            for ref in request.required_refs
            if not any(item.ref == ref for item in selected)
        )
        missing = sorted(set(missing))
        error = (
            "CONTEXT_RETRIEVAL_LIMIT"
            if batch.overflow
            else "CONTEXT_AUTHORITY_CONFLICT"
            if conflicts
            else "CONTEXT_MISSING"
            if missing
            else "CONTEXT_BUDGET_EXCEEDED"
            if overflow
            else None
        )
        excluded.extend((*authority_excluded, *budget_excluded))
        package = ContextPackage(
            project_id=request.project_id,
            task_id=request.task_id,
            workflow_id=request.workflow_id,
            request=replace(request, request_id=None),
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_hash=profile.profile_hash,
            profile_json=canonical(profile.model_dump(mode="json")),
            build_status=ContextStatus.BLOCKED if error else ContextStatus.READY,
            items=selected,
            excluded_items=tuple(
                sorted(
                    excluded,
                    key=lambda i: (i.selector_id, str(i.source_id), i.source_version, i.reason),
                )
            ),
            missing_required_items=tuple(sorted(missing)),
            authority_conflicts=conflicts,
            source_snapshots=tuple(sorted(batch.snapshots, key=lambda s: s.selector_id)),
            token_budget=profile.token_budget,
            prompt_overhead=prompt_overhead,
            output_reservation=output_reservation,
            estimated_tokens=estimated,
            future_knowledge_policy=profile.future_knowledge_policy,
            package_hash="",
            error_code=error,
        )
        package = ContextSerializer.seal(package)
        return ContextBuildResult(
            status=package.build_status,
            package=package,
            error_code=error,
            missing_required_context=package.missing_required_items,
            authority_conflicts=conflicts,
        )


class FreshnessValidator:
    def validate(self, package, *, source_snapshots, workflow_state_version, profile_hash):
        if package.build_status != ContextStatus.READY:
            return ContextBuildResult(
                status=package.build_status,
                package=package,
                error_code=package.error_code,
                missing_required_context=package.missing_required_items,
                authority_conflicts=package.authority_conflicts,
            )
        stale = (
            ContextSerializer.hash(package) != package.package_hash
            or profile_hash != package.profile_hash
            or workflow_state_version != package.request.workflow_state_version
            or tuple(sorted(source_snapshots, key=lambda s: s.selector_id))
            != package.source_snapshots
        )
        return ContextBuildResult(
            status=ContextStatus.STALE if stale else ContextStatus.READY,
            package=package,
            error_code="CONTEXT_STALE" if stale else None,
        )
