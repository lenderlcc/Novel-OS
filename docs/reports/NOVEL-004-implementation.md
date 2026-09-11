# NOVEL-004 — Agent Runtime & Mock Agent

验证日期：2026-09-11。分支：`wfg/novel-004-agent-runtime`，基于 `c9b119f`。
状态：实现与 Review 修复完成，独立只读复核通过。交付分支为 `wfg/novel-004-agent-runtime`；未开始 NOVEL-005。

## 1. Implementation Summary

接入持久化 PostgreSQL 任务队列、独立 Worker、统一 AgentRuntime、MockModelProvider、
结构化结果校验和确定性事件处理。沿用 NOVEL-001 TOML 配置、NOVEL-002 Service/Repository
事务约定、NOVEL-003 Workflow/Guard/HumanGate，不重写稳定基础设施。

新增文件按职责分组：

| 文件（相对仓库根目录） | 实现 |
| --- | --- |
| `backend/novel_os/domain/agents.py` | AgentDefinition、AgentTask、AgentRun、TaskLease、Enum |
| `backend/novel_os/agents/{registry,authority,schemas,provider,runtime}.py` | 7 Agent、任务合约、权限、结构化输出、Mock 执行 |
| `backend/novel_os/models/agents.py` | 两张执行表的 ORM |
| `backend/novel_os/repositories/agent_tasks.py` | 查询、持久化、行锁、队列候选 |
| `backend/novel_os/services/{task_scheduling,task_history,agent_queue,agent_results,agent_queries}.py` | 调度、审计、领取、结果事务、只读查询 |
| `backend/novel_os/worker.py` | 独立 Worker CLI |
| `backend/novel_os/api/{agent_routes,agent_schemas}.py` | 3 个只读接口与显式 DTO |
| `backend/alembic/versions/0005_agent_runtime.py` | Frozen DDL |
| `backend/tests/core/workflow/agent_test_support.py` | 执行测试辅助函数 |
| `backend/tests/core/workflow/test_agent_*.py` | 7 组数据库、API、并发、迁移、子进程与 Review 回归测试 |
| `backend/tests/test_agent_contracts.py` | 独立于数据库的合约与配置测试 |

修改 `README.md`、`config.example.toml`、Settings、main 路由注册、Agent 包说明、Alembic
metadata 注册，以及 Workflow 的小型接入点。既有 `test_review_migration.py` 显式指定
0004 revision，继续测试原 Review 修复，避免把新的 head 当作 0004。

无新增或升级依赖，`pyproject.toml` / `uv.lock` 未修改。继续使用 Python、FastAPI、
SQLAlchemy 2.x、Pydantic、Alembic、psycopg、pytest、ruff；线程、CLI 与 JSON 使用标准库。

## 2. Agent Runtime Architecture

```text
WorkflowRuntime transition transaction
  → TaskScheduler → AgentTaskRepository → PostgreSQL
Independent Worker
  → AgentQueue claim/start (short transactions)
  → AgentRuntime → MockModelProvider → JSON/Pydantic → AuthorityValidator
  → AgentResultHandler (one application transaction)
  → fixed event mapping → existing WorkflowRuntime → Core Services
  → Repository → Database + Audit
```

Domain 不依赖 FastAPI 或 ORM；AgentRuntime 不导入 Repository、Service、ORM 或 Workflow
writer。API 返回独立 Pydantic DTO，Repository 仅 flush，不 commit/rollback。

## 3. Agent Registry

固定注册 A01_ORCHESTRATOR、A02_REQUIREMENT、A03_PLANNING、A04_WRITING、A05_REVIEW、
A06_REVISION、A07_MEMORY。每项包含 ID、name、mission、accepted_task_types、
default_capabilities、result_schema、enabled。没有拆分额外 Agent，没有业务 Prompt。

任务合约固定为本阶段 13 个 MOCK_* 类型，注册表内保存系统拥有的事件映射。

## 4. AgentTask Design

