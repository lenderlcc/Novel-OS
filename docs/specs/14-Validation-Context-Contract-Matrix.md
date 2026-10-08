# VALIDATION-001 Context Contract Matrix

This matrix records the implemented, stable Context Profiles at repository baseline
`38de644b835ae06eed82b39a9959a11f5b0d6d9b`. It adds no selectors, authority levels,
or product contract semantics. “Must Include” means the existing selector is required
for a READY package; conditional sources remain subject to relevance, exact binding,
authority, freshness, and the existing token budget.

Recorded / Mock evidence verifies engineering integration. Real AI Behavior = NOT RUN.

| Task | Implemented profile | Must Include | Conditional | Must Exclude |
| --- | --- | --- | --- | --- |
| EXPLORE (`EXPLORE_CHAPTER_CONCEPTS`, A03) | CP-004E v2 | Task input; target chapter; exact workflow CreativeBrief with exploration policy | Effective Requirements/Decisions; explicit locked Plan/Requirement/Decision dependencies; approved ProjectWritingProfile; relevant committed current State and owner-labeled Knowledge; relevant character identity; exact approved BehaviorProfile with involved relationship pairs; up to 3 compact recent approved Plans and up to 3 committed derived final summaries | Unapproved/superseded BehaviorProfiles; unrelated characters/pairs; uncommitted Memory; full historical chapter prose; other or rejected candidates; future information lacking an explicit required dependency; knowledge attributed to the wrong owner |
| PLAN (`PLAN_CHAPTER`, A03) | CP-004 v9 | Task input; target chapter; exact workflow CreativeBrief with policy | Selected concept projection from the workflow's exact CreativeExploration when exploration ran, A7 only; effective Requirements/Decisions; explicit locked dependencies; previous iteration Plan and Plan Review repair targets; approved WritingProfile; relevant State/owner-labeled Knowledge/identity; exact approved BehaviorProfiles and involved relationship pairs; compact recent approved Plans and derived final summaries | Rejected concepts, rejection/selection commentary capable of carrying rejected content; unapproved profile versions; unrelated profiles/pairs; uncommitted Memory; unrelated or future-only history; treating a selected concept as an approved Plan or Canon |
| WRITE (`WRITE_CHAPTER`, A04) | CP-005 v7 | Task input; target chapter; exact workflow-bound approved Plan | Effective approved/locked Requirements and Decisions; explicit approved locked Plan/Requirement/Decision dependencies; approved WritingProfile; exact approved relevant BehaviorProfiles and involved pairs; relevant identities; current committed POV State/relationship records and POV Knowledge, with Canon facts linked through that POV's KNOWS records | All CreativeExploration candidate bodies (including selected candidate); unapproved/superseded or unrelated BehaviorProfiles; unrelated modifiers; another character's Knowledge or unlinked global Canon fact; superseded State; uncommitted Memory; full previous chapter prose, including locked prose dependencies; unrequired future information |
| PLAN_REVIEW (`REVIEW_CHAPTER_PLAN`, A05) | CP-004R v4 | Task input; target chapter; exact CreativeBrief; exact workflow target Plan proposal | Effective Requirements/Decisions; project metadata; explicit dependencies; approved WritingProfile; exact approved relevant BehaviorProfiles/pairs and character identities | Unapproved/superseded profiles; unrelated profiles/pairs; latest Plan replacing the exact proposal under review; full candidate/rejected content; private committed Knowledge; all future Knowledge (profile policy NONE); Review becoming story authority or writing profiles |
| QUALITY_REVIEW (`REVIEW_CHAPTER_COMPLIANCE` / `REVIEW_CHAPTER_NARRATIVE`, A05) | CP-006 v4 | Task input; target chapter; exact target Draft with indexed paragraphs; exact approved Plan; exact workflow CreativeBrief | Effective Requirements/Decisions; explicit dependencies; approved WritingProfile; bounded recent approved chapters; exact approved relevant BehaviorProfiles/pairs and identities | Current/latest Draft replacing the bound target; unapproved/unrelated profiles and pairs; candidate bodies; private committed Knowledge; unrequired future information; Review mutating Profile, Canon, or approved Plan; assuming a missing BehaviorProfile exists |
| REVISION (`PLAN_CHAPTER_REVISION` / `REVISE_CHAPTER` / `VALIDATE_REVISION_FIDELITY`, A06 / fidelity A05) | CP-007 v8 | Task input; target chapter; exact source Draft; exact approved Plan; exact approved WritingProfile; exact CreativeBrief; exact Revision contract with preservation constraints | Effective Requirements/Decisions and explicit dependencies; bounded recent approved chapters; source Quality Review diagnosis; current request Revision Plan/candidate; source Human Feedback and interpretation; exact approved relevant BehaviorProfiles/pairs and identities | Rejected creative concepts; unapproved/unrelated profiles/pairs; latest Draft replacing the bound source; private committed Knowledge; unrequired future information; automatic Profile/Preference learning; changing preserved prose/scene/relationship elements without the allowed revision scope |
| FEEDBACK_INTERPRET (`INTERPRET_CHAPTER_FEEDBACK`, A02) | CP-008 v2 | Task input; target chapter; exact source Draft; exact approved Plan; exact approved WritingProfile; exact CreativeBrief; current Draft Human Feedback | Effective Requirements/Decisions and explicit dependencies; bounded recent approved chapters; optional source Review diagnosis; relevant approved BehaviorProfiles/pairs and identities (including explicit POV identity from exact Plan generation) | Rejected creative concepts; unapproved/unrelated profiles/pairs; private committed Knowledge; unrequired future information; automatically creating a BehaviorProfile version, ProjectWritingProfile version, or persistent preference; treating Review diagnosis as story authority |
| MEMORY_EXTRACT (`EXTRACT_CHAPTER_MEMORY`, A07) | CP-009 v1 | Task input; target chapter; exact finalized/accepted source Draft; exact approved Plan; exact CreativeBrief | Effective Requirements/Decisions and explicit dependencies; relevant previously committed Memory and identities for candidate reconciliation | Every CreativeExploration candidate body; any unaccepted Draft as extraction source; BehaviorProfiles/relationship modifiers and WritingProfile learning inputs; future information lacking a required dependency; automatic Canon commit or automatic Profile mutation; proposal facts entering effective Context before explicit confirmation |

