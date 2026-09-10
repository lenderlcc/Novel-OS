# NOVEL-011 — Human Acceptance + Feedback Loop

**Priority:** P0  
**Depends On:** NOVEL-001~010

## Goal

把用户正式接回系统：

```text
Internal PASS
→ HumanGate
→ Approve / Reject / Comment
→ Feedback Diagnosis
→ C0/C1 Revision
  C2 Replan
  C3/C4 Escalate
```

## Core Product Rule

用户只需要表达：
- 通过 / 不通过
- 哪里不满意
- 新想法
- 哪些要保留
- 哪些要锁定

用户不需要告诉 AI 具体怎么修。

## AcceptanceRecord

绑定具体 ChapterVersion。

Approval 不是 Chapter Completed；仍需 Memory Commit。

## Feedback Flow

```text
Raw Feedback
→ Requirement Agent interpretation
→ FeedbackSpec
→ Review Agent diagnosis if needed
→ FeedbackRoutingService
```

## Change Classification

- C0 Local Polish → Revision
- C1 Scene Change → Revision
- C2 Chapter Change → Replan
- C3 Story Change → Change Workflow
- C4 Canon Change → Human Change Gate

## Feedback Root Layer

- REQUIREMENT
- PLANNING
- WRITING
- REVIEW
- STYLE
- CANON
- UNKNOWN

这样系统不会把所有 Reject 都归罪于 Writer。

## Preserve vs Lock

- Preserve = 当前修改临时约束
- Lock = 持续约束未来 Workflow

用户说“这轮别动结尾”不能自动变永久 Lock。

## Metrics

- Human First Pass Acceptance Rate
- Human Revision Rounds
- Reject Reason Distribution
- Requirement Misunderstanding Rate
- Planning Reject Rate
- Writing Reject Rate
- Quality Miss Rate
