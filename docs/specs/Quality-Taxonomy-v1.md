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