保存项目、Workflow、创建时 state/state_version、Agent/task type、objective、Chapter target_ref、
requirements、constraints、capability scope、expected schema、priority、attempt/max_attempts、
version、各阶段时间、lease owner/token/expiry/heartbeat、错误码、结果引用与安全摘要。

状态：PENDING、CLAIMED、RUNNING、SUCCEEDED、BLOCKED、FAILED、CANCELLED。
默认 priority=0、max_attempts=3。内部调度支持优先级 -100..100 与延迟可用时间；无客户端创建入口。
创建时间、available_at、租约与完成时间均取 PostgreSQL clock_timestamp，避免宿主机与容器时钟偏差。

## 5. AgentRun Design

每次 claim 创建新 run_id、attempt_number 和 lease_token；Task 仅累计尝试次数。
Run 保存 worker、状态、claim/start/finish、duration_ms、provider/model、输入输出 metadata、
error_code/error_message、result_status 和 disposition。

状态：CLAIMED、RUNNING、SUCCEEDED、FAILED、ABANDONED、CANCELLED。
成功、失败、取消、租约放弃的 Run 一旦完成即不可修改；不覆盖第一次失败记录。
执行成功但结果过期时，Run 可以是 SUCCEEDED，同时 disposition=STALE_IGNORED。

## 6. PostgreSQL Queue Design

可领取条件为 PENDING 且 available_at 已到，或 CLAIMED/RUNNING 且 lease 已过期。
按 priority 降序、available_at、created_at、task_id 排序。取消和其他终态不参与领取。
表上配置队列与 Workflow/Task 查询索引，无 Redis、消息中间件或额外队列依赖。

普通 transition 与任务创建同事务；升级前已存在的 WAITING_AGENT 实例没有任务时，
Worker 在无可领取任务的轮询中最多补建一个缺失的当前阶段任务。已有逻辑任务不会被补建覆盖。

## 7. Worker Architecture

入口：`uv run --locked python -m novel_os.worker [--once] [--config config.toml]`。
FastAPI 不启动 Worker，也不在 HTTP 请求内执行 Provider。Worker 每次执行一个任务，可运行多个进程。

claim、start、heartbeat、completion 分别使用短事务，Provider 调用位于数据库事务之外。
心跳线程只调用租约服务；Worker 不包含状态图、业务 Guard 或事件选择逻辑。
SIGINT/SIGTERM 等待当前执行结束后退出；异常或强制退出由持久化租约恢复。
CLI 在 Docker 镜像中也可用，已检查打包后的 `python -m novel_os.worker --help`。

## 8. Claim / SKIP LOCKED Design

先用 `FOR UPDATE OF projects SKIP LOCKED` 锁定候选所属 Project，再用
`FOR UPDATE SKIP LOCKED` 锁 Task。沿用 Core/Workflow 的 Project 根锁顺序，避免与审计外键锁形成反向等待。

取得 Task 行锁后重新读取状态、available_at、lease_expires_at 并比较数据库时钟；
即使选候选和锁 Task 之间 heartbeat 延长租约，也不能错误重领。claim、Run 创建及审计同事务提交。
第二段 Task 锁被占用时，排除该候选并按原顺序继续扫描；同项目或跨项目的后续可用任务
都能被领取。只有候选耗尽才返回空，保留 Project → Task 锁序，Repository 不提交或回滚事务。

## 9. Lease / Heartbeat / Recovery

默认 lease=30 秒、heartbeat=5 秒，配置校验要求 0 < heartbeat < lease。
有效执行资格同时绑定 task_id、worker_id、随机 token、attempt_number、未过期时间。
heartbeat 在锁住 Task 后核对所有条件，增加 Task version 并续租。

过期 claim/RUNNING 可恢复：旧 Run 标记 ABANDONED/LEASE_EXPIRED，新 Run 使用新的 token。
超过 3 次尝试进入 FAILED；Workflow 通过原确定性 FATAL_ERROR 路径失败。
旧 Worker 在到期后、重领后、甚至新 Worker 完成后，都不能续租或覆盖新结果。

