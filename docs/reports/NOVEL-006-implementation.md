# NOVEL-006 — Context Engine & Memory Query Foundation

日期：2026-09-11。分支：`wfg/novel-006-context-engine`。基线：`4614e0d`。
本报告仅覆盖 NOVEL-006。完成后等待 Review，不启动 NOVEL-007，不自动提交或推送。

## 1. Implementation Summary

实现结构化 Context 查询、可版本化 Profile、确定性策略、不可变执行快照和 Inspector。
生产 Worker 必须先取得持久化 READY Package，才会调用模型；返回结果必须携带该运行对应的
Package ID/hash，且应用前重新验证源数据。未新增业务 Agent、Memory Domain 或向量检索。

新增代码集中于 `backend/novel_os/context/`、`domain/context.py`、`services/context.py`、
`services/memory_query.py`、两类 Context Repository、Context ORM、只读 API 和 0007 迁移。
现有 Runtime/Worker/ResultHandler 只增加上下文接入与结果绑定检查。没有升级依赖或修改 uv.lock。

## 2. Context Engine Architecture

调用链：API → ContextService → Repository → PostgreSQL。
执行链：Task → Profile → MemoryQueryService → Filter → AuthorityResolver → Ranker → Budgeter
→ immutable Package → ContextSerializer → PromptCompiler → Provider。
Domain 使用标准库 frozen dataclass/enum，不依赖 FastAPI、Pydantic 或 SQLAlchemy。
ContextEngine 不访问数据库、不调用模型、不改变 Workflow；阻塞由现有应用层结果处理器派发。

## 3. ContextProfile Design

Profile 包含 ID/version/status、允许的 Task 类型、token budget、future policy/horizon 和 selectors。
Selector 明确 source type、priority、required、authority floor、allowed statuses、version policy、
scope、max_items、ranking/serialization policy。Pydantic 拒绝未知字段、不合法预算、重复 selector、
非 P0 required selector，以及无精确目标的 Draft 策略。Registry 拒绝重复版本、原地改写及哈希冲突。
数据库按 Profile ID/version 检查历史绑定；并发发布检查使用事务级 advisory lock。

## 4. ContextProfile Files

| 文件 | 用途 | 未来信息策略 | 预算 |
|---|---|---|---:|
| `context/profiles/CP-004.v2.json` | Planning | LIMITED，显式、最多下一章 | 48000 |
| `context/profiles/CP-005.v2.json` | Writing | REQUIRED_ONLY | 48000 |
| `context/profiles/CP-006.v2.json` | Review / deterministic check | LIMITED | 48000 |
| `context/profiles/CP-007.v2.json` | Revision | REQUIRED_ONLY | 48000 |
| `context/profiles/CP-000.v1.json` | 既有 Mock 控制阶段、独立 smoke | NONE | 48000 |

路径相对 `backend/novel_os/`。配置来自版本化 JSON 文件，运行配置继续使用 TOML，没有新增环境变量。
CP-004～CP-007 的 v1 文件及 hash 保留；v2 修正显式 artifact 依赖为 LOCKED/A1 策略，历史包仍按原版本重放。
Generic `CHAPTER_PLANNING/WRITING/REVIEW/REVISION` 已映射到对应 Context Profile；没有新增真实 Task/Agent 业务实现。

## 5. ContextRequest

显式携带 project/task/chapter、workflow/state version、attempt number、目标正文版本、批准计划版本、
章节序号、任务输入、explicit/required/future refs、missing bindings 和 knowledge scope/character ID。
应用层从当前 Task、Workflow 与同一精确批准计划构造请求，不接受客户端伪造这些执行绑定。
通用请求契约可用于未来扩展测试；生产 Worker 请求来源是持久化 Task。

## 6. ContextItem

包含稳定 item ID、source type/ID/logical ID/version、project、status、authority、lock、priority、
scope、structured payload、选择原因、源时间、章节关系、future/plan 标记及 provenance。
Domain 内 payload 保存为 canonical JSON 字符串，读取时返回独立对象，防止嵌套可变对象改写快照。
Serializer 提供结构化 payload；业务文本始终是 DATA。

## 7. ContextPackage

冻结保存请求、Profile 精确版本/hash/定义、构建状态、items、排除项、缺失项、权威冲突、source
snapshots、预算、估算与预留、future policy、package hash 和创建时间。
READY/BLOCKED 快照均可持久化，构建后不允许 UPDATE/DELETE。freshness 是查询结果，不能改写包内容。
新 Profile 版本或新来源不会重新解释历史 Package。

