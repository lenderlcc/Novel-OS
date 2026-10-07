# NOVEL-014 — Character Depth & Voice

Date: 2026-10-06. Branch: `wfg/novel-014-character-depth-voice`.

## 1. Background

Make a character's attention, decisions, defense and interlocutor-specific expression available to the existing creative pipeline. Avoid treating characters as interchangeable names attached to plot functions. Implementation reuses existing identities, approval/version/transaction infrastructure, runtime, Context and lineage.

## 2. Phase Status

| Phase | Engineering | Real Provider / human acceptance |
|---|---|---|
| NOVEL-001–012 | COMPLETE | Multi-chapter E2E-001R PENDING |
| NOVEL-013 | COMPLETE, frozen | PENDING |
| NOVEL-014 | COMPLETE / PASS | NOT_RUN / NOT_EVALUATED |

Local main is `1cb275d2439af3e9c5e2982002ca9c1d4fc9e107`, ahead of the fetched remote main `8199173`. The new branch starts from local main while preserving the existing 012/013 worktree changes. This task does not discard, commit or push earlier work; tests remain local. Existing real E2E project/Plan gate and running development data are untouched.

## 3. Manual Failure Evidence

The user's ticket reports recurring Case 01–05/Revision problems: WEAK_CHARACTER_VOICE, CHARACTERS_AS_ARGUMENTS, GENERIC_INNER_VOICE, LOW_RELATIONAL_SPECIFICITY and OVER_STRUCTURED_DIALOGUE. Characters represent positions, dialogue follows argument/counterargument/clarification/conclusion, and everyone explains themselves precisely. These are reported acceptance observations, not new model runs or evidence of improvement. The synthetic weak-character-source fixture is clearly human-authored and is not a historical Provider output.

## 4. Scope

Implemented sparse user-owned CharacterBehaviorProfile, immutable versions/approval, manual identity creation, optional explicit A02 natural-language organization, relevant approved Context, new Prompt versions, lightweight UI/Debug, migration, tests/docs and offline eval protocols. No new Agent, personality learner, CharacterVoiceResult, psychology scores, graph, Vector DB, QualityEngine replacement or NOVEL-015 functionality. No new dependency or environment configuration.

## 5. Existing Character Audit

memory_subjects(kind=CHARACTER) is the current identity store. committed_memory already separates CHARACTER_STATE, RELATIONSHIP_STATE and owned CHARACTER_KNOWLEDGE from global facts. Neither an identity row nor a dynamic memory entry can safely represent multiple independently approved immutable behavior definitions. Add exactly one profile table; retain identity/state/knowledge and existing retrieval/commit paths. Manual identity batch_id=null plus created_at/by enables defining a character before any completed chapter, without inventing a Canon batch or State.

## 6. CharacterBehaviorProfile

Shared `characters/schemas.py` defines the canonical sparse body: nullable decision_tendency, risk_tolerance LOW/MEDIUM/HIGH, conflict_response, emotional_defense, communication_style, attention_bias, self_image, vulnerability; empty-default assumptions, avoided admissions, occasional tells, relationship modifiers, guidance and avoid_tendencies. Unknown fields, blank/NUL text and invalid risk values fail. Users can save an empty/sparse profile without filling a questionnaire. Domain is independent from ORM/FastAPI; ORM is never an API DTO.

## 7. Relationship Modifier

Embedded sparse other_character_id, interaction_tendency, trust_expression, conflict_pattern, things_left_unsaid and guidance. Same-project CHARACTER/non-self/unique counterpart validation applies in shared contract and Service. Only involved counterpart modifiers enter Context. They share the parent profile version; no separate graph/table/automatic N×N population. trust_expression does not change current trust, hostility or cooperation.

## 8. Authority

DRAFT A7_AI_INFERENCE → explicit USER approval → A3_CANON; no new authority enum. A3 records the approved creative definition, while tendencies permit motivated exceptions. It cannot override User Locks, Canon State, actual Knowledge or approved Plan. Project mutation checks user identity, archive and Locks. API extra-forbid prevents fake status/version/authority/approval/system actor. A07, Review, Revision and Feedback cannot write profiles. Prompt data cannot grant capabilities.

## 9. Versioning