## 10. MockModelProvider

支持 SUCCESS、BLOCKED、FORMAT_ERROR_ONCE、MODEL_ERROR_ONCE、ALWAYS_FAIL、AUTHORITY_VIOLATION、
LOW_CONFIDENCE、NEEDS_HUMAN，以及 SLOW_SUCCESS、MALFORMED_OUTPUT、QUALITY_FAIL。

ONCE 场景使用持久化 attempt_number，而非进程内计数，Worker 重启不重置错误场景。
Mock 始终返回未信任文本，经过统一 Runtime/Parser/Validator/Handler；没有绕过校验直接发送事件的后门。
没有单独 LEASE_LOST provider 场景；通过真实数据库过期、重领、迟到结果测试覆盖该语义。

## 11. AgentResult Schema

统一必填字段：task_id、status、result、confidence、assumptions、issues、proposed_changes、
memory_proposals、escalation。状态为 SUCCESS / PARTIAL / BLOCKED / NEEDS_HUMAN / FAILED。

result 为带 kind discriminator 的 ack、plan、draft、review 类型或 null。
plan/draft 字段有长度边界，review 使用 PASS/FAIL/WARN verdict，ack 显式 simulation=true。
confidence 必须为有限的 0..1 数值；列表有数量上限。所有嵌套模型均禁止额外字段。
Plan/Draft 四个文本字段共用 ArtifactText 校验：拒绝纯空白及 NUL，保留合法文本原始排版。
这些输出错误在写入 Workflow/Core 之前归为 SCHEMA_PARSE_ERROR，正常记录失败 Run 并调度重试。

## 12. Output Validation

执行前校验 task identity/scope；执行后按以下顺序检查：文本类型与 150,000 字符上限、
JSON（拒绝重复 key）、Pydantic、SUCCESS 输出 kind 与任务合约匹配、结果权限与 target scope。
Handler 只接受 ExecutionResult，并在应用事务内再次校验 AgentResult。

禁止接受 arbitrary dict、next_state、next_event、客户端伪造的 APPROVED 或 authority_level。
错误只保存已知错误码和固定安全说明，不保存原始 Provider 输出、异常字符串或 validation input。

## 13. Authority / Capability Validation

有效权限是 Agent Definition 默认权限、Task Type 所需权限、当前绑定 Workflow State 与 Task scope
的共同约束。Agent ID 本身不授予永久权限。Agent disabled、错误 task type/state/schema/scope 均拒绝。

所有 Agent 禁止 APPROVE、LOCK、UNLOCK、COMMIT_CANON、SET_WORKFLOW_STATE、DIRECT_DATABASE_WRITE。
proposed_changes 必须在交集权限内且 target_ref 与任务一致；本阶段所有 memory_proposals 拒绝。

权限失败不写入提案、不创建内容、不进入后续业务阶段，也不技术重试。
Run 保存 FAILED/AUTHORITY_DENIED，Task BLOCKED，系统 Handler 固定生成 BLOCK，进入 C90 并保留恢复位置。
这是失败控制状态，不是接受 Agent 指定的事件；只有用户显式 Resume 才重新调度当前业务阶段。

## 14. Result → Workflow Event Mapping

| Task type | SUCCESS 的确定性事件 | Review FAIL |
| --- | --- | --- |
| MOCK_INTAKE / MOCK_READY | AGENT_SUCCEEDED | — |
| MOCK_CONTEXT | CONTEXT_READY | — |
| MOCK_PLAN | PLAN_READY | — |
| MOCK_PLAN_REVIEW | PLAN_REVIEW_PASSED | PLAN_REVIEW_FAILED |
| MOCK_WRITE | DRAFT_READY | — |
| MOCK_CHECK | DETERMINISTIC_CHECK_PASSED | DETERMINISTIC_CHECK_FAILED |
| MOCK_REVIEW | REVIEW_PASSED | REVIEW_FAILED |
| MOCK_REVISE | REVISION_READY | — |
| MOCK_HANDOFF | READY_FOR_USER | — |
| MOCK_FEEDBACK | LOCAL_CHANGE | — |
| MOCK_MEMORY_PREPARE | MEMORY_CHANGESET_READY | — |
| MOCK_COMPLETION | MEMORY_COMMITTED | — |

