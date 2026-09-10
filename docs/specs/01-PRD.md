# Novel OS PRD v1.0

**Status:** Baseline  
**Scope:** Novel OS 系统设计；不讨论任何具体小说内容。

## 1. Product Vision

Novel OS 是一个面向长篇小说创作的 AI Native 创作操作系统。

目标不是“让 AI 帮忙续写”，而是把用户创作意图转化为：

> 可规划、可执行、可审查、可修改、可追溯、可持续迭代的长篇创作生产流程。

## 2. Core Problems

通用 AI 小说创作主要存在：

- 自主性不足：用户需要不断告诉 AI 下一步做什么。
- 创意不足：容易输出安全、模板化、平均化方案。
- 文本机械：过度解释、均匀节奏、功能化对白、角色声音趋同。
- 长篇一致性不足：OOC、时间线、人物知识、伏笔、状态连续性容易崩。
- 修改不精确：用户只要求改 A，AI 常顺带破坏 B/C/D。

## 3. Target User

Primary User = **Creative Director / Product Owner**

用户负责：

- 提出需求
- 提供创意
- 决定整体方向
- 决定章节方向
- 审核重要方案
- 提供反馈
- 最终验收

用户不负责：

- Prompt Engineering
- Agent 调度
- Context 管理
- Review 流程
- 修改任务拆解

## 4. Human-AI Collaboration

采用：

# Human Sovereignty + Bounded AI Autonomy

用户始终拥有最终创作主权；AI 在用户批准边界内拥有较高自主权。

### Human Authority

用户可随时：

- 提新需求
- 修改需求
- 补充创意
- 否决方案
- 要求重做
- 指定保留内容
- Lock / Unlock
- 推翻历史决定

### AI Authority

AI 默认自主：

- 需求理解
- 方案设计
- 局部创作
- 内部 Review
- 普通 Revision
- Context Retrieval
- Memory Extraction

原则：

> Escalate Decisions, Not Problems.

## 5. Core Product Principles

1. Human Sovereignty
2. AI Owns Execution
3. Review Before Human Review
4. User Approval Creates Authority
5. Canon Is Explicit
6. Structured Memory
7. Retrieve, Don't Dump
8. Plan Before Write
9. Self-Heal Before Escalation
10. Version Everything Important

## 6. Product Scope

### Planning
- 创意探索
- 世界观
- 人物
- 人物关系
- 主线 / 支线
- 分卷 / Arc
- 章节规划
- 时间线
- 伏笔

### Production
- 场景
- 章节正文
- 对话
- 描写
- 动作
- 情绪
- Revision / Rewrite

### Quality
- Requirement
- OOC
- Character
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

### Knowledge
- Canon
- Character State
- Character Knowledge
- Relationship
- Timeline / Event
- Plotline
- Foreshadow
- Requirement
- Decision
- Style

### Infrastructure
- Workflow
- Agent Runtime
- Memory
- Context Engine
- Prompt Library
- Version
- Quality Analytics
- Dashboard

### Downstream
- 发布
- Metadata
- 平台格式转换
- 封面 / 插图
- 素材管理

## 7. Core Workflows

### Workflow A — Project Initialization

```text
Project Intake
→ Requirement Normalization
→ Creative Exploration
→ Core Premise
→ World / Character / Story
→ Timeline / Relationship / Foreshadow
→ Volume / Arc
→ Global Review
→ Human Project Gate
→ Canon Commit
→ Project Ready
```

### Workflow B — Chapter Production

```text
Chapter Request
→ Context Assembly
→ CreativeBrief
→ Chapter Planning
→ Human Plan Gate
→ Writing
→ Internal Review
→ Auto Revision
→ Human Acceptance
→ Memory Commit
→ Next Chapter
```

### Workflow C — Feedback & Change

```text
User Feedback
→ Interpretation
→ Change Classification
→ Impact Analysis
→ Preserve / Change Boundary
→ Change Plan
→ Human Gate if needed
→ Execute
→ Targeted Review
→ Regression Review
→ Human Acceptance
→ Commit
```

## 8. Change Classification

- C0 Local Polish
- C1 Scene Change
- C2 Chapter Change
- C3 Story Change
- C4 Canon Change

C0/C1 默认可 Revision；C2 需 Replan；C3/C4 必须升级。

## 9. Agent Architecture

Prototype v1 固定 7 个 Agent：

1. Orchestrator
2. Requirement Agent
3. Planning Agent
4. Writing Agent
5. Review Agent
6. Revision Agent
7. Memory Agent

专业能力优先实现为 Skill，而不是继续拆 Agent。

## 10. Memory Model

五层：

- Canon Memory
- Decision Memory
- Planning Memory
- Working Memory
- Derived Memory

关键原则：

- Memory ≠ Canon
- AI Output ≠ Canon
- Plan ≠ Fact
- Derived Memory 不是 Source of Truth
- User Approval 才能提升权威

## 11. Quality Model

五层：

- Q1 Requirement Quality
- Q2 Consistency Quality
- Q3 Story Quality
- Q4 Prose Quality
- Q5 Human Acceptance

使用：

> Hard Gate + Soft Score

而不是单一平均分。

## 12. North Star Experience

理想状态：

> 用户提出创作意图、方向与反馈；Novel OS 自主组织规划、创作、审查和修改。AI 在允许空间内拥有足够自主性，但不会越过用户批准的重大方向。系统长期可靠维护人物、世界、剧情、时间线、关系、伏笔和用户要求；最终产物自然、个体化、非模板化。

## 13. Prototype Success Criteria

Prototype 必须证明：

- 用户不需要复杂 Prompt
- Workflow 可自动推进
- Human Gate 可暂停 / 恢复
- Agent 无法越权改 Canon
- Writing 使用结构化 Context
- Review 能发现真实问题
- Revision 能精准修改
- Approval 绑定具体版本
- Approved Chapter 可更新 Memory
- 下一章可读取新状态
- 全流程可 Audit
- Failure 不污染 Canon
