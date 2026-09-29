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

## NOVEL-010A Fidelity Contract

新 PLAN_CHAPTER_REVISION 使用 `chapter-revision-plan.v2`，新增三个 preservation arrays、strength_preservation/risks、revision_zones、allowed_structural_change、structural_authorization 和 change_budget。REVISE_CHAPTER 仍输出 `chapter-revision-result.v1`，但只保存候选产物，不直接创建当前正文。A05 VALIDATE_REVISION_FIDELITY 使用 `revision-fidelity-result.v1`；精确 source/plan/candidate/hash、checks、violations、verdict 由服务统一校验。

GET `/workflows/{id}/revisions` 增加可空 candidate（完整 proposal、A06 lineage）以及 result.body.candidate_id/fidelity/accepted（A05 lineage），既有 v1 历史依旧可读。失败 result.chapter_version_id=null，不新增可接受 Draft；普通 UI 使用固定失败文案，Debug 查看具体内部 FidelityCode。这些字段不能通过客户端来授权新版本或绕过 Service gate。

## NOVEL-010B Workspace 复用 API

不增加端点。GET `/projects/{project_id}/chapters/{chapter_id}/versions` 提供不可变版本列表，Chapter.current_version 是当前正文指针。GET 同路径 `/quality-reviews` 全量分页后按 exact chapter_version_id 筛选，以 Review.version 选该正文最新审阅，不能依赖返回数组顺序或直接取最新章级 Review。历史正文可读其历史 Review；请求修改还必须验证 Review.binding.workflow_id 是当前 Workflow。

POST `/workflows/{id}/revision` 复用 `event_id + expected_state_version + expected_draft_version + source_review_id`。Workflow 确定 Chapter，Review 确定 immutable ChapterVersion ID；前端不传正文、Plan JSON、Agent 或 Authority。请求结果不确定时，同一来源重用 event_id；409 不静默刷新重试。后端锁、Fidelity、追加版本及事务规则不变。

新增 CP-007 v5 仅提高本地保守预算至 240000，容纳完整 source/review/authority、RevisionPlan、candidate 及 Fidelity Schema；不截断 P0、不改变选择策略。v4 与已冻结请求保持不变，新请求绑定 v5。该预算不是计费 token 或 Provider 窗口声明。

A05 Compliance/Narrative 的 evidence 仍是单个 paragraph_index 加该段的精确连续 excerpt。`quality-evidence` skill v3 明确跨段论证必须拆成独立引用条目；JSON Schema、API、校验规则和历史 v2 pin 均保持兼容。

## NOVEL-011：Human Feedback API

POST `/api/v1/workflows/{workflow_id}/feedback`：event_id、expected_state_version、source_chapter_version_id、raw_feedback、可选 reason。禁止客户端注入 source/status/action/authority；当前正文 UUID 和工作流状态不匹配返回 conflict。重复 event_id 相同 payload 返回原结果，不创建第二条反馈。

GET 同一路径：limit/offset 分页返回反馈与可选 Interpretation（exact Draft、task/run/prompt/context lineage、typed body）。Revision history 增加 nullable source_feedback_id/source_review_id/source_binding；人工来源通过 Interpretation绑定，不伪造 Review。Structured Output 以 Pydantic FeedbackAgentResult 为准，Proposal/Memory arrays必须为空。参见 [Human Feedback](09-Human-Feedback.md)。