Every save appends DRAFT with expected_version (0 initially); a new Draft does not alter the approved pointer. Approval binds the current exact token and atomically supersedes the previous approved record. Unique (character_id, version), one-approved partial index and existing project lock prevent duplicate/current ambiguity. Immutable body/source/history triggers reject direct SQL changes/deletion. profile_id/logical_id is uuid5(character_id, "character-behavior-profile"), stable across versions and distinct from the character identity and record IDs without a duplicate database column. profile_hash covers logical ID, version and canonical body; relationship modifier version equals enclosing version.

0019_character_behavior_profile adds character_behavior_profiles and manual identity provenance, backfilled from old commit batches. Fresh-schema upgrade/downgrade/upgrade/check passed. Operational downgrade refuses existing manual identities: 0018 cannot represent them without fabricating a batch. Export/migrate these explicitly before rollback; the migration does not erase them to force success.

## 10. UI

Workspace sidebar opens a small Characters drawer. It lists/creates identities, shows basic information/current committed State separately, and provides six common behavior dimensions. Advanced fields and sparse per-person expression collapse by default. Save creates a new Draft, approval is explicit; current/approved pointers and history remain visible. Natural-language action states that it calls a model. Project/character changes ignore late responses. Failed operations preserve edits/description and allow manual correction/retry, without automatic model calls. Initial profile-load failure disables commands.

## 11. Natural Language Profile Input

POST behavior-profile/interpret uses existing A02/AgentRuntime/PromptRuntime/Provider/parser through the shared pure report entry point. CP-010 v1 contains user description and server-resolved explicitly mentioned related identities, not project Canon or another profile. Pydantic CharacterProfileAgentResult owns output; proposed_changes/memory_proposals are empty, server fields are forbidden, unspecified body fields stay sparse. Hard-rule-only requests ask for clarification/Decision/Lock handling.

The short preflight transaction verifies actor/scope/Lock/token and ends before model IO; ordinary create_draft rechecks after the call. Success saves raw source_text in an unapproved Draft. No fake Chapter/Workflow, new persistent task family or automatic retries are created. This synchronous report path does not persist a new AgentRun artifact; downstream chapter tasks retain the existing ContextPackage/PromptLineage/SourceVersions chain. Mock interpretation is explicitly an empty offline fixture, not a semantic keyword parser or quality proof.

## 12. A03 Integration

Approved relevant profiles enter Exploration/Planning and Plan Review. A03 considers causal choice, pressure and expression without imposing catchphrases, mandatory traits, paragraph quotas or fixed actions. A low-risk tendency cannot reject a motivated approved outcome. guidance is not copied into authoritative_constraints or constraints[]. Review recommendations remain revision targets/recommendations rather than becoming user constraints.

## 13. NOVEL-013 Integration

Only new Context versions and new Prompt usage instructions integrate profiles. Candidate count, selection policy, output schema, creativity levels, state machine, artifact and retries are unchanged. Baseline hash checks verify exploration_schemas.py, exploration_policy.py, historical exploration v1/plan v7 templates and chapter-planning.v4.yaml are unchanged. No speculative creative tuning or claim of real creative improvement.

## 14. A04 Integration

Writing reads exact approved Plan plus relevant approved profiles. Voice draws from desires, known information, avoided admissions, emotional defense, attention and specific interlocutor; it does not require slang, filler, silence, misunderstandings or personality slogans. Motivated exceptions preserve approved outcomes. STYLE-002 first/third-person narration remains intact. Profile version lineage is automatically captured in ContextPackage, without adding citation fields to WritingResult.

## 15. A05 Integration

Plan, Compliance and Narrative Review receive relevant approved profiles, using existing accurate issue codes/evidence. Flexible tendency differences alone are not automatic OOC/P0 failures. The current Quality schema/taxonomy remains unchanged. Grounded voice diagnosis and handling of motivated exceptions require future real/human evaluation; tests establish source/contract boundaries.

## 16. A06 Integration

Revision Planning/Execution use relevant approved profiles alongside exact Review, source Draft, approved inputs and existing locality/preservation contract. They can repair local expression without reconstructing scenes, Plan, relationships or long-term definitions. Existing fidelity task/result rules are unchanged; candidates must pass fidelity before producing a successor Draft and independent Review.

## 17. NOVEL-011 Integration

