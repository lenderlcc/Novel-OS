# Novel OS Technical Architecture v1.0

**Status:** Prototype Baseline  
**Strategy:** Modular Monolith First

## 1. Prototype Goal

验证：

```text
Requirement
→ Planning
→ Human Approval
→ Writing
→ Review
→ Revision
→ Human Approval
→ Memory Commit
```

当前风险是产品逻辑，而不是 QPS。

## 2. Architecture Strategy

采用：

# Modular Monolith

```text
Vue Web UI
    │
HTTP / SSE
    │
FastAPI
├── Workflow Engine
├── Domain Services
├── Control Plane
├── Agent Runtime
├── Context / Memory
├── Quality
└── Version / Dependency
    │
PostgreSQL

Agent Worker
└── Prompt Runtime
    └── Model Adapter
        └── LLM Providers
```

## 3. Technology Baseline

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Database:
- PostgreSQL

Search:
- SQL
- PostgreSQL FTS
- pgvector optional later

Frontend:
- Vue 3
- TypeScript

Realtime:
- SSE

Local:
- Docker Compose

## 4. Why Not Microservices

Prototype 不做：
- Service discovery
- Distributed transaction
- Kafka
- Kubernetes
- Graph DB
- Dedicated Vector DB

原因：
- 当前低并发
- 大量跨域事务
- Debug 优先
- 单机足够

## 5. Database Strategy

采用：

> Relational Core + JSONB Flexible Fields

结构化列保存：
- authority
- version
- status
- relationship
- references

JSONB 用于：
- flexible planning attributes
- scorecard
- metadata
- assumptions

影响权限与版本的数据不能全部藏在 JSON。

## 6. Search Strategy

1. Exact Fetch
2. Structured Query / FTS
3. Semantic Retrieval later

Vector Search 不是 Memory Source of Truth。

## 7. Workflow Engine

自研轻量确定性 State Machine：

- WorkflowDefinition
- WorkflowInstance
- WorkflowTransition
- EventDispatcher
- GuardRegistry
- WorkflowRuntime

Workflow Definition 使用 YAML / config，业务 Guard 用代码实现。

## 8. Agent Runtime

```text
AgentTask
→ Context Resolver
→ Prompt Compiler
→ Model Adapter
→ LLM
→ Output Parser
→ Schema Validator
→ Authority Validator
→ AgentResult
```

Agent Runtime 不决定 Workflow next state。

## 9. Background Worker

FastAPI 与 Agent Worker 分离。

Prototype Task Queue 使用 PostgreSQL：

- PENDING
- CLAIMED
- RUNNING
- SUCCEEDED
- FAILED

后续并发需求起来再引入专用 Queue。

## 10. Model Provider Abstraction

统一接口：

- generate
- generate_structured
- stream
- count_tokens
- get_capabilities

Agent 不绑定具体 Provider。

## 11. Prompt Runtime

```text
System Policy
+ Agent Role
+ Task Template
+ Skills
+ Quality Profile
+ Context
+ Output Contract
→ Prompt Compiler
→ Model Adapter
```

Prompt Source of Truth = Git files。

DB 只保存 PromptLineage。

## 12. Context Engine

```text
Task
→ Context Profile
→ P0 Retrieval
→ P1/P2 Search
→ Authority Resolution
→ Exclusion
→ Ranking
→ Budgeting
→ ContextPackage
```

## 13. Quality Engine

```text
Deterministic Evaluators
+
Review Agent
+
Quality Aggregator
```

Quality Aggregator 必须是确定性代码。

## 14. Storage

Prototype：
- 文本正文：PostgreSQL TEXT
- Metadata：JSONB
- 文件：Local filesystem
- Production：S3-compatible object storage

## 15. Recommended Repository Structure

```text
novel-os/
├── backend/
├── frontend/
├── prompts/
├── workflow-definitions/
├── context-profiles/
├── quality-profiles/
├── schemas/
├── evals/
├── migrations/
├── tests/
├── docs/
└── docker/
```

## 16. Backend Structure

```text
backend/novel_os/
├── api/
├── domain/
├── services/
├── repositories/
├── workflow/
├── agents/
├── context/
├── memory/
├── quality/
├── prompts/
├── models/
├── tools/
├── events/
├── audit/
└── infrastructure/
```

Dependency direction：

```text
Agent → Tool → Service → Repository → Database
```

禁止 Agent → SQL。

## 17. Prototype P0 Scope

- Project
- Requirement
- Decision / Lock
- ChapterPlan
- Chapter Writing
- Internal Review
- Revision
- Human Approval
- Character Memory
- Event Memory
- Context Assembly
- Memory Commit
- Workflow Engine
- Version History

## 18. Explicitly Not Yet

- Kubernetes
- Microservices
- Kafka
- Neo4j
- Dedicated Vector DB
- Fine-tuning
- Multi-user Collaboration
- Plugin Marketplace
- Complex Publishing / Illustration

## 19. Prototype Technical Success Criteria

必须证明：

1. Human Gate 可暂停 / 恢复
2. Agent 无法改 Canon
3. Writing 使用结构化 Context
4. Review 独立
5. Review FAIL → Revision
6. Revision 新版本
7. Approval 绑定版本
8. Memory Commit 原子化
9. 下一章读取新 Canon
10. 全链路可 Audit

## NOVEL-009 — Chapter Quality Review

质量审阅复用既有 Worker/AgentRuntime/A05/Context/Prompt 链路，两个任务共享冻结的 review binding。Result Service 控制 pass → aggregate → workflow/audit 事务。数据库保护追加式证据和 exact lineage。没有新增调度器、Memory 数据库、评分服务、模型投票或自动修订。配置文件中的 chapter-quality 范围显式包含两个新任务；chapter-writing 保留原允许列表。详见 [Quality Engine](07-Quality-Engine.md)。

## NOVEL-010 Persistence / Runtime

在现有 API → Service → Repository → Database 和 Agent Runtime 上扩展 A06；无第二套队列/状态机。0012 添加 append-only revision_requests/plans/results 与 workflow active request FK。事务边界仍在 WorkflowRuntime / AgentResultHandler，Repository 仅 flush。新增 Draft 与 RevisionResult、Audit、工作流事件、下一 A05 task 原子提交；唯一约束、项目锁、乐观 token、lease fencing 共同防止重复写入。

CP-007 v3 重用正式 Quality 源选择并加入 exact Review、authority contract、RevisionPlan；既有 QualityBinding 冻结 source fingerprints，运行时两次校验，继承 approved/current 分离。history 使用分页联合查询。Domain 无 FastAPI/ORM 依赖；所有 Prompt/Context/Model 通过原 Runtime 追溯。详见 [Revision Engine](08-Revision-Engine.md)。