非 SUCCESS、confidence < 0.6 或 escalation.required 触发系统 BLOCK，Task BLOCKED。
Review verdict 的判定独立于 SUCCESS 执行状态，FAIL 不能错误映射为 REVIEW_PASSED。
C14/C15 只是已有模拟交接事件，不创建 MemoryChangeSet 或提交 Canon。

## 15. Retry Design

仅模型超时/不可用、临时 Provider/基础设施错误、JSON/Schema 错误和租约失效允许技术恢复。
同 Task、新 Run；默认最多 3 次执行，available_at 按 retry_seconds × 2^(attempt-1) 退避，最多 60 秒。
重试过程不改变 Workflow state_version，也不增加其 revision/planning iteration。

预算耗尽后 Task FAILED，Workflow C91_FAILED。Review FAIL 正常完成执行，
通过 Workflow 进入 Revision 或 Replanning，计数仍由原 Workflow Engine 管理。

## 16. Cancellation Design

Workflow Cancel/离开阶段时，PENDING 和 CLAIMED 任务在 transition 事务中取消。
已领取但未开始的 Run 同时标记 CANCELLED，不能再 start。
RUNNING 可执行到 Provider 返回；结果必须重新检查 Workflow，过期则忽略。
若进程崩溃，在租约恢复时取消已不被 Workflow 期待的任务，而非重新执行。

## 17. Stale Result Protection

completion 使用 Project → Workflow → Task 锁顺序，检查 Workflow 状态、state、state_version、
project、chapter target、Task 状态及有效租约。取消、暂停、状态版本移动的结果不会更新 Workflow 或内容。
Run 保存成功或失败的执行事实及 STALE_IGNORED；Task CANCELLED，保留 result_ref 与安全摘要。

Workflow 事件继续携带 expected_state_version、origin_state，使用既有 stale/Guard 防线。
租约丢失返回 LEASE_LOST；旧 Run 的终态历史不因迟到提交而被改写。

## 18. Idempotency Design

任务逻辑唯一键为 `(workflow_instance_id, workflow_state_version, task_type)`。
Task identity/state/scope 不可变，state_version 本身已唯一定位阶段，不依赖调用端重试次数。

Run 唯一键 `(task_id, attempt_number)`，token 唯一。Run ID 同时作为发送 Workflow Event 的幂等 ID。
重复 complete 返回 DUPLICATE；并发重复处理只创建一个 Plan、一个转换和一条完成 Run。
Task 的每次更新必须 version+1，数据库 trigger 拒绝陈旧快照覆盖。

## 19. Database Tables

新增 `agent_tasks`、`agent_runs`，未新增 agent_workers 表。
Task 使用复合外键约束 Workflow/Chapter 与 Project 一致；result_ref 必须引用同 Task 的 Run。
有尝试预算、状态、优先级、租约存在性、版本和时长约束。
数据库 trigger 拒绝 Task/Run hard delete、Task identity 修改、终态 Task 修改及已完成 Run 修改。

事务边界属于应用服务：调度与 Workflow、领取与 Run、结果与 Core artifact/Workflow/Audit 原子提交。
Provider 在事务外执行。Repo 不完成事务；故障注入验证失败后 Task、Run、内容、转换及审计一起回滚。

审计复用 append-only AuditRecord，挂在 Chapter target，下含 agent_task_id/workflow_id/run_id。
覆盖创建、领取、开始、成功/失败、重试、取消、租约回收与结果忽略。
每次 heartbeat 持久化租约和 version，不逐次添加审计，避免轮询事件淹没业务历史。