## 8. MemoryQueryService

这里只是现有 Core Domain 的结构化查询 facade。当前读取 Project、Chapter、Requirement、Decision、
Lock、ChapterPlan、ChapterVersion。它提供候选与查询指纹，不决定最终 Package。
`ContextSourceReader` 是未来 Memory 数据源扩展接口；Character/Event/Canon 无 ORM 或数据库表。

## 9. Retrieval Strategy

强制 exact fetch / structured SQL。Chapter artifact 查询包含 project ID、chapter ID 和具体 version；
前文章节选择按章节序号找最近有批准正文的章节，再读取 approved_version。
Requirement 按有效状态、作用域、时间范围、类型查询；Decision 按结构化 affected_objects 关系查询。
显式锁定的 Requirement/Decision 依赖以 logical ID + version + project + active Lock 查询，允许脱离普通目标作用域，
随后仍接受未来信息策略过滤。所有候选有稳定排序与检索数量上限；P0 超过检索上限会阻塞。
没有全文检索、Embedding、pgvector、向量库、外部 RAG 或 LLM ranking。

## 10. Authority Resolution

按既有 A0 → A7 层级，同一 source type/logical ID 的高权威候选胜出；同权威不同 payload 形成显式冲突并阻塞。
同内容重复来源去重。胜出项继承该组最高优先级，A1/A2 可压过 A7，但不能被 optional selector 数量限制删除。
不使用 LLM 推测不同业务对象之间的语义矛盾。

## 11. Status Filtering

排除 STALE/SUPERSEDED/DEPRECATED/CANCELLED/ARCHIVED，以及 selector 不允许的状态。
普通 Requirement/Decision 读取批准或有效锁定记录；unrelated Draft/Proposed 不进入上下文。
Chapter 的 DRAFT 是容器生命周期，不表示选择未批准正文；正文/计划版本采用独立规则。

## 12. Version Selection

Writing 的 required plan 使用 `workflow.plan_version`，与当前 approved_plan_version 不一致时阻塞；
依赖也从这个版本提取。前文按 approved_version，不读取 current_version 的未批准正文。
Review/Revision 可读取 workflow.draft_version 的精确目标 Draft。创建 target Plan v2 Draft 不会替换批准 Plan v1。
已锁定 Requirement/Decision 依赖也使用明确版本，不能通过普通 effective 查询碰巧找到或遗漏。

## 13. Priority Model

CP-005 的批准计划、有效 MUST/FORBIDDEN/PRESERVE、锁定 Decision、目标 Chapter 为 P0；
其他有效需求/决定及前文批准正文为 P1。CP-004 包含目标、有效需求/决定、任务约束等 P0，项目元数据为 P2。
Priority 由 Profile 决定，reader 无权降级。required_refs 自动提升为 P0。
合法空集合不等于缺失：没有 MUST 需求时无需虚构；已有且有效的匹配项必须完整保留或阻塞。

## 14. Ranking

确定性顺序为 Priority → Authority → 明确关联分值 → scope match → source updated time →
source type/logical ID/version/source ID/selector ID。关联分值来自目标关系，未使用模型或随机数。
候选物理返回顺序不影响排序与 hash；排除项也按稳定键排序。

## 15. Token Budget

`TokenEstimator` 为 provider-neutral 接口，默认 UTF-8 字节数保守估计，并非实际计费 tokenizer。
预算扣除 Prompt envelope（含消息 frame 与原生 output schema）和 model max_output_tokens 预留。
先保留全部 P0，再按 P1/P2/P3 尝试纳入完整条目。超额 optional 条目标记 TOKEN_BUDGET；不截断正文片段。
P0 自身超额返回 BLOCKED/CONTEXT_BUDGET_EXCEEDED，保留 P0 供诊断。独立 smoke 也计入 overhead 与输出预留。

## 16. Missing P0 Handling

缺少 required selector、required ref、计划版本绑定或声明的 active Lock 时，返回业务 BLOCKED。
在最终 selected 集合再次检查 required refs。Context 缺失、预算超额、权威冲突和检索上限不会走技术重试。
Worker 在调用 Provider 前完成检查；ResultHandler 也拒绝没有持久化 Package 的成功结果。
数据库等技术故障回滚构建事务，由既有基础设施错误路径记录失败/重试，不伪造成功快照。