Feedback interpretation sees the exact profile Context. A local 'this line does not sound like A' uses the existing targeted Revision route. A permanent redefinition uses existing explicit profile/preference-change handling rather than silent learning. Feedback and A06 do not approve/update profiles; feedback-derived tasks reuse the same freshness and fidelity path.

## 18. Knowledge Firewall

Identity, State, Knowledge, relationship facts and behavior tendencies remain distinct. Profile perceptiveness grants no secret/global knowledge; modifiers do not assert current trust. Writer still uses approved POV ownership and owned KNOWS/belief/suspicion distinctions; future policy/horizon remain unchanged. No prior raw chapter shortcut or secret passed as personality data. A07's six memory types and immutable commit boundaries remain separate from profiles.

## 19. Context Integration

One approved-character-behavior-profiles selector/adapter, optional P0 and exact A3 APPROVED-only. SourceType.EXTENSION plus payload kind=CHARACTER_BEHAVIOR_PROFILE identifies profiles without expanding the shared enum and changing historical output Schema hashes. Stable namespaced logical IDs keep identity and Profile sources distinct. Relevance derives from actual task/Brief/selected-concept or approved Plan/target Draft values plus explicit POV; serialization keys, UUID/source metadata and enum-only fields cannot manufacture relevance. Modifiers retain only involved counterpart UUIDs. Persisted SourceVersions record selected SourceRef fields source_type/source_id/logical_id/version. Profile ID/version/hash are bound in ContextPackage payloads; source_snapshots also preserve empty selector bindings.

Snapshot checks preserve empty sets and approved bindings. Saving another Draft does not stale tasks; relevant approval changes stale queued/inflight Planning/Writing/Revision/Feedback before use or persistence. A new explicitly requested task binds the then-approved profile snapshot; a tendency update alone does not invalidate an already approved Plan or force replanning. Historical Context pins without the selector remain valid under their original contracts. No all-project profile dump, Vector RAG or parallel freshness engine.

## 20. Prompt Versions

| Task | Context | New Prompt |
|---|---|---|
| Exploration | CP-004E v2 | explore-chapter-concepts v2 |
| Planning without / with Exploration | CP-004 v8 / v9 | plan-chapter v8 / v9 |
| Plan Review | CP-004R v4 | review-chapter-plan v5 |
| Writing | CP-005 v7 | write-chapter v5 |
| Compliance / Narrative Review | CP-006 v4 | review-chapter-compliance v2 / review-chapter-narrative v3 |
| Revision Planning / Execution | CP-007 v8 | plan-chapter-revision v7 / revise-chapter v8 |
| Feedback | CP-008 v2 | interpret-chapter-feedback v3 |
| Profile interpretation | CP-010 v1 | interpret-character-profile v1; character-profile-interpreter role v1 |

Historical modules/profile JSON are preserved. Exact Context version selects its matching template; current estimates conservatively reserve current usage instructions. Profiles themselves are in Context, never baked into templates. The appended instructions explain usage and authority rather than repeating a character form or requiring model reasoning disclosure.

## 21. Tests

Added local collected tests: core/test_character_profiles_local.py (persistence/API/migration/concurrency/rollback/NL), context/test_character_profile_context.py (all creative tasks/relevance/lineage/freshness/firewall), test_character_profile_contracts.py (A02 shared parser/schema/capabilities/historical Prompt pins), and frontend characterProfiles.test.ts (drawer/edit/approval/NL/advanced/Debug/response races/error recovery).

| Ticket criteria | Engineering evidence |
|---|---|
| 1–6 create/version/Draft isolation/approve/supersede/history | API, SQL immutability and Context tests |
| 7–9 invalid risk/counterpart/cross-project | Shared Pydantic + API/DB negative tests |
| 10 source refs/lineage | Exact Context source triples/profile hash and persisted pipeline checks |
| 11–18 task relevance and sparse pair filtering | Parametrized Exploration/Plan/Write/Review/Revision/Feedback Context tests |
| 19 approved changes stale tasks | Scheduling/result-side checks including empty-set/addition and Revision/Feedback |
| 20–25 Lock/Canon/Knowledge/Plan/A07/Feedback boundaries | User/project Lock tests, knowledge firewall, unchanged mutation contracts and full workflows |
| 26–34 UI operations/advanced/modifier/Debug versions | Component/API client/Debug tests plus typecheck/build |

