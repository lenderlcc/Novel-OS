# NOVEL-003 — Chapter Workflow Engine

**Priority:** P0  
**Depends On:** NOVEL-001/002

## Goal

实现确定性 Chapter Production State Machine，先使用 Fake Agent / Fake Event，不接真实 LLM。

## States

```text
C00_CREATED
C01_REQUIREMENT_INTAKE
C02_CONTEXT_ASSEMBLY
C03_REQUIREMENT_READY
C04_CHAPTER_PLANNING
C05_PLAN_REVIEW
C06_PLAN_APPROVAL
C07_WRITING
C08_DETERMINISTIC_CHECK
C09_INTERNAL_REVIEW
C10_REVISION
C11_INTERNAL_PASS
C12_USER_REVIEW
C13_USER_FEEDBACK_DIAGNOSIS
C14_MEMORY_PREPARATION
C15_MEMORY_COMMIT
C16_COMPLETED
C90_BLOCKED
C91_FAILED
C92_CANCELLED
```

## Must Implement

- WorkflowDefinition YAML
- Definition loader / validator
- WorkflowInstance
- WorkflowTransition
- WorkflowEvent
- GuardRegistry
- HumanGate
- Pause / Resume
- Block / Resume
- Cancel
- revision_count / retry_count
- state_version optimistic lock
- event_id idempotency
- transition audit
- Fake executor

## Critical Rules

- No direct `set_state`
- Agent cannot approve HumanGate
- Guard reads real Domain state, not event claims
- Plan not approved → cannot enter Writing
- Quality failure → Revision, not technical retry
- duplicate event no duplicate side effect
- completed workflow terminal

## Acceptance

必须跑通：
- Happy Path
- Plan Review Fail
- Internal Review Fail
- User Reject
- Block/Resume
- Pause/Resume
- Duplicate Event
- Stale state version
- stale approval version
- illegal skip
