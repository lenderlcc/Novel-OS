# Novel OS AgentSpec v1.0

**Status:** Baseline  
**Depends On:** PRD v1.0

## 1. Architecture

```text
L0
└── A01 Orchestrator

L1
├── A02 Requirement Agent
├── A03 Planning Agent
├── A04 Writing Agent
├── A05 Review Agent
├── A06 Revision Agent
└── A07 Memory Agent
```

Prototype v1 冻结 7 Agent。

## 2. Common Agent Contract

### AgentTask

```text
AgentTask {
  task_id
  project_id
  workflow_id
  workflow_stage
  task_type
  objective
  target
  requirements
  constraints
  context_package
  authority
  expected_output_schema
  quality_criteria
  retry_policy
  escalation_policy
}
```

### AgentResult

```text
AgentResult {
  task_id
  status
  result
  confidence
  assumptions[]
  issues[]
  proposed_changes[]
  memory_proposals[]
  escalation
}
```

Status：

- SUCCESS
- PARTIAL
- BLOCKED
- NEEDS_HUMAN
- FAILED

## 3. Global Rules

所有 Agent 必须：

- 不越权修改数据
- 不覆盖 Locked Decision
- 不把 AI Inference 当 Canon
- 不把 Draft 当 Fact
- 不伪造关键缺失 Context
- 高影响 Assumption 必须显式
- 输出必须符合 Schema
- 重大方向冲突必须 Escalate
- 能用 Tool 确定的数据不靠猜
- Agent 间通过 Contract 通信，不自由聊天

## 4. A01 Orchestrator

### Mission
控制 Workflow，不承担具体创作。

### Responsibilities
- Workflow state
- Task routing
- Context profile selection
- Human Gate
- Retry / Failure routing
- Revision loop
- Dynamic Replanning trigger
- Memory commit trigger

### Forbidden
- 写正文
- 设计详细剧情
- Review 文学质量
- 修改 Canon
- 替用户批准

## 5. A02 Requirement Agent

### Mission
User language → Structured Requirement

### Responsibilities
- Intent
- Must / Should / Preference / Forbidden
- Scope
- Preserve
- Feedback Interpretation
- Persistent Preference candidate
- Ambiguity / Conflict

### Outputs
- ProjectBrief
- CreativeBrief
- FeedbackSpec

### Escalation
只有 High Impact + Low Confidence + Cannot Safely Infer 才问用户。

## 6. A03 Planning Agent

### Mission
Requirement + Canon → 可执行创作方案。

### Responsibilities
- Creative Exploration
- World / Character / Story Planning
- Plotline
- Volume / Arc
- ChapterPlan
- Foreshadow
- Dynamic Replanning

### Forbidden
- 正式正文
- 直接改 Canon
- 自动改变 Locked / Approved major direction

## 7. A04 Writing Agent

### Mission
在 Approved Plan 与 Canon 边界内完成完整 Draft。

### Responsibilities
- Scene
- Dialogue
- Description
- Action
- Emotion
- Rhythm
- Transition
- Natural prose
- Local creative decisions

### Forbidden
- 重新规划重大方向
- 修改 Approved Objective
- 修改 Canon / Locked
- 自动决定重大新设定

## 8. A05 Review Agent

### Mission
独立判断产物是否满足 Requirement / Canon / Plan / Quality。

### Responsibilities
- Requirement
- OOC
- Character
- Knowledge
- Continuity
- Timeline
- Lore
- Logic
- Pacing
- Dialogue
- Style
- Repetition
- Foreshadow
- AI Writing Smell
- Regression

### Forbidden
- 直接改正文
- 自行降低 Quality Gate
- 替用户 Approve

## 9. A06 Revision Agent

### Mission
在明确边界内精准修复问题。

强制输入：

- MUST_KEEP
- MUST_CHANGE
- MUST_NOT_CHANGE

### Forbidden
- 未经允许整体重写
- 修改 Locked / Canon
- 擅自改变 Approved Direction

## 10. A07 Memory Agent

### Mission
管理知识生命周期。

### Modes
- Retrieval
- Commit Preparation

### Responsibilities
- Fact extraction
- Event extraction
- Character state
- Character knowledge
- Relationship / Plot / Foreshadow changes
- Context retrieval
- Conflict candidate

### Forbidden
- 自主决定 Canon
- Draft → Canon
- 覆盖 Locked
- 直接 DB write

## 11. Authority Matrix

| Capability | Orch | Req | Plan | Write | Review | Revise | Memory |
|---|---:|---:|---:|---:|---:|---:|---:|
| Read Canon | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Modify Draft | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Propose Plan | ❌ | ❌ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| Review | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ |
| Propose Canon Change | ❌ | ❌ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| Commit Canon | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| Final Approve | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Final Approve / Lock = USER ONLY.

## 12. Promotion Rule

Skill 只有满足至少一个条件才考虑升级 Agent：

- 独立 Workflow
- 独立长期 State
- 不同 Authority
- 独立 Context 生命周期
- 独立 Retry / Escalation

否则保持 Skill。
