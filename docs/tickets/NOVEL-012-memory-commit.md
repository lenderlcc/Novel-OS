# NOVEL-012 — Memory Commit + Canon State Update

**Priority:** P0  
**Depends On:** NOVEL-001~011

## Goal

```text
User APPROVED ChapterVersion
→ Memory Agent
→ MemoryChangeSet
→ Validation
→ Conflict Detection
→ Authority Check
→ Atomic Commit
→ Canon Revision +1
→ Chapter COMPLETED
→ Next Chapter reads updated Canon
```

## Core Principle

```text
Draft ≠ Canon
Internal PASS ≠ Canon
User APPROVED ≠ Commit Complete
User APPROVED + Memory Commit SUCCESS = Canonical State
```

## First Canon Domains

- Character
- CharacterState
- CharacterKnowledge
- Event
- CanonFact v0.1
- Plotline
- ChapterSummary (Derived)

## Memory Extraction

提取：
- events
- character state changes
- character knowledge changes
- important facts
- plotline changes
- chapter summary

不提取：
- narrator metaphor
- unconfirmed hint
- character guess as global fact
- future plan as executed event
- every tiny action / emotion

## Critical Rules

- Approved Chapter Content is source
- Plan not executed → not Canon
- Character belief ≠ Canon fact
- important state change needs cause/evidence
- low-confidence major change blocks
- Memory Agent proposes, Service commits
- all Canon changes have provenance
- commit is atomic
- same source version commit idempotent
- stale canon revision blocks old changeset

## Canon Revision

Project maintains monotonic `canon_revision`.

MemoryChangeSet records `base_canon_revision`.

Successful commit increments revision in same transaction.

## Next Chapter Proof

Chapter 1 Commit 后，Chapter 2 Context 必须读取：
- latest CharacterState
- CharacterKnowledge
- recent Event
- Plotline state

Chapter 1 unapproved draft must never leak.

## Acceptance

必须跑：
- Full Chapter E2E
- Next Chapter Context E2E
- Draft Isolation E2E
- Memory Conflict E2E
- Atomic rollback test
- Idempotency test
- Canon revision conflict test
