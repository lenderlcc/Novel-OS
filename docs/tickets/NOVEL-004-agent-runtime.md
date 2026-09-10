# NOVEL-004 — Agent Runtime & Mock Agent

**Priority:** P0  
**Depends On:** NOVEL-001~003

## Goal

把 Fake Event 升级为真实 AgentTask 执行基础设施，但仍使用 Mock Model。

```text
Workflow
→ AgentTask
→ PostgreSQL Queue
→ Worker
→ Agent Runtime
→ Mock Provider
→ Structured AgentResult
→ Validation
→ Workflow Event
```

## Must Implement

- AgentRegistry
- AgentDefinition
- AgentTask
- AgentRun
- PostgreSQL queue
- claim with `FOR UPDATE SKIP LOCKED`
- lease / heartbeat / recovery
- independent worker process
- ModelProvider base
- MockModelProvider
- structured output validation
- authority validation
- result handler
- task_type → workflow event mapping
- stale result protection
- technical retry

## Critical Rules

- Worker 不包含 Workflow 业务逻辑
- AgentRuntime 不直接改 Workflow
- Agent Result 不能自己指定 next event
- business FAIL 不做 technical retry
- each retry creates new AgentRun
- Agent identity ≠ permission
- stale result cannot advance cancelled/moved workflow
- old worker losing lease cannot overwrite new result

## Acceptance

必须验证：
- 并发 claim 安全
- retry once then success
- retry exhausted
- format error retry
- authority violation blocked
- lease recovery
- stale result ignored
- full mock pipeline reaches human gates and C16