Regression tests verify engineering boundaries, not a statistical or semantic claim of improved voice. Tests are not committed.

## 22. Engineering Evaluation

Final full backend pytest: **1,634 passed, 4 skipped, 0 failed, 0 errors**. The four file-sharded processes all exited 0 (456/423/418/337 passed); an independent normal collect-only run confirmed all 1,638 cases were selected exactly once. Longest shard: 544.73 seconds. The skipped OpenAI smoke, Planning E2E, Writing smoke and Case 01 Requirement attempt each require explicit --live-model; no live flag or paid call was used.

Focused checks also passed: persistence 28 tests; 24 Character Context/Memory isolation tests including identity/Profile namespace coexistence; 18 migration compatibility tests; 74 Context/Revision/Feedback/history workflow tests and 19 frozen-Schema/character contracts. Backend Ruff check and format check passed (440 files); git diff --check passed. Final frontend after OpenAPI regeneration: **168 tests / 13 files PASS**, npm run lint/typecheck/build PASS. Browser inspection of the real UI with entirely intercepted fixture GETs covered basic identity/committed State, approved profile summary and expanded advanced controls; no POST or Provider request occurred.

Docker image novel014-acceptance-backend built successfully from the final contract-aligned source (sha256:d9ef271cb084b88daa750bdc7b2ecc75a0ee58a92fea0e1e7b0ab5df95095cff); source hashes remained stable during final tests/build. Isolated mock/non-root container, no published ports/Worker, separate novel_os_test schema: startup and health/health/db HTTP 200. Alembic upgrade head → downgrade -1 → upgrade head produced 0019 → 0018 → 0019; check reports no new upgrade operations. Container/schema/private config were removed. Existing native backend/db/frontend probes returned 200 before and after; no restart/development data migration was performed.

Evidence: ignored backend/.runtime/novel014/pytest-*.xml/log, final-summary.json, normal-collection.json, collection-coverage.json and final-source-hashes.json; docker-evidence.json/docker-build.log/docker-migration.log; frontend/.runtime/novel014-final-gates.log; root .runtime/novel014/historical-contracts.json. Superseded pre-fix runs are separated and excluded from final results. Docs update 02/03/05/06 plus new [12-Character-Depth-Voice](../specs/12-Character-Depth-Voice.md).

Final independent review has no remaining Critical/Required findings. Fixed metadata-driven short-name contamination, NL input length mismatch, unrecoverable UI mutation-error state, and Writer instruction asking for absent citation fields. Full regression exposed shared SourceType enum propagation into historical Schema hashes; reusing EXTENSION with a dedicated selector/payload kind and namespaced UUID restored those contracts. Exact Planning template selection now also checks Context profile ID, preserving historical pins and unrelated-profile behavior. Baseline verification preserves 233 historical Prompt/Context/013 Schema-policy-workflow/dependency files; old hash assertions remain unchanged while current-version tests follow the new versions. Additional reason validation rejects blank/NUL audit input. Eval reciprocal review fixed variant inputs to name their real characters so normal retrieval, rather than manually injected Context, selects the intended profiles. The final review's documentation recommendations now distinguish selected SourceVersions from empty selector snapshots.

## 23. Real Provider Evaluation

**NOT_RUN.** No paid Provider call, new real Project, model output or user approval was created. Five offline evals under [character-depth](../../evals/character-depth/README.md): same-pressure A/B, A speaking to B/C, motivated tendency exception, knowledge boundary and old no-profile project. Includes deliberate weak voice prose and Review/Revision/Feedback human protocols.

Human Behavior/Prose Evaluation: **NOT_EVALUATED**. [Manual worksheet](../../evals/character-depth/manual-evaluation.md) records exact runtime/profile/Context/Prompt lineage, attention/decision/defense/interlocutor differences, knowledge isolation and source fidelity. No exact prose comparison or fabricated quality score. E2E-001R and NOVEL-013 real acceptance remain pending.

## 24. Known Limitations

