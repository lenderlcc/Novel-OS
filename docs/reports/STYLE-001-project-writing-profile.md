# STYLE-001 — Project Writing & Audience Profile

Date: 2026-09-16. Scope: project writing preferences, context integration, internal console, and manual evaluation evidence. No NOVEL-009 work. Existing uncommitted changes from earlier tickets are preserved; this report describes the STYLE-001 delta.

## 1. Background

NOVEL-008 can produce a traceable Draft from an approved Plan. It did not have an independent, explicit answer to “who is this for, and how should it read?” Story intent and audience experience must remain separate.

Read the repository's six design specifications and NOVEL-001–008 implementation reports before implementing. Reused existing API → Service → Repository → Database, project transaction locks, workflow human gates, ContextPackage, and PromptLineage infrastructure.

## 2. Case 01 Human Finding

The user's human assessment is **AUDIENCE_STYLE_MISMATCH**: slow pacing, excessive environment/object detail, low event density, overly restrained emotional/relationship payoff, and a literary reading experience. The finding and desired changes are saved in `evals/writing/v0.1/case-01/evaluation/human-review.md`. This is not an automatic quality score or inferred project configuration.

## 3. Product Diagnosis

Naturalness was underspecified relative to audience: avoiding formulaic prose does not imply slow, subtle, sparsely dialogued or literary prose. A small cooperative event can have high narrative efficiency. Product behavior needs an explicit, lower-authority audience preference alongside unchanged story constraints.

## 4. WritingProfile Architecture

Added `ProjectWritingProfile` and frozen `WritingPreferences` in `domain/writing_profile.py`; the Domain imports neither FastAPI nor SQLAlchemy. An independent ORM table, mapper/repository, application service and Pydantic API DTO follow existing boundaries. No generic configuration framework, style scoring engine, new workflow state or business agent was introduced.

## 5. Schema

Preferences contain `target_audience`; `pacing`; `narrative_density`, `description_density`, `dialogue_density`, `emotional_explicitness`, `subtext_level`, `literary_ornamentation`, `scene_hook_strength`, `chapter_ending_hook`, `relationship_payoff_visibility`, `exposition_density`, `naturalness`; and `reading_experience[]`, `guidance[]`, `avoid_tendencies[]`.

Pacing and intensity use named discrete levels; no false-precision numerical scores. Optional dimensions remain null, audience defaults to empty, lists to empty. Bounded text/list sizes and validation reject unknown fields, malformed enums, NUL and blank list entries. No genre-specific default is installed.

Server metadata: immutable record UUID, project/logical profile UUID, monotonically increasing version, DRAFT/APPROVED/SUPERSEDED, USER source, A5 authority, creator/time, approver/time and content hash. One logical profile per Project uses project UUID as `profile_id`; each version has a distinct row UUID.

## 6. Versioning

Every Save creates a new immutable DRAFT. `expected_version=0` creates v1; subsequent Save/Approve uses the currently observed version. A stale request returns VERSION_CONFLICT/409. Approval only accepts the current DRAFT; approving v2 supersedes the former approved v1 atomically, preserving its original payload and approval metadata.

Current and approved are separate derived pointers, returned from one SQL statement. Draft v2 never replaces approved v1 in context. No direct update/delete endpoint exists. Database triggers additionally reject payload changes and hard deletion, including direct SQL.

## 7. Authority

All versions, including APPROVED, remain **A5_USER_PREFERENCE**. Approval means consent to use preferences, not promotion to A2/A1/Canon. Only the existing USER application context can Save/Approve. Client-supplied status, authority, source, version or actor fields are rejected.

Profiles do not become Requirement, Decision, Canon, Lock or an approved story plan. Story MUST/FORBIDDEN, required outcome, locked direction and approved Plan remain authoritative. Existing project locks/archive checks apply to mutations. Profile text is untrusted context data and cannot add system capabilities.

## 8. Context Integration

Added exact relational source `PROJECT_WRITING_PROFILE`; no embeddings, vector store, RAG or additional Memory domain. New immutable profile versions:

| Context | New version | Purpose |
| --- | --- | --- |
| CP-004 | 5 | Planning preferences alongside sourced story constraints |
| CP-004R | 3 | Plan Review sees the same preference to avoid conflicting advice |
| CP-005 | 5 | Writing preferences alongside the exact approved Plan |

The selector is project-scoped, APPROVED-only, maximum one item, A5, and optional when no approved profile exists. P0 means retention priority, not story authority. Draft/current, other-project and superseded preference payloads cannot be selected. Requirement extraction remains story-only.

## 9. Planning Integration

Planner receives audience, pacing/density and payoff preferences as a separate context object. `authoritative_constraints`, `review_revision_targets` and `recommendations` remain separate. The existing sourced-constraint validator prevents Profile prose from becoming Plan.constraints. User outcome limits still control the plan.

Plan guidance emphasizes efficient small events and character interaction without over-engineering causal mechanics, fixed sentence counts or a prose blueprint. Review treats style suggestions as recommendations; it must not require excessive specificity and subsequently punish that specificity. No new style hard gate was introduced.

## 10. Writing Integration

Writer consumes exact approved preferences and Plan. It can adjust description allocation, interaction, pacing and visible payoff within the approved direction; it cannot enlarge a relationship outcome or remove a prohibition. Existing five writing skills remain active. No new Draft acceptance or rewrite behavior was added.

## 11. Prompt Changes

New immutable task templates: `plan-chapter` v5, `review-chapter-plan` v4, `write-chapter` v3. New skill: `natural-prose` v2. Prior versions and their hashes remain available for historical lineage. Planner/Review task-template manifests explicitly restrict compatible agents/task types.

All text updates have matching hashes. Prompt selection and compilation use the existing registry and lineage path. Project data is carried in the untrusted CONTEXT_DATA layer, never interpolated into a system policy.

## 12. Naturalness vs Literary Style Boundary

Naturalness remains compatible with fast pacing, direct interaction and visible emotional payoff. LOW literary ornamentation does not permit poor grammar. No mandatory short sentences, sentence quotas, cliffhangers, reversal counts, emotional rewards or “爽点” were introduced. Existing anti-smell guidance remains active, including over-explanation, emotion labeling, uniform rhythm, template transitions, functional dialogue, voice collapse, excessive closure and over-signposting.

## 13. Web Fiction Test Profile

Saved the ticket's exact example as `evals/writing/v0.1/case-01/web-fiction-test-profile.json`: mainstream Chinese online-fiction audience, MEDIUM_FAST pacing, HIGH narrative density, LOW_MEDIUM description, MEDIUM_HIGH dialogue/payoff, LOW ornamentation/exposition, HIGH naturalness, plus the supplied qualitative guidance. It is an explicit test fixture, not a universal project default or a “爽文” genre rule.

## 14. UI

The internal console has a project-keyed `WritingProfile.vue` panel. It displays current/approved versions, existing approved values, common controls and expandable advanced fields. “Load Web Fiction Test Profile” fills the form only; Save Draft and exact-version Approve are separate actions. Unsaved form changes disable approval. Conflict/error requires explicit refresh; no silent retry or automatic overwrite.

Unmount abort and disposed-response guards prevent a slow response from a previous Project from modifying a new Project's view. Human feedback handlers have no profile mutation path. Browser verification loaded the example and confirmed Current/Approved remained absent; no user profile was saved or approved by the agent.

## 15. API

Base: `/api/v1/projects/{project_id}/writing-profile`.

| Method | Path suffix | Behavior |
| --- | --- | --- |
| GET | empty | Current and approved versions and DTOs |
| GET | `/approved` | Exact approved DTO, or null |
| GET | `/versions` | Paginated immutable version history |
| POST | `/drafts` | `{expected_version, preferences, reason?}` → new DRAFT |
| POST | `/approve` | `{expected_version, reason?}` → approve that current DRAFT |

Schemas reject extra fields. Responses are explicitly mapped DTOs, not ORM objects. Frontend OpenAPI types were regenerated.

## 16. Persistence

Migration `0010_project_writing_profile` follows `0009_writing_agent`, adding only `project_writing_profiles`, its indexes/checks and immutability trigger. Unique project/version and a partial unique APPROVED index protect concurrency. Source/authority and approval metadata have database checks.

