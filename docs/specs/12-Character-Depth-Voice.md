# NOVEL-014 — Character Depth & Voice

## Scope and phase status

Phase 1 NOVEL-001–012 engineering is complete. E2E-001R real multi-chapter/human acceptance remains pending. NOVEL-013 engineering is complete with real acceptance pending; its candidate counts, selection, workflow and creativity semantics are frozen. NOVEL-014 adds user-defined long-term behavior/expression tendencies and relevant context integration. It does not prove improved character voice from Mock results. No NOVEL-015 work is included.

## Character model and existing layers

Reuse existing memory_subjects(kind=CHARACTER) for Static Identity. Committed CHARACTER_STATE and RELATIONSHIP_STATE describe changing facts; CHARACTER_KNOWLEDGE has an owner and epistemic status. A new CharacterBehaviorProfile describes stable creative tendencies without merging those layers. Manual character creation adds name/aliases/provenance only, with no fabricated biography, current state, secret, relationship truth or Memory batch.

## Sparse behavior profile

The shared Pydantic CharacterBehaviorProfileBody is the input and interpretation contract. All scalars are nullable, lists default empty; an old project needs no fabricated default profile.

| Field | Meaning |
|---|---|
| decision_tendency | Usual approach to decisions |
| risk_tolerance | Optional coarse LOW / MEDIUM / HIGH tendency |
| conflict_response | Usual response to disagreement/pressure |
| emotional_defense | How the person protects themselves emotionally |
| communication_style | How they express intent, not mandated phrases |
| attention_bias | What they first notice or overlook |
| self_image / vulnerability | Creative self-perception and sensitive points |
| default_assumptions | Usual interpretation habits, not facts |
| avoids_saying_directly | Matters they tend to avoid admitting |
| behavioral_tells | Occasional observable tendencies, never per-chapter quotas |
| guidance / avoid_tendencies | Flexible creative guidance |
| relationship_modifiers | Sparse expression changes toward specified people |

There is no MBTI, psychological scoring, personality taxonomy or rule compiler. Text is bounded and rejects blank/NUL values; invalid risk enums and unknown fields fail validation.

## Relationship modifiers

Each embedded modifier has other_character_id plus nullable interaction_tendency, trust_expression, conflict_pattern and sparse things_left_unsaid/guidance. The counterpart must be another CHARACTER in the same project; duplicates and self-links fail. Modifiers share the enclosing profile version, not their own independent lifecycle. They describe how A tends to respond to B, not whether trust/cooperation/hostility is currently true. No automatic N×N population or relationship graph is built.

## Authority and knowledge boundary

Drafts are A7_AI_INFERENCE, including manual drafts. Only explicit user approval makes a profile A3_CANON. A3 records creative definition provenance; it does not make every tendency an unbreakable command. Locks, Canon State, actual Knowledge and exact approved Plan prevail. A low-risk character can take a motivated risk. Guidance cannot authorize new facts, capabilities or private knowledge; higher perceptiveness does not disclose a secret. A07, feedback, Review and Revision cannot persist profiles or learn them from a scene.

Hard constraints belong to Decision/Lock. Interpretation returns NEEDS_HUMAN for an input consisting only of such rules rather than silently creating a behavioral script. Semantic adherence is subject to future real/human evaluation, not a deterministic keyword personality checker.

## Versioning and transactions

Create/edit always appends a DRAFT using expected_version=latest current version (0 initially). Approval accepts only the current Draft token, changes approval metadata, supersedes the previous approved record and writes Audit atomically. A new Draft leaves the old approved version active. Historical bodies/raw source stay immutable; SQL triggers also reject direct update/delete and invalid lifecycle transitions.

API → Service → Repository → PostgreSQL. Service owns transactions using the existing project lock and user/Lock/archive checks; Repository only adds/flushes. Unique character/version and single-approved indexes reinforce concurrency. Logical profile_id=uuid5(character_id, "character-behavior-profile"); this stable derived ID avoids a duplicate database column and collisions with character identity sources. The hash binds logical ID, version and canonical body. API exposes current_profile_version and approved_profile_version separately.

## Natural-language input

POST behavior-profile/interpret uses the configured A02 runtime, Prompt registry, Provider and parser with report-only INTERPRET_CHARACTER_PROFILE. It is an explicit user model call, not an automatic background learner. CP-010 v1 contains user input and server-resolved related identities only. The output uses the same sparse body schema, forbids server fields and requires empty proposed_changes/memory_proposals. Runtime execute_report is shared with internal smoke and cannot execute Writer/approval tasks.

Preflight verifies user/scope/Lock/version, releases DB locks during network IO, then ordinary draft creation rechecks the expected version. Raw source_text stays with the resulting Draft. The synchronous endpoint has no fabricated Chapter/Workflow, separate Agent or queue; it returns a Draft or a real error. Downstream chapter production still uses the existing persisted ContextPackage/PromptLineage chain. User approval is a separate command.