## 20. API / Debug Endpoints

GET `/api/v1/agent-tasks/{task_id}`；GET `/api/v1/agent-tasks/{task_id}/runs`；
GET `/api/v1/workflows/{workflow_id}/agent-tasks`。列表使用既有 limit（1..200）/offset。
DTO 不暴露 lease_token。无新增写入接口，无 mock-execute HTTP 接口。
原 FakeExecutor HTTP 默认关闭，保留 NOVEL-003 dev/test 测试语义。

## 21. Migration

冲突已在实施前说明：请求中的 `0004_agent_runtime` 与已经发布的
`0004_workflow_recovery` 编号冲突，根因是 NOVEL-003 Review 后已有独立恢复修复迁移。
影响只在 revision 编号和迁移验证起点；覆盖旧 0004 会破坏已部署 migration lineage。

实际采用 `0004_workflow_recovery → 0005_agent_runtime`，保留 0001..0004 原文件和既有恢复语义。
0005 是 migration 序号，与 NOVEL-005 Ticket 无关。Migration 为 frozen SQL，不导入 runtime ORM/domain。
新增 Workflow `(id, project_id)` 唯一约束供 Task 复合外键使用，没有改状态机数据结构或定义。

## 22. Tests Added

新增 104 个测试用例（含后续 Review 修复新增的 14 个）：

| 文件 | 数量 | 重点 |
| --- | ---: | --- |
| `test_agent_contracts.py` | 16 | JSON 边界、NaN/Inf、尝试语义、权限、心跳配置、合法文本排版保留 |
| `test_agent_execution.py` | 14 | Registry、Task/API、Run、重试、质量失败、人工 Gate、完整流程 |
| `test_agent_authority.py` | 25 | 6 禁止权限、状态/事件伪造、scope、secret、分层边界 |
| `test_agent_leases.py` | 14 | claim 并发、SKIP LOCKED、过期/续租、崩溃、stale、旧 Worker |
| `test_agent_persistence.py` | 18 | 版本、唯一键、不可变、回滚、重复结果并发、优先级/延迟 |
| `test_agent_migration.py` | 2 | 带数据 roundtrip、旧阶段补建、metadata 对照 |
| `test_agent_process.py` | 2 | 真实独立 Python 子进程执行 pending / reclaimable Task |
| `test_agent_review_regressions.py` | 13 | 多个锁住队首仍可领取、四字段非法文本失败重试、Handler 再校验 |

使用独立 `_test` 数据库，每项数据库测试创建临时 schema；不清理或覆盖开发数据。

## 23. Concurrency Test Result

PASS：两个 Worker 同时 claim，只有一个成功、只有一个 Run；捕获 SQL 确认 SKIP LOCKED。
锁住 Task 时另一 worker 不等待；两个相同结果并发 complete，返回 APPLIED + DUPLICATE，
只生成一个版本和一次转换。过期 Task version 无法覆盖更新后的 claim。
优先级高的可用任务先取，未来 available_at 即使优先级最高也不能领取。
Review 回归补充同/跨 Project × 一个/两个连续锁住队首的四个场景，验证后续任务按序领取、
全部不可领取时返回空、被跳过任务无 Run 且保持 PENDING、释放锁后可以再次领取。

## 24. Lease Recovery Test Result

PASS：CLAIMED 与 RUNNING 到期均可恢复；新 token/new Run，旧 Run ABANDONED。
旧 Worker 迟到 SUCCESS 与 heartbeat 均不能覆盖新执行。未重领但已过期也不能提交。
真实后台 heartbeat 支撑超过租约时长的 SLOW_SUCCESS；独立子进程恢复持久化过期任务成功。
连续崩溃直到预算耗尽会结束任务与 Workflow。

## 25. Retry Test Result