- Real interpretation/voice/Review/Revision improvement is unverified; all semantic outcomes remain pending.
- Relevance reuses existing normalized name/alias substring matching. Serialization metadata false positives are fixed; ambiguous very short aliases appearing inside real prose words can still overmatch. It is not a semantic entity linker.
- Natural-language profile organization is a synchronous explicit A02 report, without a resumable queued interpretation artifact; it preserves source_text and uses existing parser, followed by user inspection/approval.
- Downgrade with manual identities needs explicit export/migration because the previous schema requires a real memory batch.
- Profiles have no individual Lock endpoint, automatic learning, edit-in-place, personality metrics or relation graph; existing project Locks/explicit Decisions retain hard constraints.
- The existing Workspace targets desktop with a 760px minimum body width; this ticket reuses its drawer rather than redesigning mobile layout.

## 25. Deferred Work

Real Profile interpretation and five character evaluations, real A05 voice diagnostics/A06 fidelity/A02 feedback behavior, and E2E-001R multi-chapter human acceptance. Any future personality-learning/entity-linker design needs its own scope. No automatic NOVEL-015/long-range planning, 013 creative tuning or new Memory/Provider infrastructure.

## 26. Acceptance Result

**Engineering Acceptance: PASS.** All engineering criteria 1–34, full 001–013 regression, lint/format/diff, frontend tests/typecheck/build and Docker/migration/health gates passed. No remaining independent-review required fixes.

**Real Behavior Acceptance: NOT_RUN. Human Behavior/Prose Evaluation: NOT_EVALUATED.** NOVEL-013 and E2E-001R real/human acceptance remain PENDING. Mock/fixture successes do not establish that character voice, Review diagnosis or local Revision quality improved.

Overall **NOVEL-014 = CONDITIONAL PASS**, with engineering complete and real behavior explicitly pending. Stop after NOVEL-014 for user Review. No NOVEL-015, commit/push, paid Provider call or development database migration/restart was performed.

## 27. Post-Review Context Fix (2026-10-06)

Fixed the two P2 retrieval findings within the existing Context services:

- Plan Review resolves the workflow's exact proposed Plan generation; Writing, Quality Review, Feedback and all Revision stages reuse their existing exact generation to carry POV identity. Anonymous first-person prose retains its approved character profile even without a literal character name. A missing bound version never falls back to current/latest Plan.
- Character relevance reads required_outcome, plot_progression, information_release, ending_state, constraints and risks in addition to the original Plan fields. The exact bound Plan remains the source. Existing story-value filtering continues excluding serialization metadata/UUIDs, unrelated profiles and modifiers, current unapproved Plan versions and unapproved profile drafts.

No new repository, entity, schema, migration, Prompt version, workflow, frontend path or permission rule. KnowledgeScope, private-knowledge authorization and future-information filtering are unchanged. Documentation now follows Ticket §58: profile approval drift invalidates affected pending/inflight tasks; a new explicitly requested task can bind the new approved profile without forcing an already approved Plan to be replanned.

Regression evidence:

- Six Plan-field cases failed before the fix; the complete character Context file passes **27 tests** afterward. Each new case also verifies an approved Plan v1/current Plan v2 split, approved profile v1/current profile Draft v2, metadata exclusion and sparse relationship modifiers.
- Three POV cases failed before the fix and pass afterward (**3 tests**, final run 9.42 seconds): anonymous first-person Plan Review → Writing → Quality Review → Feedback → Revision Planning/Execution/Fidelity → Draft v2/new Review; queued Review approval drift blocked before any Provider call; current Plan v2 cannot replace workflow-bound Plan v1 even without a required Plan selector.
- Independent final review found no additional P1/P2 issues. Its 21 offline ownership/cross-project filter checks passed. Backend Ruff check, format check (441 files) and git diff --check passed.
- Related Context, Exploration, Writing, Memory isolation/commit, Quality recovery, Revision safety, Feedback and POV regressions: **239 passed, 0 failed/errors/skips**, 843.34 seconds. Evidence: backend/.runtime/novel014/context-fix-regressions.xml/log and context-fix-source-hashes.json. Product source fingerprints remained unchanged during this run. The strengthened current Plan v2/bound Plan v1 POV case also passed in the final three-case rerun above.

The full-suite and Docker/migration results in §22 describe the earlier NOVEL-014 verification, before this local patch. All new reproductions use Mock and isolated schemas in the separate `_test` database. No real Provider or human voice evaluation was performed; behavioral acceptance remains pending. Tests remain local and uncommitted.
