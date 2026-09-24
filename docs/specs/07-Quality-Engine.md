# Chapter Quality Review Engine — NOVEL-009

The implementation follows the latest NOVEL-009 user supplement (2026-09-24). The older ticket's three model passes are superseded: A05 runs **two passes**, COMPLIANCE and NARRATIVE + AUDIENCE, followed by deterministic aggregation. No numeric score or automatic A06/rewrite.

## Boundaries

API → Service → Repository → PostgreSQL. Pure `domain/quality.py` and `quality/{schemas,policy}.py` do not import FastAPI/ORM. Repositories flush only. Service completion holds the established Project → Workflow → Task locks and commits pass, audit, task outcome and transition together.

Deterministic checks cover schema, authority, exact sources, paragraph/quote identity, version freshness and verdict invariants. Semantic compliance, POV, immersion, dialogue and reader fit belong to A05. Dialogue containing a first-person pronoun is never a deterministic POV violation. AI output remains inference, never user approval or a hard requirement.

## Two-pass contract

- `REVIEW_CHAPTER_COMPLIANCE`: exact Draft/CreativeBrief MUST and FORBIDDEN/approved Plan/locked and approved sources/approved A5 POV. Never promotes SHOULD or preferences into MUST.
- `REVIEW_CHAPTER_NARRATIVE`: narrative quality, creative suggestions and audience fit. No independent hard gates.
- P0 or a P1 whose explicit impact requires revision → FAIL. Other issues → PASS_WITH_WARNINGS. No findings → PASS. Severity/category/issue/verdict contradictions fail validation. Number of issues is not a scoring rule.
- Every issue has a short exact Draft excerpt, 1-based paragraph index and reason, impact, revision direction, confidence and selected source references. Strengths are also evidenced. No rewritten prose.
- MUST/FORBIDDEN proof may cite either an exact Brief constraint or the `content` field of a selected formal Requirement with matching requirement type and APPROVED/A2 or LOCKED/A1 status/authority. Approval of a SHOULD/PREFERENCE never makes it a hard constraint. `quality-evidence.v2` explains both source paths; v1 stays unchanged.
- Final report has separate compliance/narrative/audience verdicts and both pass Context/Prompt lineage IDs. Stable code taxonomy is in `Quality-Taxonomy-v1.md`.

## Context and authority

CP-006 v3 selects the exact target Draft, workflow approved Plan, CreativeBrief, effective approved/locked requirements and decisions, exact locked dependencies and exact approved ProjectWritingProfile. Unapproved current Profile/Plan/previous chapter Drafts are excluded. Up to three earlier approved chapters are optional P1 context and may be omitted under budget. No vector search or new Memory domain.

A5 remains A5. Profile absence is snapshotted, so first approval also invalidates queued work. Missing canon/character-knowledge evidence means no justified conflict claim. Repeated safe creative choice needs evidence from at least two earlier chapters and remains P2/P3. Human expectations and test tags never enter the model prompt.

## Lifecycle and persistence

`chapter-planning.v3` preserves prior stages, adds C08 deterministic check → C09 review. Both passes use the same C09 state version and immutable binding. C09 PASS/warnings → C11; FAIL → C10; both wait for the human without scheduling A06. Explicit user `REQUEST_REVIEW` can start another review, retaining the first report. Provider errors use existing technical retry policy; a quality FAIL is a successful task result, not a retry.

Tables: `quality_review_bindings`, `quality_review_passes`, `chapter_quality_reviews`. Database triggers prohibit update/delete and validate Project/Chapter/Draft/Plan/Brief/task/run/context/lineage relationships. One result per binding; each chapter's review version is allocated under the Project lock.

Input freshness is checked before the model, before persistence and between passes. A changed source blocks the pending/in-flight result as CONTEXT_STALE; it cannot attach to another Draft. GET history rechecks all frozen source fingerprints and returns STALE without changing the historical report.

Chapter bookkeeping version/timestamp changes caused by an unapproved Plan are excluded from review fingerprints. Actual Chapter input/authority changes, exact Draft and approved Plan versions remain checked.

Explicit REQUEST_REVIEW from C10/C11 or a suspended review checks `expected_state_version` and `expected_draft_version` against current records under the Project lock, then starts a fresh C09 binding and two new passes. RESUME of a suspended review accepts the same Draft token. Omitting it only resumes an unchanged bound Draft; otherwise HTTP 409 requires a refresh. Old passes/reports remain immutable, no Draft/approval is changed. Changed Brief or approved Plan still routes through intake/replanning. A legacy C08 block is recoverable only when the workflow has an existing quality binding; v1/v2 Writing handoffs cannot adopt a new Draft using this token.

Existing v1/v2 workflow definitions and instances remain immutable. Legacy chapters render without a review; historical evaluation uses a separate read-only export plus opt-in CLI in `evals/quality`, not silent workflow migration.

## Product and evaluation

Workspace steps: 需求 → 方案 → 正文 → 审阅. Normal view uses 通过/有改进空间/建议修改, short Chinese issues, expandable excerpts/impact/directions, strengths. Internal codes, severity, confidence, paragraph indices, raw JSON, source bindings, Context and Prompt are in Debug. Human evaluation import/comparison is local and independent; mismatch in exact artifact identity is rejected.

No Revision Engine, quality ensemble, automatic prompt tuning, Writer changes, numeric score or NOVEL-010 behavior is introduced. Real evaluations require explicit `--real`, at most two calls per input, with no automatic retry.
