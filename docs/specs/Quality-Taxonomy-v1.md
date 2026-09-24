# Quality Taxonomy v1

Codes identify *supported findings*, not a checklist that each Draft must fail. Every finding has: code, category, severity, title, description, short exact paragraph evidence + reason, impact, revision direction, confidence and exact selected source references. No numeric prose score.

P0 = confirmed serious authority/explicit-boundary conflict, FAIL. P1 = material problem; explicit `requires_revision` distinguishes FAIL from warnings. P2 = local weakness, warnings. P3 = optional improvement, warnings. P2/P3 cannot require revision. Subjective NARRATIVE/CREATIVE/AUDIENCE issues and A5 POV preferences cannot be P0. Confirmed LOCKED_CONFLICT/MAJOR_DIRECTION_VIOLATION must be P0; confirmed MISSING_MUST/FORBIDDEN_VIOLATION/CANON_CONFLICT/CHARACTER_KNOWLEDGE_LEAK must be P0/P1 requiring revision. This validates the *reported semantic claim*; it does not detect these claims using keywords.

| Code | Category / severity | Definition and required evidence | Non-trigger / boundary |
|---|---|---|---|
| MISSING_MUST | COMPLIANCE P0/P1 | A specific Brief MUST is absent; cite `must.<id>`, relevant Draft scene/end and explain absence. | SHOULD, preference, reviewer wish or mechanical omission of the exact wording. |
| FORBIDDEN_VIOLATION | COMPLIANCE P0/P1 | Draft violates a specific `forbidden.<id>` boundary; cite both. | Depiction of a topic is not necessarily committing the forbidden outcome. |
| CANON_CONFLICT | COMPLIANCE P0/P1 | Explicit contradiction with supplied approved/locked canon evidence; quote Draft and exact authoritative source. | No canon source, mere surprise, or an AI inference about unseen world rules. |
| LOCKED_CONFLICT | COMPLIANCE P0 | Contradiction with an actual locked A1 source and its version. | Unlocked inference, suggestion or A5 preference. |
| MAJOR_DIRECTION_VIOLATION | COMPLIANCE P0 | Changes the approved Plan's main direction, result or governing choice; cite approved Plan. | Local creative execution that preserves approved direction. |
| NARRATIVE_POV_MISMATCH | COMPLIANCE P1/P2 | Semantic narration conflicts with explicit approved A5 `narrative_perspective`; cite narrative passage and field. | First-person words in dialogue; absent/unspecified POV; historical profile with no POV. |
| CHARACTER_KNOWLEDGE_LEAK | COMPLIANCE by impact | Character uses information inconsistent with supplied character-specific knowledge evidence; cite character ID/context. | Global Canon alone; speculation/belief; missing character knowledge sources. |
| LOW_IMMERSION | NARRATIVE P1–P3 | Reader watches explanation rather than experiencing consequential action/perception through characters. | Deliberate summary or distance serving the scene. |
| WEAK_POV_ANCHOR | NARRATIVE P1–P3 | Attention/perception/reaction lacks a coherent experience center, regardless of grammatical person. | Intentional supported omniscient or distant narration. |
| UNSELECTIVE_DETAIL | NARRATIVE P1–P3 | Transitional actions receive the same attention as important turns; quote specific contrasted passages. | Detailed process that creates tension or meaningful character choices. |
| MISALLOCATED_NARRATIVE_DETAIL | NARRATIVE P1–P3 | Minor physical actions are precise while crucial relationship, cost, conflict or judgment remains abstract. | Purposeful restraint or detail carrying that crucial meaning indirectly. |
| OVER_EXPLAINED_REASONING | NARRATIVE P1–P3 | Explanatory reasoning repeatedly replaces dramatized cause/choice. | Necessary concise inference or a character's distinctive reasoning voice. |
| OVER_EXPLAINED_EMOTIONAL_MEANING | NARRATIVE P1–P3 | Text tells the emotional meaning already conveyed by action/interaction. | A new realization that changes character understanding. |
| FUNCTIONAL_DIALOGUE | NARRATIVE P1–P3 | Lines primarily service information/tasks and lose plausible personal motive. | Brief practical dialogue appropriate to the situation. |
| OVER_STRUCTURED_DIALOGUE | NARRATIVE P1–P3 | Conversation reads as orderly bullet-point procedure or argument outline. | A formal setting or purposeful procedural exchange. |
| WEAK_CHARACTER_VOICE | NARRATIVE P1–P3 | Supplied dialogue lacks differentiation supported by the immediate characters/context. | Unsupported OOC claims about missing character memory. |
| CHARACTERS_AS_ARGUMENTS | NARRATIVE P1–P3 | People become vehicles for neatly opposed positions rather than embodied motives/costs. | A genuine disagreement expressed through character-specific experience. |
| OVER_SYMMETRICAL_CONFLICT | NARRATIVE P1–P3 | Artificially balanced turns, concessions or arguments flatten specific tensions. | Two reasonable positions or balanced conflict by itself. |
| ABSTRACT_STAKES | NARRATIVE P1–P3 | Consequences remain conceptual and the reader cannot feel what a concrete choice risks. | Intentional uncertainty with specific observable stakes. |
| EXCESSIVE_CLOSURE | NARRATIVE P1–P3 | Text repeatedly settles meaning/relationship beyond the scene's needed resolution. | A deserved local resolution; not every chapter needs a cliffhanger. |
| REQUIREMENT_VISIBILITY_BIAS | NARRATIVE P1–P3 | Prose visibly ticks brief items or explains compliance instead of allowing events to carry them. | Simply satisfying user requirements. |
| SAFE_GENERIC_CREATIVE_CHOICE | CREATIVE P2/P3 | Repeated low-risk scene/conflict solutions reduce creative specificity; cite at least two earlier approved chapter sources and current evidence. | One quiet indoor scene, one ordinary device, or insufficient recent history. |
| LOW_CREATIVE_NOVELTY | CREATIVE P2/P3 | Within allowed local freedom, choices lack specificity or fresh causal use; explain concrete missed potential. | Demanding a new main direction, canon, ability or major character. |
| AUDIENCE_STYLE_MISMATCH | AUDIENCE P1–P3 | Reading experience conflicts with exact approved A5 audience/style preferences; cite populated field and Draft effect. | Hardcoded web-fiction rules; unspecified audience; newest unapproved Profile. |

