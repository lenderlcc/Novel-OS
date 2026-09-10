# NOVEL-010 — Revision Agent + Regression Review

**Priority:** P0  
**Depends On:** NOVEL-001~009

## Goal

```text
Review FAIL
→ RevisionContract
→ Revision Agent
→ ChapterVersion vNext
→ Targeted Review
→ Preservation Review
→ Regression Review
→ Full Review
```

## RevisionContract

强制包含：
- MUST_KEEP
- MUST_CHANGE
- MUST_NOT_CHANGE
- allowed_scope
- forbidden_scope
- approved_plan_ref
- locked_decisions
- issue refs
- user feedback refs

## Revision Types

- LOCAL_REVISION
- SCENE_REVISION
- STRUCTURAL_REVISION
- DIALOGUE_REVISION
- PACING_REVISION
- NATURALNESS_REVISION
- MIXED_REVISION

C3/C4 不允许普通 Revision。

## Skills

- Targeted Revision
- Preservation
- Pacing Revision
- Dialogue Revision
- Naturalness Revision

## Critical Rules

- Revision ≠ Write Again
- local problem → local change
- Diff 由 deterministic service 计算
- Scope violation blocks
- MUST_NOT_CHANGE = hard boundary
- Revision Agent cannot self-confirm issue fixed
- Issue closes only after Review verification
- every revision creates new version
- approved_version unchanged
- repeated failure → blocked/escalation, not infinite rewrite

## Metrics

- issue resolution rate
- regression rate
- preservation failure rate
- modified text ratio
- revision count