## 17. Future Knowledge Policy

NONE 不允许 future；REQUIRED_ONLY 只允许显式 required_future_refs；LIMITED 要求 explicit ref
且处于配置的章节窗口；FULL 为契约支持，不是当前 Writing/Review 默认值。
Writer 的 future refs 只来自精确批准计划声明的必要锁定依赖，未提供“读取所有未来计划”的查询。
依赖的章节关系产生 future 标记，Plan 保留 is_plan 标记；没有批准且没有被精确锁定为必要依赖的未来内容不进入包。
锁定依赖可处于尚未独立批准的 LOCKED 状态；主计划、前文和普通 Draft 的选择规则保持不变。

## 18. Character Knowledge Boundary

GLOBAL_ONLY 与 CHARACTER_KNOWLEDGE 是不同类型。角色请求只接受相同 character_id 的角色认知数据；
Global Canon 不自动转换为角色已知信息，角色认知也不能直接升格为全局事实。
通用测试夹具验证这条防火墙。未建立 Character、CharacterKnowledge、Event 或 CanonFact persistence。
KNOWN/SUSPECTED/MISUNDERSTOOD 等正式 Memory 状态留给 NOVEL-012。

## 19. Freshness / Staleness

每个 selector 保存稳定候选指纹和相关指针观察，覆盖源版本、批准/当前目标指针、lock、作用域与有效集合变化。
同时验证 workflow state version、Task/project/chapter 绑定、Profile 精确版本/hash 和 Package 自身 hash。
模型调用前及结果应用前分别检查；执行中不自动换成最新包。批准计划改变后旧包为 STALE，结果不会落库。
Workflow 已切换/暂停/取消的成功模型结果沿用 STALE_IGNORED，保留成功执行历史而禁止应用。
Inspector 对已不适用当前阶段的历史快照显示 STALE，不表示历史记录被篡改。

## 20. Context Hash

使用 canonical JSON + SHA-256。参与内容包括精确 Profile、执行绑定、源指纹、选择结果、顺序和策略；
忽略 package ID、构建时间及 request_id。稳定来源 item ID 与源时间保持来源可追溯性。
新的执行尝试是新的绑定输入，Package ID 必须不同；结果校验同时比较 ID 与 hash，不能只比较内容 hash。

## 21. Context / Prompt Integration

AgentRuntime 的准备阶段可以产生用于估算的 skeleton，但 skeleton 无 Package，不能执行模型。
可执行请求的 context_payload 只来自 ContextSerializer，位于 `CONTEXT_DATA` user message，标记
`UNTRUSTED_DATA_ONLY`。PromptCompiler 继续不读取数据库或 Memory，不选择上下文。
Runtime 校验 Package/Task/attempt 绑定及序列化数据；Provider 返回仍经过原有 schema/authority 校验。

## 22. AgentTask Integration

每个 AgentRun 以唯一关系绑定一个 ContextPackage；Task Inspector 可查看最近一次运行的包。
ExecutionResult 携带 context_package_id/hash，ResultHandler 对照 lease 对应的数据库行校验。
attempt 1 的成功输出无法配合 attempt 2 的租约提交。缺少持久化快照、引用不匹配或源 stale 均不写业务数据。
没有增加新的调度系统，沿用 NOVEL-004 claim/start/heartbeat/fencing/retry 流程。

## 23. Persistence

新增一张 `context_packages`，具有 run/task 复合 FK、run 唯一约束、Profile/hash/status 校验和 JSONB snapshot。
item/source/version/排除原因等元数据可通过 JSONB 查询；正文 payload 保留 canonical JSON 表达。
BEFORE UPDATE/DELETE trigger 拒绝历史修改。没有修改旧的 AgentTask/Run 或 PromptLineage 表。
Repository 只 add/flush/query，事务由 ContextService 持有；顺序沿用 Project → Workflow → Task。
同一事务保存 Package 与审计，模型 RPC 不占用数据库事务。

## 24. Inspector APIs

- `GET /api/v1/context-packages/{context_package_id}`
- `GET /api/v1/agent-tasks/{task_id}/context`

只读返回 package、freshness、error_code，包含精确来源版本、Priority、Authority、预算、缺失/冲突、排除原因。
未找到快照返回既有统一 NOT_FOUND。遵循本机单用户控制面；不返回 Provider credentials 或运行配置。