## Context, versions and freshness

Optional P0 approved-character-behavior-profiles is retained as input when relevant; P0 is not a hard behavioral gate. It selects only APPROVED records at A3, with exact record ID, profile logical ID, character ID, version, hash and enclosing modifier version. It reuses SourceType.EXTENSION, with a dedicated selector and payload kind=CHARACTER_BEHAVIOR_PROFILE, preserving historical output Schema enums/hashes. Identity and Profile sources have distinct logical IDs. Relevance uses task/Brief/selected-concept content for A03, or exact approved Plan and target Draft for downstream tasks. Explicit POV is included; all-project profile dumps are forbidden. Metadata field names and UUIDs cannot manufacture character relevance. Only modifiers whose counterpart is involved enter the payload.

SourceVersions record selected SourceRef fields, including source_type/source_id/logical_id/version. ContextPackage payloads bind profile ID/version/hash; source_snapshots fingerprint both populated and empty selector bindings. Profile approval changes invalidate affected queued/inflight tasks before model use and before result persistence. Merely saving a new Draft does not change selected approval. A new explicitly requested task binds the then-approved profile snapshot; a behavior tendency update alone does not invalidate an already approved Plan or require forced replanning. Historical Context profiles without the selector retain their original inputs.

| Task | New Context version | New template |
|---|---|---|
| Exploration | CP-004E v2 | explore-chapter-concepts v2 |
| Planning without / with Exploration | CP-004 v8 / v9 | plan-chapter v8 / v9 |
| Plan Review | CP-004R v4 | review-chapter-plan v5 |
| Writing | CP-005 v7 | write-chapter v5 |
| Compliance / Narrative Review | CP-006 v4 | review-chapter-compliance v2 / review-chapter-narrative v3 |
| Revision Planning / Execution | CP-007 v8 | plan-chapter-revision v7 / revise-chapter v8 |
| Human Feedback interpretation | CP-008 v2 | interpret-chapter-feedback v3 |
| Explicit Profile interpretation | CP-010 v1 | interpret-character-profile v1 |

Historical JSON/Prompt files are preserved. Template selection follows exact Context profile version; estimates use current conservative templates. Writer lineage comes from selected ContextPackage, without new citation fields in WritingResult. Fidelity output and source preservation rules stay unchanged.

## Planning and NOVEL-013

A03 uses tendencies to shape causal choices, pressure, conflict response and possible progression, rather than renaming the same mechanism around personality labels. No new scoring, count, selection policy, creativity enum, retry or gate is added. Profile guidance is never copied to authoritative_constraints/constraints[] or promoted from Review recommendations.

## Writing, Review, Revision and feedback

A04 uses attention, desires, knowledge, avoided admissions, defense and the specific interlocutor to differentiate response and inner experience. It preserves STYLE-002 narration and does not mandate slang, catchphrases, interruptions, silence or misunderstanding. It executes approved outcomes while allowing motivated deviations from tendencies.

A05 uses existing voice/character diagnoses and grounded evidence; ordinary tendency differences are not automatic P0/OOC failures. A06 fixes local voice problems in the current Draft with source fidelity and existing zones/budgets; it cannot reconstruct scenes, Plan, relationships or profiles. A02 feedback distinguishes local 'this line does not sound like A' from a permanent character redefinition; the latter uses the existing explicit preference/profile-change route and never auto-persists.

## UI and Debug

Workspace sidebar opens a small Characters panel. Choose/create an identity, read name/aliases and current committed CHARACTER_STATE using the existing Memory API, inspect current/approved profile versions, edit six common dimensions, or expand advanced fields and sparse counterpart modifiers. State loading/errors are independent from profile editing. Save creates a new Draft; approval is explicit. Natural-language organization is labeled as a model call. Failed operations retain input and allow manual correction/retry; profile loading failures disable commands. Debug filters Character Context and exposes source version/authority, included/excluded items and lineage through the existing panels.

## Migration and rollback

0019 adds one table and nullable manual identity provenance, preserving legacy committed identities. Fresh/test schemas support upgrade → downgrade one → upgrade and Alembic check. Downgrade refuses if manual identities with batch_id=null exist because the previous schema cannot represent them without inventing a commit batch. Export/migrate these identities explicitly before operational rollback; never delete user data to make downgrade appear successful.

## Evaluation

Engineering tests verify contracts, immutability, approval separation, relevant retrieval, stale results, authority boundaries and old-project compatibility. evals/character-depth contains sparse fixtures and human protocols for same-pressure A/B, interlocutor B/C, motivated exceptions, knowledge isolation and an old no-profile flow, plus Review/Revision/Feedback checks. No exact prose string asserts quality. Real Provider and human behavior acceptance are NOT_RUN/PENDING until explicit execution; see the [implementation report](../reports/NOVEL-014-character-depth-voice.md).
