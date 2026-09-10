# NOVEL-007 — Requirement Agent + Planning Agent Vertical Slice

**Priority:** P0  
**Depends On:** NOVEL-001~006

## Goal

第一条真实 AI 业务链：

```text
User natural language
→ Requirement Agent
→ CreativeBrief
→ CP-004
→ Planning Agent
→ ChapterPlan
→ Plan Review
→ Human Plan Gate
```

## Requirement Agent

输出 CreativeBrief：
- intent_summary
- chapter_objective
- must
- should
- preferences
- forbidden
- preserve
- required_outcome
- desired_reader_effect
- creative_freedom
- ambiguities
- assumptions
- conflicts
- confidence

原则：
- 不制造用户没说的重大方向
- 低风险歧义自主处理
- 高风险 + 低置信才升级
- 保留 creative freedom

## Planning Agent

输出 ChapterPlan：
- objective
- required_outcome
- opening_function
- scenes
- character_progression
- plot_progression
- information_release
- ending_function/state
- creative_freedom
- constraints
- risks
- proposed new elements
- proposed major changes
- requirement coverage

原则：
- 不写正式正文
- 不擅自改 Approved / Locked
- 不过度规划
- 重大方向只 Proposal

## Plan Review

Hard Gates：
- Missing MUST
- Forbidden violation
- Locked conflict
- Approved direction violation
- required outcome impossible
- major logic break

Review FAIL → new Planning iteration，不是 technical retry。

## Human Gate

支持：
- Approve
- Reject
- Modify
- Request Alternative
- Lock Element

## Metrics

- Requirement correction rate
- Planning internal first-pass rate
- Human plan approval first-pass rate
- Planning iteration count
