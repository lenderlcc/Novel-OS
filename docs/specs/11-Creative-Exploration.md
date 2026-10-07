# NOVEL-013 — Creative Exploration for Planning

## Product boundary

A03 remains Planning Owner. Creative Exploration is one internal task before the formal Plan, not an Agent, workflow, approval gate, selectable brainstorm UI, or Memory domain. Normal Workspace shows one final Plan. Full candidates are diagnostic evidence in Debug/Eval only.

Phase 1 (NOVEL-001–012) Engineering Complete; E2E-001 Engineering Acceptance = PASS_WITH_BLOCKERS_RESOLVED. E2E-001R Real Provider / Human Multi-Chapter Acceptance = PENDING. Phase 2 NOVEL-013 Engineering = COMPLETE; Real Provider / Human Acceptance = PENDING. Its creative behavior is frozen while NOVEL-014 proceeds. Starting either ticket does not complete the paused real five-chapter acceptance or approve its pending Plan.

## Runtime and trigger

`POST /api/v1/workflows/chapter-exploration` uses the existing create DTO and starts immutable `chapter-planning` definition v4. Its states, transitions, gates and downstream semantics match v3. Existing v1/v2/v3 endpoints and instances retain their contracts.

C04 schedules A03 `EXPLORE_CHAPTER_CONCEPTS`, then A03 `PLAN_CHAPTER`, then existing A05 Plan Review and human Plan Approval. Exploration completion does not dispatch PLAN_READY: it atomically persists diagnostics and schedules formal Planning within the same state/version. Only the formal Plan emits PLAN_READY.

- HIGH: explore 3–4 mechanism-level concepts by default.
- MEDIUM: explore 2–3 only when granted operations include LOCAL_CONFLICT; otherwise skip.
- LOW: skip exploration.
- Already fixed events/direction: FOCUSED may return one concept with a grounded explanation; do not force artificial alternatives.

One successful exploration is reused by ordinary A05 repair iterations. The existing maximum two automatic formal Plans stays unchanged; candidates are not iterations. Explicit human REJECT/MODIFY/REQUEST_ALTERNATIVE invalidates the old selection and starts one new exploration. There is no creativity score threshold or creative-quality retry loop.

## Output contract and selection

Pydantic `CreativeExplorationOutput` / `ExplorationAgentResult` are Structured Output sources of truth. Candidate fields cover summary, event, causal conflict, character pressure, progression, reader interest, continuity/requirement/freedom/audience fit, feasibility, disclosed local additions, qualitative repetition/major-change risks and reasons, authority fit, strengths and risks. IDs are local strings; no server versions, approval fields or authority grants are model output.

Compare mechanisms, not renamed locations, objects, gestures or surface detail. Character reactions must fit supplied state, motivation and known evidence. Diversity is a model/human semantic judgment; the runtime does not pretend to prove it with keyword matching, templates, forbidden-action catalogs, embeddings or numeric novelty scores.

A selected candidate must exist, have major_change_risk LOW/MEDIUM and authority_fit WITHIN_BOUNDS. Every unselected candidate needs one rejection. HIGH major risk or REQUIRES_MAJOR_CHANGE is rejected as REQUIRES_MAJOR_CHANGE; otherwise a Lock/Canon violation is VIOLATES_AUTHORITY. Empty proposed_changes and memory_proposals are mandatory. If all candidates are unsafe, persist BLOCKED with no selected candidate and block the existing workflow; never silently force a fallback or create a new approval gate.

Major direction, identity, relationship status, world rules and Canon remain PROPOSAL_ONLY. A7 diagnostics cannot change any approved/locked content. Service validates exact Brief, runtime lineage, selected sources, citations of locked/Canon evidence and freedom-dependent candidate count; SQL protects execution bindings and the selected authority declaration. Semantic compliance remains subject to A05 and human review, not an invented deterministic NLP checker.

## Context