Repositories map/flush but never commit. Service transactions reuse the existing Project root lock, validate the optimistic version, persist lifecycle changes and write audits atomically. Audit failure rolls back both approval and supersession. Concurrent identical Save requests produce one 201 and one 409.

Upgrade → downgrade -1 → upgrade was executed against development PostgreSQL while the new table was empty. `alembic check` reports no drift. The migration regression snapshots all prior tables and verifies identical data across the round trip. Downgrading 0010 intentionally drops profile history; do not downgrade a database containing profiles without preserving them first.

## 17. Lineage

Every selected preference item carries `writing_profile_id`, `writing_profile_version`, `writing_profile_hash`, source record/version/status, authority and provenance. The canonical SHA-256 covers logical profile, version and normalized preferences. Context serialization and existing PromptLineage pin that evidence. WritingResult continues to link Task/Run, ModelProfile, ContextPackage, PromptLineage, Plan and immutable Draft.

No duplicated mutable profile pointer was added to WritingResult. The existing evidence chain resolves the exact selection. The A/B exporter records exact PLAN/REVIEW/WRITE bindings and rejects inconsistent versions, unapproved/A2 evidence, changed raw requirement/model parameters, or Draft/hash mismatch.

## 18. Freshness

Planning/Review tasks store a server-owned schedule binding, including explicit absence. Checks run before context/model execution and result acceptance; approving a different profile blocks stale tasks instead of silently substituting a new version. The schedule binding stays in task metadata but is filtered out of model-visible requirements.

Context source snapshots track exact approved identity/version/hash and absence→first-approval. Existing WritingBindingService captures the profile through its immutable source snapshot. Plan freshness is checked again before review/human approval, so changing preferences requires an explicit replan and new human gate. Historical pre-STYLE plans with no selector retain historical semantics; they are not rewritten.

## 19. Tests

Added 51 backend tests and four frontend tests. Focused coverage:

- Core API/repository/service/database: lifecycle, separate pointers, stale approval, forgery rejection, isolation, project lock, payload immutability/hard delete, USER-only writes, repository no-commit, rollback, concurrent version allocation, migration preservation.
- Context/service integration: approved-only Planning/Review/Writing, no draft/foreign leakage, hard MUST/FORBIDDEN and locked dependency retention, preference injection remains data, immutable lineage, no automatic Chapter approval.
- Freshness: three stages × queued/before-model/during-model approval changes; first approval invalidates a no-profile task; stale Plan gate/replan; Human Reject does not update preferences.
- Contract tests: exact fixture/non-default, invalid payloads, naturalness/authority/anti-template prompt boundaries, private scheduling metadata filtering.
- Ten offline HTTPX MockTransport export tests: GET-only behavior, three-stage bindings, inconsistent/missing Review evidence, authority/status, raw/model/content mismatch, missing Draft and explicitly partial C06 export.
- Four new UI tests: load/save/approve separation, current vs approved, 409 handling, project/unmount late responses.

## 20. Full Regression

Final verification completed on 2026-09-16. All model-backed regression tests use mock/recorded providers; real-provider opt-in tests remain skipped.

| Check | Result |
| --- | --- |
| Backend full pytest | PASS — 919 passed, 4 explicit real-provider skips, 2 upstream warnings; 586.24s |
| Backend/script Ruff check | PASS |
| Ruff format --check | PASS (262 Python files) |
| git diff --check | PASS; untracked source whitespace also checked |
| Frontend test | PASS — 45 tests / 5 files |
| Frontend lint | PASS |
| Frontend build / TypeScript | PASS |
| Alembic upgrade / downgrade -1 / upgrade | PASS |
| Alembic metadata drift check | PASS |
| Docker build | PASS — final image rebuilt |
| Docker health / health/db | PASS inside container |
| Host API and frontend proxy health/db | PASS |
| Fixture / private TOML Vite access | 200 / 403 |

Reproduce from `backend/`: `uv run --locked pytest -q --tb=short --show-capture=no`,
`uv run --locked ruff check .`, `uv run --locked ruff format --check .`,
`uv run --locked alembic upgrade head`, `uv run --locked alembic downgrade -1`,
`uv run --locked alembic upgrade head`, and `uv run --locked alembic check`.
From `frontend/`: `npm test`, `npm run lint`, `npm run build`.
From repository root: `git diff --check`, `docker compose build backend`.
Run migration downgrade only on disposable/empty-profile data as described above.

