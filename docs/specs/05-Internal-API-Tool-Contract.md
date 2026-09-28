# Novel OS Internal API & Tool Contract v1.0

**Status:** Baseline

## 1. Core Principle

三类执行主体：

```text
USER
LLM AGENT
DETERMINISTIC SERVICE
```

LLM 可以：
- 想
- 写
- 判断
- 提议

System Service 负责：
- 验证
- 授权
- 状态
- 版本
- Commit

## 2. API Types

### Type A — Query
只读；Agent 可用。

### Type B — Proposal
创建 Proposal，不直接改 Canon；Agent 可用。

### Type C — Workflow Command
主要由 Orchestrator 使用。

### Type D — Privileged Mutation
Approval / Lock / Canon Commit / Workflow State。
Agent 不可直接调用。

## 3. Core Services

1. Project Service
2. Requirement Service
3. Decision & Authority Service
4. Artifact / Version Service
5. Planning Service
6. Quality Service
7. Workflow Service
8. Task Service
9. Agent Runtime Service
10. Memory Service
11. Context Service
12. Dependency Service
13. Prompt Runtime
14. Audit Service

## 4. Common Command Context

```text
CommandContext {
  request_id
  project_id
  actor_type
  actor_id
  workflow_instance_id
  task_id
  expected_version
  reason
  timestamp
}
```

## 5. Common Error Categories

- VALIDATION_ERROR
- NOT_FOUND
- VERSION_CONFLICT
- AUTHORITY_DENIED
- LOCKED_OBJECT
- INVALID_STATE
- CONTEXT_MISSING
- CANON_CONFLICT
- DEPENDENCY_CONFLICT
- QUALITY_GATE_FAILED
- RETRY_EXHAUSTED
- TOOL_FAILURE
- MODEL_FAILURE
- INTERNAL_ERROR

## 6. Key APIs

### Requirement
- get_requirement
- list_requirements
- get_effective_requirements
- propose_requirement
- approve_requirement
- supersede_requirement

### Decision / Authority
- get_decision
- list_effective_decisions
- get_authority
- is_locked
- create_decision
- approve_decision
- lock_object
- unlock_object

### Artifact / Version
- get_artifact
- get_artifact_version
- get_current_version
- get_approved_version
- compare_versions
- create_artifact_version

### Planning
- get_story_plan
- get_plotline
- get_chapter_plan
- create_plan_proposal
- create_chapter_plan
- create_replanning_proposal
- approve_plan

### Quality
- create_review_request
- record_review_report
- create_review_issue
- evaluate_quality_gate
- record_regression_result

### Workflow
- create_workflow
- dispatch_event
- pause_workflow
- resume_workflow
- cancel_workflow
- transition (internal only)

### Task
- create_agent_task
- start_agent_task
- complete_agent_task
- fail_agent_task
- cancel_agent_task

### Agent Runtime
- run_agent(task_id)

### Prompt Runtime
- compile_prompt(...)

### Memory
- get_character
- get_character_state
- get_character_knowledge
- get_event
- search_events
- get_plotline
- create_memory_changeset
- commit_memory_changeset

### Context
- build_context_package
- get_context_package
- validate_context_package
- refresh_context_package

### Dependency
- get_dependencies
- get_dependents
- trace_downstream
- analyze_impact

### Approval
- create_human_gate
- get_pending_gate
- submit_user_decision
- cancel_gate

## 7. Tool Side Effect Levels

- S0_READ_ONLY
- S1_CREATE_DRAFT
- S2_CREATE_PROPOSAL
- S3_WORKFLOW_COMMAND
- S4_CANON_MUTATION
- S5_USER_AUTHORITY

Agent 默认只能使用 S0/S1/S2。

Orchestrator 可部分 S3。

S4/S5 不暴露给普通 Agent。

## 8. Agent Tool Principles

- Agents Never Own Canon
- Workflow Owns State
- User Owns Approval
- Queries Safe by Default
- Mutation Requires Authority
- Version Checks Mandatory
- Idempotency Mandatory
- Domain Tools, Not Generic DB Tools
- Memory Commit Transactional
- Tool Access Task-Scoped
- Important Actions Auditable
- Control Plane Deterministic

## 9. Forbidden Generic Tools

禁止：
- execute_sql
- generic_database_write
- memory.write(anything)
- arbitrary set_state
- direct approve / lock / commit

## 10. Task-scoped Capability

```text
CapabilityToken {
  task_id
  agent_id
  project_id
  allowed_tools[]
  allowed_object_scope[]
  expires_at
}
```

Agent Identity ≠ Authority。

权限来自：

> Agent + Task + Workflow State + Capability Scope

## 11. Internal API Groups

```text
/project
/requirements
/decisions
/artifacts
/chapters
/planning
/quality
/workflows
/tasks
/agents
/prompts
/memory
/context
/dependencies
/approvals
/audit
```

## NOVEL-009 — Chapter Quality Review

POST `/api/v1/workflows/chapter-quality` 使用现有 CreatePlanningWorkflow DTO 创建 v3 流程。GET `/api/v1/projects/{project_id}/chapters/{chapter_id}/quality-reviews` 返回绑定精确版本的不可变结果及当前 freshness。POST `/api/v1/workflows/{workflow_id}/quality-review` 使用 event_id、expected_state_version、expected_draft_version、reason 显式重新审阅已完成的 v3 结果，不改写或批准 Draft。同一 event 幂等，过期版本拒绝。没有修改/删除审阅证据的 API。Pydantic `quality/schemas.py` 统一定义 Provider 和响应契约。

复审可绑定新的 current Draft，必须提供精确的 `expected_draft_version`；旧结果继续保存。受阻/暂停的审阅也可使用该接口，或通过 POST `/api/v1/workflows/{workflow_id}/resume` 的可选 `expected_draft_version` 恢复。省略 token 只允许恢复仍为 current 的原绑定 Draft；版本变化返回 409。该 token 仅用于审阅恢复，其他阶段携带时拒绝，既有 Writing handoff 不变。审批 Plan/Brief 已变化仍需走原有 intake/replanning 恢复，不能借复审更换批准依据。

## NOVEL-010 Revision Contract

`POST /workflows/{id}/revision` 输入 event_id、expected_state_version、source_review_id、expected_draft_version、可选 reason；只接受真实 USER 上下文，禁止客户端指定 Authority/Agent 身份/新版本。重复 event 幂等返回，旧 state/Draft token 409。源 Review 必须是当前完成的 non-PASS Review，且已绑定 exact approved WritingProfile；缺失时返回 CONTEXT_MISSING，不创建任务，需用户批准 Profile 后明确重新审阅。

`GET /workflows/{id}/revisions` 分页返回 immutable request、source_binding、可空 plan/result；包括 source IDs、具体 issue ID、preservation/boundary contract、AgentTask/Run/PromptLineage/ContextPackage IDs。输出 DTO 不暴露 ORM。

PLAN_CHAPTER_REVISION / REVISE_CHAPTER 的 Pydantic schema 分别为 `chapter-revision-plan.v1` / `chapter-revision-result.v1`。Agent 无事件或状态字段；系统验证后发出合法完成事件。RevisionResult 的 addressed_issue_ids 不等同“已解决”，必须由 A05 新 Review 复核。详见 [Revision Engine](08-Revision-Engine.md)。
