# NOVEL-006 — Context Engine & Memory Query Foundation

**Priority:** P0  
**Depends On:** NOVEL-001~005

## Goal

让 Agent 按 Task 获取最小充分 Context，而不是整项目 / 整聊天。

```text
AgentTask
→ ContextProfile
→ Memory Query
→ Authority Resolution
→ Status/Version Filter
→ Priority Ranking
→ Token Budget
→ ContextPackage
```

## First Profiles

- CP-004 Chapter Planning
- CP-005 Chapter Writing
- CP-006 Full Chapter Review
- CP-007 Targeted Revision

## Priority

- P0 Mandatory
- P1 High
- P2 Supporting
- P3 Optional

P0 永不因 token budget 被静默裁剪。

## Must Implement

- ContextProfile registry
- ContextRequest
- ContextItem
- ContextPackage
- MemoryQueryService
- exact / structured retrieval
- authority resolver
- status/version filtering
- exclusions
- relevance ranking
- token budget
- freshness validation
- future knowledge policy
- character knowledge separation
- context hash / snapshot
- debug inspector
- AgentTask / PromptRuntime integration

## Critical Rules

- Approved Plan only for Writing
- previous approved chapter, not current draft
- SUPERSEDED/DEPRECATED excluded
- latest != correct
- future plans restricted for Writer
- global fact != character knowledge
- Context Engine does not modify Workflow
- Context Serializer does not query DB

## Acceptance

必须验证：
- Draft leakage blocked
- locked decision P0
- same-authority conflict blocks
- project isolation
- token budget behavior
- stale context detection
- future knowledge restriction
- stable context hash