CP-004E v1 uses REQUIRED_ONLY, zero implicit future horizon, exact current READY Brief, effective approved/locked requirements and decisions, approved Writing Profile, relevant existing committed continuity, character/knowledge/open-thread inputs, and up to three recent compact approved Plan/final summary hints. No current Draft Plan or chapter prose is historical input; approved_plan_version determines prior accepted Plans. The compact projection contains objective, outcome, progressions, ending state and risks, not scene/prose dumps.

CP-004 v7 hands formal Planning the exact selected candidate as a separate EXTENSION UUID at A7, alongside authoritative_constraints, review_revision_targets and recommendations. Rejected candidates, comparative selection_reason and the full exploration body never enter this projection. Comparative reasons remain in Debug only. Selected inference does not become constraints[], Canon, or a future seed.

Recent final summaries read existing committed batches and DERIVED_CHAPTER_SUMMARY entries (A6/P1). Their compact payload matches the canonical reader representation so duplicate selection deduplicates instead of causing false Authority conflicts. Character/global knowledge policies, owners, epistemic status and A07/Memory retrieval algorithms remain unchanged. Writer, Revision and Memory profiles do not register the selected-concept reader. Historical CP-004 v6 remains bound to v1–3 workflows.

## Persistence and transactions

0018_creative_exploration adds immutable creative_explorations and nullable creative_exploration_id/selected_candidate_id to PlanGeneration. The final ChapterPlan output/schema is unchanged. The artifact binds exact project/chapter/workflow/Brief, AgentRun, PromptLineage, ContextPackage, source versions, result and creation time. Its authority is derived A7; there is no promotion/approval/write endpoint.

Project locking, lease fencing, unique AgentRun, append-only triggers and transaction-owned completion prevent duplicate evidence and mixed lineage. Repositories flush; AgentResultHandler/WorkflowRuntime own commit/rollback. Plan creation, generation lineage, audit and transition are one transaction. Migration compatibility changes extend existing Writing/Quality version allowlists to v4 only; their behavior remains unchanged. Downgrade restores prior version guards and leaves pre-013 data intact.

## Freshness and recovery

Replay the saved Context profile and all source snapshots, including empty sets; do not substitute latest for approved. The Brief and exploration inputs, approved Profile, active Locks, Canon and selected artifact pin are checked before model use and again before persistence. A stale result cannot create a Plan.

A source change with a still-fresh Brief requires explicit RESUME to take a fresh exploration snapshot; unchanged BLOCKED diagnostics cannot trigger an automatic retry. A stale Brief uses the existing C01 recovery state and original raw input for fresh interpretation before exploration. Human directives newer than the selected artifact invalidate it. One queued Plan cannot silently switch to a replacement selection.

## Prompts and budget

New immutable modules: explore-chapter-concepts v1, creative-exploration skill v2, plan-chapter v7, planning-agent role v2 and planning-quality v2 task compatibility. Earlier versions remain intact. Legacy schema v1 keeps template v5; old current schema uses v6 with historical Context; CP-004 v7 selects template v7/skill v2. Worker pre-Context estimation conservatively reserves the larger current template, avoiding under-budgeting.

Eligible initial Planning costs one extra model task. Technical retries use the existing attempt budget; no ordinary quality-driven re-exploration. No additional dependencies, queue, cache, vector store or scoring service.

## Read API and Debug

GET /workflows/{id}/planning/exploration returns current diagnostics; GET /planning/explorations/{exploration_id} returns workflow-scoped history; GET /planning/history includes paginated explorations. Status and dynamic freshness are separate. Debug exposes concepts, mechanism/pressure/progression, selection/rejections, risk explanations, exact input Brief and lineage IDs. Normal Workspace has no candidate selector and retains final Plan approval.

## Acceptance evidence

See [implementation report](../reports/NOVEL-013-creative-exploration.md). Offline tests establish engineering behavior only. `evals/creative-exploration/` holds actual historical Case 03 baseline references, bounded repetition/authority scenarios and a qualitative human worksheet. Real Provider B is NOT_RUN until explicitly user-triggered; previous E2E authorization does not transfer. Novelty, character fit, natural prose and multi-chapter semantic performance are not claimed from Mock tests. No NOVEL-014 or Retrieval Phase 2 is included.
