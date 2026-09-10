# Novel OS

Novel OS 是一个面向长篇小说创作的 AI Native 创作操作系统。

它不是单次文本生成器，也不是一个 Giant Prompt，而是通过：

- Human Control Plane
- Deterministic Workflow
- Multi-Agent Runtime
- Structured Memory
- Context Engineering
- Composable Prompt Library
- Quality / Review / Revision
- Versioning & Audit

组成的一套可持续创作系统。

## Prototype v0.1

当前目标不是构建完整商业产品，而是验证一条完整 Chapter Production Pipeline：

```text
User Requirement
→ Requirement Agent
→ CreativeBrief
→ Planning Agent
→ Plan Review
→ Human Plan Approval
→ Writing Agent
→ Chapter Draft
→ Quality Review
→ Revision / Regression
→ Human Chapter Approval
→ Memory Commit
→ Next Chapter uses updated Canon
```

## Design Principles

1. Human Sovereignty
2. Bounded AI Autonomy
3. Review Before Human Review
4. User Approval Creates Authority
5. Draft ≠ Canon
6. Plan ≠ Fact
7. Structured Memory
8. Retrieve, Don't Dump
9. Deterministic Workflow
10. Version Everything Important
11. Agents Never Own Canon
12. User Approval Is Final

## Repository Layout

```text
docs/specs/      核心产品与系统规格
docs/tickets/    NOVEL-001 ~ NOVEL-012 开发任务
backend/         后端（从 NOVEL-001 开始）
frontend/        前端（后续）
prompts/         Prompt Library
workflow-definitions/
context-profiles/
quality-profiles/
schemas/
evals/
```

## Development Order

```text
NOVEL-001
→ NOVEL-002
→ NOVEL-003
→ NOVEL-004
→ NOVEL-005
→ NOVEL-006
→ NOVEL-007
→ NOVEL-008
→ NOVEL-009
→ NOVEL-010
→ NOVEL-011
→ NOVEL-012
```

每完成一个 Ticket：

1. 实现
2. 自动测试
3. Architecture Review
4. Acceptance Review
5. Commit
6. 再开始下一 Ticket

禁止 Codex 一次性跳过多个 Ticket 自行扩展 Scope。

## Current Status

- Product / Architecture Specification: Frozen for Prototype v0.1
- Actual Implementation: Not started
- Next Action: Execute `NOVEL-001 — Backend Bootstrap`

具体规格见 `docs/specs/`，开发任务见 `docs/tickets/`。