## Shared implemented boundaries

- A0–A7 and the seven-agent roster remain unchanged. A7 proposals, Plan Review,
  Quality Review, Revision evidence, and selected concepts cannot override stronger
  authority. Plans are marked as Plans; behavior tendencies remain separate from
  knowledge-owner records. Feedback remains scoped to its source Draft.
- BehaviorProfile Context items use `source_type=EXTENSION`, the profile's distinct
  `logical_id`, the approved immutable record `source_id` and `source_version`,
  `authority_level=A3_CANON`, the approved profile hash, a nonempty `selected_reason`,
  and provenance `character_behavior_profile` / `version_policy:APPROVED`.
- Relevant identities come from story values and the exact bound approved Plan,
  Brief/selected concept, source Draft when applicable, and explicit Plan POV.
  Serialization keys, UUID metadata, candidate IDs, and source references do not
  authorize an unrelated profile. Existing normalized Latin/alnum names and aliases (ASCII and the supported
  U00C0–U024F Latin letter ranges) match within complete Latin/alnum/underscore
  boundaries, with their historical space/punctuation-equivalent forms and existing
  NFKC/casefold normalization. Internal newlines cannot join separate story leaves.
  CJK keeps its existing normalized lookup. Stored aliases lack original whitespace:
  AB / A B and RedFox / Red Fox are equivalent forms. This lexical lookup does not
  establish NLP identity disambiguation; exact bindings establish knowledge ownership. A→B modifiers are projected only when B is involved.
- `current v2 DRAFT` does not replace `approved v1`. Approving v2 changes source
  fingerprints/bindings: an already pending bound task fails its pre-model
  freshness check with CONTEXT_STALE, Task FAILED and Workflow C90_BLOCKED; a newly
  scheduled task may use v2. Context freshness has STALE; the Task status enum does not. Historical packages retain their original immutable data.
- Planning/Exploration may read relevant owner-labeled committed Knowledge for
  continuity planning. This does not label the information as another character's
  knowledge. Writing has the narrower exact POV firewall and obtains linked Canon
  facts only through that POV's `KNOWS` records. Profile personality grants no access.
- Missing optional character profiles leave Requirement/Planning/Writing/Review
  available for historical projects. Revision and Feedback retain their already
  required WritingProfile contract; this is separate from optional BehaviorProfiles.
- Token evidence uses existing `TokenBudgetService` and `Utf8TokenEstimator`, whose
  conservative estimate counts UTF-8 bytes. It is neither provider billing usage nor
  a prose/voice/creativity score. Required inputs fail closed when the budget is exceeded.

## Implementation and verification evidence

Selector definitions: `backend/novel_os/context/profiles/CP-004E.v2.json`,
`CP-004.v9.json`, `CP-005.v7.json`, `CP-004R.v4.json`, `CP-006.v4.json`,
`CP-007.v8.json`, `CP-008.v2.json`, and `CP-009.v1.json`.

Binding/retrieval/filtering: `services/context.py`, `services/character_profile_context.py`,
`services/canon_context.py`, `repositories/memory.py`, `services/exploration_context.py`, `services/memory_query.py`,
`services/revision_context.py`, `services/feedback_context.py`, `context/policies.py`,
and `context/engine.py` under `backend/novel_os`.

Freshly executed local evidence for VALIDATION-001 is recorded under ignored
`backend/.runtime/validation001/`: `context-focused.xml`, `context-new-focused.xml`,
`context-authority.md`, `context-authority-evidence.json`, and
`context-overload-samples.json`. The final evidence manifest records test outcomes,
source hashes, package hashes, exact source metadata, and the zero-real-call guard.
No prior report's PASS is used as this run's verification result.

Focused suites: `tests/context/test_context.py`,
`tests/context/test_character_profile_context.py`,
`tests/core/quality/test_checkpoint_phase2.py`,
`tests/core/quality/test_character_profile_pov_regressions.py`,
`tests/core/quality/test_memory_context_isolation.py`,
`tests/core/workflow/test_exploration_context.py`,
`tests/core/workflow/test_creative_exploration.py`,
`tests/core/writing/test_context_and_prompt.py`, and the uncommitted local
`tests/core/quality/test_validation001_context_authority.py` under `backend`.