The first complete backend run found four stale version assertions and one actual scheduling-metadata leak; the assertions were updated while retaining legacy hash tests, and the leak was fixed at the context projection boundary. Final full regression includes the corrections.

Independent review (separate model) checked authority, freshness, prompt boundaries, repositories, migration, UI, scope and A/B evidence. No Critical finding. Its Required finding (missing Review-stage profile verification in the exporter) was fixed with negative tests; optional manifest narrowing was also applied. Final delta re-review passed with no remaining Critical/Required findings.

## 21. Case 01 Baseline

Preserved A under `evals/writing/v0.1/case-01/baseline/` with hashes:

- Workflow `cc7a88d3-087d-4da6-a540-9a0463eddf46`; same original Project and Chapter 1.
- Original raw requirement SHA-256 `82490c0b11dc0722cede763d4558334b04a2f2879b12d5f845603ef84b1fb907`.
- Approved Plan v2, Draft v1; Draft SHA-256 `28e3f7b24ca01c31ad94e1145535cc3d4f4d968acd5807f4c9a76e943bd06433`.
- Lingzhi / gpt-5.6-sol, original full ModelProfile, CP-005 v4, write-chapter v2, WritingResult and PromptLineage.
- A has no approved WritingProfile. Baseline Draft remains unapproved. No baseline content, Plan, Requirement or workflow was rewritten during STYLE-001 implementation.

`uv run --locked python ../scripts/case01_style_ab.py` validates manifest/file hashes without database mutation or model calls.

## 22. Case 01 A/B Procedure

The complete opt-in workflow is `evals/writing/v0.1/case-01/case01_style_ab.md`. User reviews, Saves and Approves the example explicitly; grants a new bounded real-provider opt-in; preserves/cancels A's completed test workflow without deleting its artifacts; creates B on the same Project/Chapter with byte-identical raw requirement.

Allow at most one Requirement and two Planning/Review iterations (five planning-stage calls), then one Writing call only after human approval of the exact new Plan. Worker runs `--once` per task, with one attempt and TOML-only configuration. Check the queue before each call. Stop on failure/block, or at C08 after the Draft.

The read-only exporter uses `--planning-only` at C06 and a separate complete directory at C08. It records exact model parameters, source evidence, Profile/Plan, ContextPackage, PromptLineage, all run attempts, WritingResult and Draft. It never invokes a provider or chooses a winner.

## 23. A/B Result

The user explicitly authorized B on 2026-09-16. Because the console contained two Projects
with the same visible name, the first Save/Approve landed on the older Project. Preflight caught
the project mismatch before any model call. The same reviewed fixture was then saved and
approved as Profile v1 on the Case 01 Project under the user's authorization; both records remain
auditable and no history was deleted.

B Workflow `65f46a36-3ced-487a-83ce-f66af213fa12` used the byte-identical original Requirement,
Lingzhi / gpt-5.6-sol and the same full ModelProfile parameters as A. Profile v1 hash is
`ac5d7feeb0064f3a26825603d0b4ac5d93718d66637646d5383c17f74acb03cf`.

- Requirement succeeded in one call. It produced 3 MUST, 2 FORBIDDEN, 1 SHOULD and
  1 PREFERENCE with minimal exact quotes, separate intent/objective, HIGH creative freedom and
  confidence 0.90.
- Planning succeeded in one call. CP-004 v5 selected exact approved Profile v1 at A5. The Plan
  retained the same required outcome and all authoritative constraints, proposed no major change,
  and used three compact scenes with clearer interaction/payoff guidance.
- Plan Review received CP-004R v3 and the same exact Profile binding, but the Lingzhi Provider
  returned no response before the configured 120-second limit. The run ended after 120,697 ms
  with `MODEL_TIMEOUT`; no raw response existed to parse or validate.
- The single-attempt policy correctly stopped Workflow B at C91_FAILED. There was no automatic
  retry, second Planning iteration, human gate, Writing task, new Draft or winner selection.