Confidence expresses certainty in the particular finding, not literary merit. Direct contradictions support higher confidence than subjective experience judgments. Do not assert certainty where relevant context is absent. Strengths require evidence and preservation directions. Revision priorities are directions for human consideration, never edits or automatically promoted requirements.

## NOVEL-009A — Dialogue and character diagnosis

These are semantic lenses, never punctuation/length/turn-count detectors or mandatory findings. Prefer a few well-supported root causes (often 2–4 when needed); a good scene can have none. LOW_IMMERSION need not repeat the effects already explained by a root issue. Character specificity asks what makes this interaction particular to these people; it is supporting reasoning in existing explanation/evidence/impact fields, not a new taxonomy code or a demand to invent relationship history.

### OVER_STRUCTURED_DIALOGUE

- **Definition:** Human interaction is compressed into an unusually complete, efficient argument protocol, even when the lines express emotion. Logical clarity alone is not the defect.
- **Typical Evidence:** Several contextual excerpts show proposition → precise objection → clarification → exact follow-up → articulated response; nearly every line advances the same decision while individual reactions and interpretation have little effect. Explain the reading consequence and any counter-evidence.
- **Non-trigger:** Clear reasoning, formal debate, purposeful procedure or a focused scene. Missing silence, interruption, evasion or misunderstanding is not sufficient; these are possible signals, not requirements.
- **Typical Severity:** P2 for local loss of natural interaction; P1 when central scene impact is materially weakened. `requires_revision` follows impact, so the code never implies automatic FAIL or P0.
- **Relationship to other Issue Codes:** FUNCTIONAL_DIALOGUE concerns information/action delivery crowding out personal motives; this code concerns the pattern of interaction. Both may exist with distinct evidence and effects, but do not duplicate one diagnosis. If the same protocol flattens voice, describe that impact under this root rather than manufacturing a second issue.

### CHARACTERS_AS_ARGUMENTS

- **Definition:** Participants primarily represent positions, solutions or abstract values; their behavior differs mainly by which side they support rather than by embodied motives, personality or relationship.
- **Typical Evidence:** The actual dialogue/actions repeatedly serve each position, while supplied pride, fear, experience, bias or relationship-specific reactions make little difference. The interchangeability of participants is a supporting lens, grounded in the present text rather than invented backstory.
- **Non-trigger:** Disagreement, one clear conflict, two reasonable positions, limited background information, or purposeful allegory supported by the project's context. A role's position may emerge naturally from personal experience.
- **Typical Severity:** P2 for localized thinness; P1 when a central relationship/choice loses its emotional meaning. No P0 and no fixed failure verdict.
- **Relationship to other Issue Codes:** OVER_SYMMETRICAL_CONFLICT concerns artificial balancing of turns/concessions; WEAK_CHARACTER_VOICE concerns expression and response habits. They can share symptoms; prioritize the supported root cause and explain the other effects without duplicating quotes.

### WEAK_CHARACTER_VOICE

- **Definition:** Speakers lack meaningful differences in rhythm, syntax, avoidance, emotional expression, judgments and reactions within the available scene/context.
- **Typical Evidence:** Differently positioned speakers share polished summaries, precise questions/rebuttals and equally complete self-explanation. Contrast actual excerpts and responses; dialogue quantity alone is insufficient. Weak relationship-specific detail can support the explanation.
- **Non-trigger:** Shared formal/literary register, restrained speech, equal line lengths, absence of slang/catchphrases, or a missing character-memory record. Do not require colloquial speech, filler, short sentences or unsupported out-of-character claims.
- **Typical Severity:** P2 for local interchangeability; P1 for a material loss of distinction central to the scene. Severity depends on effect.
- **Relationship to other Issue Codes:** Voice is not identical to opposing viewpoints. If a procedural exchange is the cause of homogenized expression, OVER_STRUCTURED_DIALOGUE can carry the diagnosis with voice loss in its impact. Use separate issues only when independently evidenced.

## Evidenced audience fit

Narrative and Audience remain separate dimensions. A narrative warning alone never changes the Audience verdict. When a supported problem directly conflicts with the exact approved A5 Profile, report one consolidated AUDIENCE_STYLE_MISMATCH and its specific preference conflict. New narrative v2 outputs must record `audience_evidence[]`: `profile_field`, exact `profile_ref`, `expected` (the actual string/list value), `observed`, and `reason`. These references must match the audience issue and top-level source references; the selected approved version/value is validated, never taken from current Draft Profile or another project.

Audience PASS has no mismatch evidence. Non-PASS Audience requires both its issue and populated mismatch evidence. The existing P0/P1/P2/P3 verdict function is unchanged. Subjective Profile mismatch remains A5 and cannot become a hard compliance conflict. An absent relevant Profile field does not justify inference. The narrative prompt is `review-chapter-narrative.v2`; its prior v1, shared quality-evidence v1/v2 and Writer/Planning/Requirement prompts remain unchanged.