PASS：FORMAT_ERROR_ONCE、MODEL_ERROR_ONCE 均 Run1 FAILED → Run2 SUCCEEDED，旧记录完全保留。
ALWAYS_FAIL 与 MALFORMED_OUTPUT 用完 3 次预算后失败。
Plan Review / Deterministic Check / Internal Review 的质量 FAIL 都进入业务改写或重规划，不技术重试。
Review 回归覆盖 objective/required_outcome/content/change_reason × 空白/NUL：首次立即记录
FAILED/SCHEMA_PARSE_ERROR 并释放租约，第二次同 Task 新 Run 成功，第一次失败历史保留。

## 26. Authority Negative Test Result

PASS：25 个权限集成负向测试。Approve、Lock、Unlock、Commit Canon、Set State、Direct DB Write
全部被拒绝；next_state/next_event、伪造 APPROVED/authority、错误任务/target/memory scope 被拒绝。
拒绝路径未改变 approved pointer。低置信/NEEDS_HUMAN 未自动批准，Provider 异常中的模拟 secret 未进入 DB/日志。

## 27. Stale Result Test Result

PASS：运行期间 Cancel、Pause 或由其他合法命令推进 state_version，随后 SUCCESS 均 STALE_IGNORED。
Workflow 不复活，不创建新 Plan/Draft，不新增业务转换。取消前未开始的任务不能 claim/start。
租约 fencing 与 Workflow stale token 两层分别验证。

## 28. Full Mock E2E Result

PASS：USER_SUBMITTED → 异步执行 → C06 Human Plan Approval → 用户批准 → C12 Human Chapter Approval
→ 用户批准 → C16_COMPLETED。正常链路 11 个 Task，每个一次成功 Run。
两个人工 Gate 都使 Worker 停止领取并等待真实用户命令；最终 Plan / Chapter current 与 approved 均为 1。
所有内容为 Mock，未做 Canon Commit。

## 29. Migration Result

2026-09-11 在开发库显式执行并通过：

```text
uv run --locked alembic upgrade head   # 0004 → 0005
uv run --locked alembic downgrade -1   # 0005 → 0004
uv run --locked alembic upgrade head   # 0004 → 0005
uv run --locked alembic check          # No new upgrade operations detected.
```

开发库 downgrade 前确认新增两表均为空。独立测试另外验证带真实 Core/Workflow/Audit/Run 数据的
roundtrip：只删除 Agent 两表，Core/Workflow/Audit 快照相同；再升级可调度旧的等待阶段。
降级删除的 AgentTask/AgentRun 内容不会恢复，审计仍保留，不建议在承载执行记录的库上随意降级。

## 30. Lint Result

`uv run --locked ruff check`：PASS / All checks passed。
`uv run --locked ruff format --check`：PASS / 105 files already formatted。
`git diff --check`：PASS。

`docker compose build backend`：PASS；`docker compose up -d --wait backend`：Healthy。
更新后的 GET `/api/v1/health` 返回 `{"status":"ok"}`，
GET `/api/v1/health/db` 返回 `{"status":"ok","database":"ok"}`。

## 31. Full pytest Result

Review 修复后重新执行 `uv run --locked pytest`：**326 passed, 2 warnings in 94.10s**。
其中新增 104、原有 222，NOVEL-001/002/003 全部继续通过，无 skip/xfail。
两条 warnings 来自既有 Starlette TestClient/httpx 与 AnyIO BlockingPortal 弃用提示。

## 32. Acceptance Criteria PASS / FAIL

