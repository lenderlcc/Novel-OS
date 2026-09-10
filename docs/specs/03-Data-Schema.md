# Novel OS Data Schema v1.0

**Status:** Baseline  
**Purpose:** 定义业务层 Source of Truth，不绑定具体数据库。

## 1. Domain Overview

```text
Project Domain
├── Project
├── Requirement
└── Decision

Knowledge Domain
├── WorldEntity
├── Character
├── CharacterState
├── CharacterKnowledge
├── Relationship
└── Event

Planning Domain
├── StoryPlan
├── Plotline
├── Volume
├── Arc
├── ChapterPlan
└── Foreshadow

Production Domain
├── Chapter
├── ChapterVersion
└── Artifact

Quality Domain
├── ReviewReport
├── ReviewIssue
└── AcceptanceRecord

Workflow Domain
├── WorkflowInstance
├── WorkflowTransition
├── AgentTask
├── AgentRun
└── HumanGate

Memory Domain
├── MemoryChangeSet
├── DerivedMemory
└── ContextPackage

Infrastructure
├── Dependency
├── PromptLineage
├── QualityProfile
└── AuditRecord
```

## 2. Common Metadata

关键对象统一具备：

- id
- project_id
- object_type
- status
- version
- source
- authority_level
- locked
- created_at / updated_at
- created_by / approved_by
- supersedes_id
- tags
- metadata

## 3. Common Status

- DRAFT
- PROPOSED
- APPROVED
- LOCKED
- ACTIVE
- STALE
- SUPERSEDED
- DEPRECATED
- CANCELLED
- EXECUTED
- ARCHIVED

## 4. Authority

- A0_SYSTEM_RULE
- A1_USER_LOCKED
- A2_USER_APPROVED
- A3_CANON
- A4_APPROVED_PLAN
- A5_USER_PREFERENCE
- A6_DERIVED_MEMORY
- A7_AI_INFERENCE

低 Authority 不得静默覆盖高 Authority。

## 5. Core Entities

### Project
根对象，保存项目状态与 current chapter / baseline。

### Requirement
字段核心：
- logical_id
- version
- scope_type / scope_id
- requirement_type
- content
- priority
- persistent
- status
- source
- authority
- effective_from / until
- supersedes_id

RequirementType：
- MUST
- SHOULD
- PREFERENCE
- FORBIDDEN
- QUALITY_EXPECTATION
- PRESERVE
- CHANGE_REQUEST

### Decision
表示“最终决定怎么做”，与 Requirement 分离。

核心：
- question
- decision
- rationale
- source
- authority
- locked
- affected objects
- version

### LockRecord
- target_type / target_id
- scope
- reason
- active
- locked_by
- released_at

### Character
Static identity。

### CharacterState
Dynamic state，append-only history。

### CharacterKnowledge
人物知道 / 怀疑 / 误解什么。

KnowledgeState：
- KNOWN
- PARTIALLY_KNOWN
- SUSPECTED
- BELIEVED
- MISUNDERSTOOD
- UNKNOWN

### Relationship
实体间关系。

### Event
Canon 一级实体，保存：
- story time
- location
- participants
- prerequisites
- consequences
- created / invalidated facts
- source chapter/version

Timeline 是 Event 的索引视图，不是第二套 Source of Truth。

### StoryPlan / Plotline / Volume / Arc
属于 Planning Memory。

### ChapterPlan
章节正式计划输入。

核心：
- objective
- required_outcome
- scene_plans
- character_progression
- plot_progression
- information_release
- ending_state
- constraints
- locked_dependencies
- risks
- version / status

### Chapter
生命周期对象，不直接保存完整正文。

### ChapterVersion
保存正文版本：
- parent_version_id
- version
- content
- source
- change_reason
- status
- created_by

正文版本 immutable。

### ReviewReport / ReviewIssue
Issue 必须包含：
- category
- severity
- location
- evidence
- diagnosis
- impact
- recommendation
- auto_fixable
- requires_human

### AcceptanceRecord
用户对具体 artifact version 的验收记录。

### FeedbackRecord / ChangeRequest / ImpactReport / RevisionRecord
支持 Feedback & Change Workflow。

### WorkflowInstance / AgentTask / AgentRun / HumanGate
支持确定性执行与运行追踪。

### ContextPackage
记录 Agent 实际看到的对象、版本、优先级和 exclusions。

### MemoryChangeSet
Canon mutation 的唯一受控入口。

### Dependency
支持 Impact Analysis / Stale propagation。

### PromptLineage
记录生成时 Prompt 组合。

## 6. Source of Truth Matrix

| Data | Source of Truth |
|---|---|
| 用户需求 | Requirement |
| 用户决定 | Decision |
| 世界规则 | WorldEntity / WorldRule |
| 人物基础 | Character |
| 人物当前状态 | CharacterState |
| 人物知识 | CharacterKnowledge |
| 关系 | Relationship / RelationshipState |
| 已发生事件 | Event |
| 时间线 | Event Index |
| 未来剧情 | StoryPlan / Plotline / Plan |
| 伏笔 | Foreshadow |
| 正文 | ChapterVersion |
| 质量问题 | ReviewIssue |
| 用户验收 | AcceptanceRecord |
| Agent 运行 | AgentRun |
| Memory 变更 | MemoryChangeSet |

## 7. Critical Business Rules

1. DRAFT 不进入默认 Canon Retrieval。
2. SUPERSEDED 不进入普通 Context。
3. LOCKED 禁止 AI 自动更新。
4. Plan 不得被当成 Event Fact。
5. CharacterKnowledge 独立于 Global Canon。
6. Approved ChapterVersion 不允许原地覆盖。
7. Revision 必须产生新 Version。
8. ReviewIssue 必须绑定具体 Artifact Version。
9. Memory Commit 必须绑定 Source Artifact。
10. 任何 Canon Update 必须可追溯到用户批准或系统规则。

## 8. Version Policy

重要对象必须版本化：

- Requirement
- Decision
- WorldEntity / WorldRule
- Character
- Relationship
- StoryPlan / Plotline / Volume / Arc
- ChapterPlan / ChapterVersion
- Foreshadow
- StyleProfile
- Prompt
- QualityProfile

Approved 历史版本 immutable。

## 9. Delete Policy

核心业务数据默认不 Hard Delete。

使用：

- DEPRECATED
- CANCELLED
- SUPERSEDED
- ARCHIVED

保留历史引用。
