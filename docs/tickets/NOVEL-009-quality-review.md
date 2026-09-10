# NOVEL-009 — Quality Engine + Full Chapter Review

**Priority:** P0  
**Depends On:** NOVEL-001~008

## Goal

```text
Draft
→ Deterministic Validation
→ CP-006
→ Review Agent
→ ReviewReport
→ Quality Aggregator
→ PASS / WARN / FAIL
```

## Architecture

```text
QualityEngine
├── Deterministic Evaluators
├── Review Agent
├── Quality Aggregator
└── QualityProfile
```

## Hard Gates

- MUST violation
- Forbidden violation
- Locked violation
- Major Plan violation
- Critical OOC
- Character Knowledge Leak
- Major Continuity conflict
- Major Timeline conflict
- Major Logic break

Hard failure cannot be averaged away by high prose score.

## Review Dimensions

- Requirement
- Plan Compliance
- OOC / Character
- Character Knowledge
- Continuity
- Timeline
- Logic
- Pacing
- Dialogue
- Style
- Repetition
- AI Writing Smell

## AI Writing Smell v1

- AS-01 Over Explanation
- AS-02 Emotion Labeling
- AS-03 Uniform Rhythm
- AS-04 Template Transition
- AS-05 Dialogue Functionalization
- AS-06 Character Voice Collapse
- AS-07 Excessive Closure
- AS-12 Over-signposting

不输出“AI 概率”。

## ReviewIssue Requirements

必须包含：
- location
- evidence
- diagnosis
- impact
- recommendation
- severity
- auto_fixable
- requires_human

## Multi-Pass

同一 Review Agent，多轮：
1. Requirement / Plan / Canon / Knowledge
2. Story / Character / Logic / Pacing / Dialogue
3. Style / Repetition / Naturalness / AI Smell

不是拆 10 个 Agent。

## Acceptance

必须有 False Positive cases，允许 Clean Draft PASS，不能为了“显得有用”硬找问题。