## 25. Tests Added

新增 `tests/context/test_context.py`、`tests/core/workflow/test_context_engine.py` 和显式 Context 测试支持。
覆盖 Profile、权威、状态、Draft、预算、future、角色知识、hash、freshness、序列化、Runtime、SQL/API、
并发、事务回滚、数据库不可变、Repo 不 commit、迁移和 E2E。
原有独立 Runtime 测试补充明确 Context 夹具；集成测试先持久化真实快照，保留旧有业务断言。
历史迁移测试改为显式起始 revision，避免新 head 改变原迁移往返的测试对象。

## 26. P0 Budget Test Result

PASS：P0 超预算阻塞且内容完整；P3/P2 优先于 P1 被排除；Prompt overhead 与输出预留计入预算。
额外复现并修复 reader 降级必需项、required P1 被预算裁掉、权威合并后的 P0 被 selector quota 裁掉。

## 27. Version Leakage Test Result

PASS：前文 approved=v2/current=v3 只含 v2；当前未批准 Plan v2 不覆盖 Plan v1；
Review 只允许精确绑定目标 Draft；通用 Writing 类型也绑定 Workflow 的批准计划版本。

## 28. Authority Conflict Test Result

PASS：A1 USER_LOCKED 优于 A7，A2 USER_APPROVED 优于较低权威；同权威不同内容阻塞。
去重及优先级继承不丢失 P0。

## 29. Future Knowledge Test Result

PASS：四类 future policy、Writer 无关未来计划排除、显式必要依赖、未批准未来 Plan 排除。
集成测试分别覆盖未来章节的锁定 Plan/Requirement/Decision，验证精确版本、future 标记及释放 Lock 后 stale。

## 30. Cross-project Isolation Result

PASS：SQL 以 project ID 约束，其他项目与无关章节需求不进入 Planning Package；
纯策略额外拒绝 project mismatch，精确 artifact 查询不跨项目，错误 run/task 组合违反数据库 FK。

## 31. Freshness Test Result

PASS：源指纹、批准指针、Workflow version、Profile hash 变化均被检测。
Lineage bind 后、模型调用前批准新计划会停止调用；模型已返回后批准新计划也不能应用旧结果。

## 32. Context Hash Test Result

PASS：不同候选排列产生同一排序/hash；不同 request_id、Package ID、构建时间不改变 hash。
快照可往返恢复，外部修改 structured payload 返回副本不影响原包；新 Profile 不改写旧 Package。

## 33. Prompt Injection Regression Result

PASS：上下文中的 Ignore system prompt / Approve / Set state / Unlock 文本保持 DATA；
伪造 next_state 被 schema 拒绝，伪造 APPROVE 被 authority 拒绝，不创建计划、不批准 HumanGate。
原 NOVEL-005 Prompt 信任边界、Provider 和 Lineage 回归保留。

## 34. E2E Planning Context Result

PASS：Project + Requirement v2 approved/v3 proposed + locked Decision + 前章批准正文，构建 CP-004。
正确纳入 P0/P1，排除 superseded、其他项目/章节和 Draft。Package 经 Serializer/Runtime 使用，成功输出正常落库。

## 35. E2E Writing Context Result

PASS：Plan v1 approved，前章 approved=v2/current=v3 Draft，存在未来未批准计划。
CP-005 只包含 Plan v1 与前文 v2；模型成功结果应用经过 Package 绑定与 freshness 验证。
E2E-C 的新批准计划使旧包 stale，快照不变、旧模型正文不落库。

## 36. Migration Result

PASS：开发库实际执行 `alembic upgrade head` → `downgrade -1` → `upgrade head` → `check`。
往返 revision 为 `0006_prompt_runtime` ↔ `0007_context_engine`；开发库降级前 Context 表为空。
`alembic check`：No new upgrade operations detected。隔离测试 schema 在有 Package 的情况下完成往返，
逐表比较所有旧 Core、Workflow、Task、Run、PromptLineage 和审计记录不变。
旧 0001–0006 文件均未修改。

## 37. Full pytest Result

Review 修复后 `pytest`：**509 passed, 1 skipped, 2 warnings，182.46 秒**。
其中 NOVEL-006 共新增 79 个通过用例：50 个 Context 单元/Runtime 用例、29 个 PostgreSQL 集成用例；
NOVEL-001–005 的 430 个既有通过用例全部保留通过。

