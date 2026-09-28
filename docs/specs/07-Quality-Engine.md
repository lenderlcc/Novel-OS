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

## NOVEL-009A — Narrative acceptance refinement

New narrative tasks use `chapter-narrative-review.v2` and `review-chapter-narrative.v2`. The latter is the repository's narrative half of chapter-quality review; only this task Prompt receives new semantic instructions. Compliance, Writer, Planning and Requirement prompts are unchanged. Taxonomy codes, severity/aggregation rules and Context selection are unchanged.

V2 adds `audience_evidence[]` describing an exact approved Profile field/value, observed reading effect and reason for mismatch. Non-PASS Audience requires an AUDIENCE_STYLE_MISMATCH issue with matching evidence/source references. Narrative warnings alone do not imply Audience warnings. This validates claims and bindings only; there are no deterministic dialogue detectors or added issue-count quotas.

Persisted v2 aggregate reports use `reviewer_version=A05-quality.v2` and retain that evidence in their existing immutable JSON body. No table/migration changes. V1 models and their output schema hash stay intact; API history accepts both versions. Queued v1 narrative tasks explicitly select their old schema and task Prompt, while newly scheduled narrative tasks select v2. The shared runtime's optional schema selector defaults to existing behavior for every other task.

The UI keeps its existing Chinese diagnosis view and adds expandable approved-preference evidence. Historical reports lacking that field render normally. Acceptance fixtures and before/after comparisons live in local `evals/quality/009a`; human themes never enter runtime Context or Prompt. Real re-evaluation still requires a new explicit trigger and does not create or rewrite a Draft.

## NOVEL-010 Review / Revision 边界

QualityReview 永久绑定原 ChapterVersion；A06 不修改旧 Review，也不能把建议转换为高 Authority。用户明确请求后 A06 创建新 Draft，新版通过本规范当前 A05 Compliance + Narrative 流程重新审阅一次。A06 的 addressed 声明不是质量证明；新问题、丢失 strength 或方向偏离仍按正常 A05 标准报告。Review v2 FAIL 仍停止等待用户，不自动无限修订。详见 [Revision Engine](08-Revision-Engine.md)。