Read-only partial evidence is stored under `evals/writing/v0.1/case-01/planning-b/`. It includes
all three Runs, ContextPackages and PromptLineages and proves the Planning and Review runs used
the same Profile ID/version/hash. This is an incomplete Planning result, not a completed A/B.

### B2 completion update

An explicitly authorized clean retry used Workflow `da39e1f2-cbd3-4b7d-95e3-63ce7334b48d`.
Requirement, Planning and Review each succeeded in one call; Review reached effective PASS in the
first planning iteration. The human approved exact Plan v4. A single Writing call then created
Draft v2 and reached C08 with deterministic PASS. Chapter `current_version=2` while
`approved_version=null`; Draft approval remains a separate future human decision.

All four stages selected the same approved Profile v1/hash. Writing used CP-005 v5, exact approved
Plan v4, write-chapter v3 and Lingzhi / gpt-5.6-sol with the same full ModelProfile parameters as A.
Complete evidence and the 3,105-character Draft are stored under
`evals/writing/v0.1/case-01/writing-b-retry/`. Human A/B prose evaluation remains pending; no
automatic winner was selected.

Changed Prompt/Context versions and nondeterministic re-planning are recorded confounds. This first comparison tests STYLE-001 product behavior against historical A, not an isolated profile-only causal experiment. Same raw input and model alone cannot prove identical generated planning decisions; the major direction must be compared at the human Plan gate.

## 24. Human Evaluation

`evaluation/style-ab-human-review.md` separates hard story consistency, 13 reading-experience dimensions and eight naturalness indicators. The human records evidence, differences, limitations and A/B/TIE; no automatic score or winner. Audience fit, improved prose and controllable behavioral differences remain unproven until B and that evaluation exist.

## 25. Architecture Deviations

No confirmed architecture was refactored. Two local implementation choices are explicit:

1. A dedicated small preference table/service preserves immutable A5 semantics; the existing generic approval lifecycle would promote story authority and is therefore not reused for profile approval. Current/approved pointers are derived instead of adding mutable Project columns.
2. CP-004R also receives the approved profile, so Review understands preferences without converting them into a hard quality gate. Scheduling pins reuse the existing immutable task metadata envelope and are excluded from model-visible requirements.

No dependency was added. Configuration remains TOML. Runtime/DB credentials were not copied into evidence, generated types or documentation.

## 26. Known Issues

- Human prose/audience assessment remains incomplete. Engineering checks and deterministic PASS
  do not establish that B is better than A.
- The first B workflow remains terminal after its Review timeout; B2 preserves it as immutable
  failure evidence rather than rewriting history.
- Two upstream Starlette/httpx/anyio deprecation warnings remain; no dependency upgrade was made for this ticket.
- Colima reports the Docker backend's published port but its host forwarding was unavailable in this session. Container health and DB health pass. The test console is served by the documented host Uvicorn development path against the same Docker PostgreSQL; this does not alter application architecture.
- The internal console retains the existing local-development actor/authentication model; this is not a public multi-user deployment.
- Large optional preference notes can trigger the existing explicit context-budget block; preferences are not silently truncated or promoted above story truth.

## 27. Deferred Items

Human A/B comparison and winner selection. Production authentication, automatic style learning,
scoring and author imitation are outside this ticket. Full Chapter Review, QualityAggregator,
AI smell reviewer, revision/automatic rewrite, Human Chapter Acceptance and Memory Commit remain
deferred to future tickets; NOVEL-009 was not started.

## 28. Acceptance Result

**Engineering Acceptance: PASS.**

**AI Behavior Acceptance: READY FOR HUMAN REVIEW. Human Prose Evaluation: PENDING.**

**STYLE-001 overall: CONDITIONAL PASS. Final product acceptance awaits human comparison.** The implementation supplies controlled, versioned preferences and evidence, without claiming that Draft B must be better or turning a human rejection into learned authority.


Current handoff: frontend `http://127.0.0.1:5173/`, host API `http://127.0.0.1:8000/`;
Docker PostgreSQL remains running. No Worker is running. Case 01 Profile v1 and Plan v4 are
approved; Draft v2 is current and unapproved. Human A/B comparison is the next step. No
commit/push was requested or performed.