使用单独 PostgreSQL 测试库与每测试独立 schema；真实 Provider 付费测试保持显式 opt-in，未发起真实模型请求。
保留 FastAPI/Starlette/httpx/AnyIO 已存在的两项 deprecation warnings，本次不升级基础依赖。

## 38. Lint Result

`ruff check`、`ruff format --check`、`git diff --check`：PASS。
`uv build`：生成 wheel 与 sdist，版本仍为 0.1.0；Profile 文件包含在发行包中。
`pyproject.toml`、`uv.lock`、既有配置基础设施均未修改。

## 39. Docker Result

`docker compose build backend`：PASS。最终镜像已通过 `docker compose up -d --no-deps --wait backend` 重建运行。
Backend、开发 PostgreSQL、测试 PostgreSQL 均 running/healthy。
`GET /api/v1/health` → HTTP 200 `{"status":"ok"}`；
`GET /api/v1/health/db` → HTTP 200 `{"status":"ok","database":"ok"}`。
容器内新 Context Inspector 路由已注册，未知 UUID 返回统一 NOT_FOUND/404。

复用已安装 Docker/Colima、现有 Compose/PostgreSQL 与 TOML 配置，没有使用 sudo。

## 40. Acceptance Criteria PASS / FAIL

| 验收项 | 结果 / 证据 |
|---|---|
| 1–5 Profile registry/校验/重复/版本/历史包 | PASS，Profile 单元测试及历史 pin 检查 |
| 6–13 P0/P1/P2/P3、预算、missing、零模型调用 | PASS，预算矩阵及 Worker missing/budget 集成测试 |
| 14–17 Authority 冲突与覆盖 | PASS，A1/A2 对低权威及同权威冲突测试 |
| 18–22 状态和精确 Draft | PASS，状态参数矩阵与 target version 测试 |
| 23–26 approved/current、Writing plan | PASS，E2E-A/B 和新 Draft 隔离 |
| 27–29 Future/Character | PASS，policy 矩阵、三类依赖及角色 fixture |
| 30–32 排序与 hash 稳定 | PASS，排列、trace/time、不变性测试 |
| 33–35 来源/批准指针/Workflow freshness | PASS，E2E-C、前调用检查与旧阶段忽略回归 |
| 36–38 排除原因、元数据、Prompt 数据来源 | PASS，序列化/预算/Runtime 检查 |
| 39–41 Injection/next_state/HumanGate | PASS，Context injection 与既有 authority 回归 |
| 42–44 exact binding/并发/rollback | PASS，唯一 Package+Audit、旧尝试拒绝、注入审计故障 |
| 45–46 项目隔离 | PASS，候选与 SQL/API/FK 负向测试 |
| 47 NOVEL-001–005 回归 | PASS，最终全量 509 passed / 1 opt-in skipped |

独立只读 Review 分三个方向：版本/隔离、策略/预算、执行/持久化。修复了通用类型映射与计划绑定、
P0 被 reader/预算/quota 删除、缺少数据库包或旧尝试结果被接受，以及显式锁定需求/决定被普通 scope 查询遗漏。
三位 reviewer 分别复核修复，均无剩余高置信度阻塞项；策略 reviewer 独立重跑原始复现及对应测试。

## 41. Architecture Deviations

1. Ticket 的 `0006_context_engine` 与已发布 `0006_prompt_runtime` 冲突，开始前说明并顺延 0007。
2. 沿用 NOVEL-004 Task 先创建、Run claim/start 后构建 Context 的时序，READY 之前不调用模型。
3. 用独立、run 唯一的 ContextPackage 关系实现 exact reference，没有改写历史 Task/Run。
4. 为既有模拟控制阶段和独立 smoke 增加 CP-000；真实 Planning/Writing/Review/Revision 使用各自严格 Profile。
5. 选择单表 JSONB snapshot 与 provider-neutral 字节估算；没有引入 token SDK 或 Memory 表。

没有大规模重构已有基础设施。Context 不拥有审批、Workflow transition 或 Memory commit。

## 42. Known Issues