| 验收项 | 结果 |
| --- | --- |
| 7 Agent Registry / Definition / Task-scoped capability | PASS |
| AgentTask / 独立 AgentRun / PostgreSQL persistence | PASS |
| Workflow 原子创建 Task / stage 幂等 | PASS |
| 独立 Worker / HTTP 无同步 Agent 执行 | PASS |
| 多 Worker claim / SKIP LOCKED / priority / available_at | PASS |
| lease / heartbeat / crash recovery / old worker fencing | PASS |
| 统一 AgentResult / Schema / Authority validation | PASS |
| Mock 必需场景 / Agent 无 Workflow 或审批写权限 | PASS |
| 系统确定性事件映射 / Guard / 用户审批边界 | PASS |
| technical retry 独立 Run / 质量失败独立于技术重试 | PASS |
| cancellation / stale result / idempotent completion | PASS |
| optimistic version / immutable history / transaction rollback / audit | PASS |
| Worker 子进程重启与既有等待阶段恢复 | PASS |
| 全 Mock E2E 经两个 Human Gate 到 C16 | PASS |
| 原有 001/002/003 回归 | PASS |
| migration upgrade/downgrade/upgrade/check | PASS（revision 0004↔0005） |
| Ruff / format / diff / Docker / health | PASS |
| 独立只读 Review，Required/Blocking 先修复 | PASS |
| 未进入 NOVEL-005，无禁止范围实现 | PASS |

## 33. Architecture Deviations

采用迁移编号 0005，原因见第 21 节。除此之外保持 API → Service → Repository → Database、
Workflow owns state、Agent owns execution、User owns approval、未来 Memory Service owns Canon 的边界。

局部接入仅在 Workflow transition 后调用 TaskScheduler，并增加要求现有应用事务的
`dispatch_in_transaction` 供结果原子组合。Agent registry/handlers 属于新增执行层，原 Guard/Dispatcher/
HumanGate/状态图/FakeExecutor 未重写。审计复用 Chapter target + metadata，不扩展 Core ObjectType。

按 `code-review-and-quality` skill 进行了两个独立 gpt-5.5 只读审查，覆盖 ownership、authority、
lease/stale race、SKIP LOCKED、事务、重试、幂等、取消、Repo commit 与范围。
Required 发现与修复：

1. Authority failure 曾使 Task FAILED 但 Workflow 仍 WAITING_AGENT。已改为明确 BLOCKED，保留错误与恢复位置；复核通过。
2. 租约测试的一行 SQL 超过 Ruff 行长。已拆分字符串，全量 Ruff 检查通过。
3. 后续整体 Review 发现队首 Task 单独被锁时，原两段领取查询直接返回空。已增加候选排除与继续扫描，
   保持根锁顺序；同/跨项目、连续锁头的四个回归场景及独立复核均通过。
4. 后续整体 Review 发现 Plan/Draft 的空白或 NUL 文本通过 Schema，却在完成事务中失败并留下 RUNNING。
   已为四个字段增加 ArtifactText，错误走 SCHEMA_PARSE_ERROR 技术重试；覆盖八个非法字段组合、
   Handler 对 model_copy 结果再校验，以及合法 Unicode/排版保留，独立复核通过。

补建旧阶段任务路径也经独立只读复核；最终无剩余 Required/Blocking。

## 34. Known Issues

- 原有两条 TestClient 依赖弃用提示仍在，本阶段未升级依赖。
- 当前为本地单用户 Prototype；无登录、多租户或真实模型凭据管理。仍使用回环地址与既有用户控制面。
- 一个 Worker 同时执行一个任务；同 Project 写事务沿用根锁串行化。未做生产规模队列压测或 Worker supervision。
- Mock 是受信任的进程内实现，没有第三方 Agent 代码执行沙箱或真实 Provider 硬超时/取消协议；后续真实集成必须另行设计。
- 只保存安全执行 metadata；不存原始输出、Prompt 或完整 Result body。Plan/Draft 经现有 Core 服务保存版本化 Mock 内容。
- 无已知阻塞 NOVEL-004 验收的问题。

## 35. Deferred Items

未实现真实 OpenAI/Claude/Gemini 调用、业务 Agent Prompt、Prompt Registry/Compiler/Lineage、
Context Engine、Memory Retrieval、Character/Event Memory、Canon Commit、Vector DB、Redis、Kafka 或前端。
无 agent_workers 表、生产调度平台、自动启动守护、真实 Provider 超时/流式协议。
这些不作为本 Ticket 的隐式后续工作；本阶段到此停止，等待用户 Review。
