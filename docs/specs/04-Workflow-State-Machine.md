# Novel OS Workflow State Machine v1.0

**Status:** Baseline

## 1. Principle

Workflow Engine 负责状态正确性；Agent 负责任务执行。

Agent 不能直接设置 next_state，只能产生结果 / Event。

```text
Current State
+
Event
+
Guard
→
Next State
```

## 2. Workflow Status

- CREATED
- RUNNING
- WAITING_AGENT
- WAITING_HUMAN
- PAUSED
- BLOCKED
- COMPLETED
- FAILED
- CANCELLED

`current_state` 与 `status` 分离。

## 3. Event Model

User:
- USER_SUBMITTED
- USER_APPROVED
- USER_REJECTED
- USER_MODIFIED
- USER_CANCELLED

Agent:
- AGENT_SUCCEEDED
- AGENT_PARTIAL
- AGENT_BLOCKED
- AGENT_FAILED
- AGENT_NEEDS_HUMAN

Quality:
- REVIEW_PASSED
- REVIEW_WARNED
- REVIEW_FAILED
- REGRESSION_PASSED
- REGRESSION_FAILED

Memory:
- CONTEXT_READY
- MEMORY_CHANGESET_READY
- MEMORY_COMMITTED
- MEMORY_CONFLICT

System:
- RETRY_EXHAUSTED
- STATE_CONFLICT
- TIMEOUT
- STALE_DETECTED

## 4. Project Initialization States

```text
P00_CREATED
P01_INTAKE
P02_REQUIREMENT_NORMALIZATION
P03_CREATIVE_EXPLORATION
P04_CORE_PREMISE
P05_WORLD_PLANNING
P06_CHARACTER_PLANNING
P07_STORY_ARCHITECTURE
P08_SUPPORTING_STRUCTURE
P09_VOLUME_ARC_PLANNING
P10_PROJECT_REVIEW
P11_REVISION
P12_PROJECT_APPROVAL
P13_CANON_PREPARATION
P14_CANON_COMMIT
P15_READY
P90_BLOCKED
P91_FAILED
P92_CANCELLED
```

## 5. Chapter Production States

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

Happy Path：

```text
C00 → C01 → C02 → C03 → C04 → C05 → C06
→ C07 → C08 → C09 → C11 → C12 → C14 → C15 → C16
```

## 6. Core Transitions

| From | Event | To |
|---|---|---|
| C00 | USER_SUBMITTED | C01 |
| C01 | AGENT_SUCCEEDED | C02 |
| C02 | CONTEXT_READY | C03 |
| C03 | AGENT_SUCCEEDED | C04 |
| C04 | PLAN_READY | C05 |
| C05 | PLAN_REVIEW_PASSED | C06 |
| C05 | PLAN_REVIEW_FAILED | C04 |
| C06 | USER_APPROVED | C07 |
| C06 | USER_REJECTED | C04 |
| C07 | DRAFT_READY | C08 |
| C08 | DETERMINISTIC_CHECK_PASSED | C09 |
| C09 | REVIEW_FAILED | C10 |
| C09 | REVIEW_PASSED/WARNED | C11 |
| C10 | REVISION_READY | C08 |
| C11 | READY_FOR_USER | C12 |
| C12 | USER_APPROVED | C14 |
| C12 | USER_REJECTED | C13 |
| C13 | LOCAL_CHANGE | C10 |
| C13 | CHAPTER_REPLAN_REQUIRED | C04 |
| C14 | MEMORY_CHANGESET_READY | C15 |
| C15 | MEMORY_COMMITTED | C16 |

## 7. Feedback Workflow

```text
F00_CREATED
F01_FEEDBACK_INTAKE
F02_INTERPRETATION
F03_CLASSIFICATION
F04_IMPACT_ANALYSIS
F05_CHANGE_PLAN
F06_CHANGE_APPROVAL
F07_EXECUTION
F08_TARGETED_REVIEW
F09_REGRESSION_REVIEW
F10_USER_ACCEPTANCE
F11_COMMIT_PREPARATION
F12_COMMIT
F13_INVALIDATION
F14_REPLANNING
F15_COMPLETED
F90_BLOCKED
F91_FAILED
F92_CANCELLED
```

## 8. Human Gate

状态：
- HG_CREATED
- HG_WAITING
- HG_APPROVED
- HG_REJECTED
- HG_MODIFIED
- HG_CANCELLED
- HG_STALE

动作：
- APPROVE
- REJECT
- MODIFY
- REQUEST_ALTERNATIVE
- LOCK
- UNLOCK
- CANCEL

Human Approval 必须绑定具体 Artifact Version。

## 9. Retry vs Revision

Technical Retry：
- MODEL_FAILURE
- TOOL_TIMEOUT
- FORMAT_ERROR

Quality Fail：
- 进入 Revision，不叫 Retry。

Block：
- Missing Human Decision
- Canon Conflict
- Locked Conflict
- Missing P0 Context

Failed：
- Persistent Tool Failure
- Corrupted State
- Unsupported Schema

## 10. Concurrency & Idempotency

WorkflowInstance 使用 `state_version`。

Transition 必须声明 expected version。

所有有副作用 Event 使用 `event_id` 幂等。

重复 Event 不得重复推进状态。

## 11. Stale Rules

上游变化时：
- Canon Change → Future Plans STALE
- Requirement Change → Plan / Draft / Review STALE
- Approved Plan Change → Existing Draft STALE

STALE 不等于删除；需 Revalidate 或 Supersede。

## 12. Ownership

| State Type | Owner |
|---|---|
| Workflow State | Workflow Engine |
| AgentTask Status | Task Manager |
| Artifact Status | Artifact Service |
| Canon Status | Memory Service |
| HumanGate | Approval Service |
| User Decision | User |
| Quality Verdict | Quality Engine |

## 13. Principles

1. State Is Explicit
2. Agents Cannot Change State Directly
3. Transitions Are Guarded
4. Human Approval Is Version Bound
5. Retry ≠ Revision
6. Blocked ≠ Failed
7. Workflow Is Versioned
8. No Silent Transition
9. Stale Propagates
10. Commit Is Explicit
11. Idempotency Required
12. Code Owns Workflow Truth