- Token 估算保守，可能比模型实际 tokenizer 更早阻塞；不用于成本计费。
- 检索按 Profile 上限执行；超额 P0 明确 BLOCKED，需要调整 Profile 版本或任务范围。
- Freshness 是短事务检查，模型调用期间允许用户变更；应用前二次检查负责丢弃过时结果，不跨网络持有数据库锁。
- Inspector 延续本地单用户权限模型，业务文本可见；多租户鉴权不属于本 Ticket。
- 查询不枚举整个数据库的所有未选择对象；excluded_items 描述已获取候选的过滤/去重/裁剪原因。
- Authority Resolver 处理结构化同一对象的冲突，不分析不同 ID 文本之间的语义矛盾。
- 计划声明未接入的依赖类型会明确 missing/block，不静默忽略。正式 Memory 类型尚不存在。
- 无已知未解决的阻塞级正确性问题。

## 43. Deferred Items

NOVEL-007 Requirement/Planning 业务、008 Writing、009 Review、010 Revision、011 Human Feedback、
012 Character/Event/Canon Memory 与 Memory Commit，均未实现。
Vector DB、Embedding、semantic RAG、Redis、Kafka、Neo4j、Frontend、真实 Agent Prompt/业务逻辑未新增。
本阶段仅复用 NOVEL-005 Provider/Prompt 基础设施，默认 Mock。等待用户 Review，不继续下一 Ticket。

## 44. Review Fixes — 2026-09-15

本轮修复用户 Review 中确认的三项 P2 问题：

1. **锁定依赖读取**：显式 ChapterPlan/ChapterVersion 依赖按 version policy 查询。
   APPROVED/EFFECTIVE 验证批准时间、有效状态和 approved pointer；LOCKED 验证 active Lock 与精确版本；
   EXACT/TARGET_VERSION 仍受 Profile 的状态、范围、未来信息策略约束。
   CP-004～CP-007 发布 v2，将显式 artifact 依赖改为 LOCKED/A1，保留所有 v1 文件与历史 hash。
   Writing 主计划与前文正文仍要求批准版本，不能用 latest/current Draft 替代。
2. **配置错误收尾**：ResultHandler 捕获 ContextService 初始化和 freshness 查询中的
   ContextConfigurationError，在同一事务完成 Run FAILED、Task BLOCKED、Workflow BLOCK 和 lease 释放。
   AgentRuntime 同样将 Context 配置错误映射为不可重试错误；没有扩大捕获数据库异常的范围。
3. **扩展候选归属**：MemoryQueryService 验证扩展候选必须为 ContextItem，且 selector_id/source_type
   与实际调用一致。不匹配时返回配置错误，不能冒充其他必需 selector；合法候选继续接受 Profile 的范围与优先级策略。

回归测试新增 11 项：

- 两类未批准但已锁定 artifact 均可驱动 Writing，普通 v1 APPROVED 策略仍拒绝它们。
- 两类依赖解锁后均使 Package stale，已有模型结果被拒绝，正文不落库。
- v1 历史包在 v2 发布后仍按原 profile/hash 执行，快照不变。
- 模型调用期间真实 JSON Profile 文件损坏，任务即时 BLOCKED、Run 结束、lease 释放、不自动重试。
- Runtime prepare/execute 的 Context 配置错误均不可重试，也不调用 Provider。
- 扩展 reader 的错误 selector、错误 source type、非 ContextItem 返回值均拒绝。
- 合法扩展 reader 仍受所属 scope 限制，不能填补缺失的其他必需项。

验证结果：

- 完整 `pytest`：509 passed / 1 opt-in skipped / 2 既有 deprecation warnings。
- `ruff check`、`ruff format --check`、`git diff --check`：PASS。
- `uv build --offline`：PASS，wheel 包含 9 个 Profile JSON 文件（历史 v1 + 新 v2）。
- 开发库 `alembic upgrade head`、`alembic check`：PASS，无新增迁移操作。
- 完整测试中的隔离 PostgreSQL migration upgrade / downgrade -1 / upgrade：PASS，旧表数据保持不变。
- 独立只读复核：通过；reviewer 另行运行 6 个 PostgreSQL 回归及 8 个 Profile/Extension 用例，未发现剩余问题。
- Docker：基础镜像元数据拉取曾两次 TLS 超时，使用 `docker pull ghcr.io/astral-sh/uv:0.9.30` 成功获取后，
  `docker compose build backend` 与 `docker compose up -d --no-deps --wait backend` 均 PASS。
  容器内验证 CP-004～CP-007 默认 v2、历史 v1 可用；health 与 health/db 均返回 HTTP 200。

本轮没有新增 Domain/ORM/迁移、依赖或环境变量配置，没有实现 NOVEL-007 及后续业务。
