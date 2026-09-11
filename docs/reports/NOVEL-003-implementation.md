# NOVEL-003 — Chapter Workflow Engine Implementation

日期：2026-09-11
分支：`wfg/novel-003-workflow-engine`
基础提交：`fa62afa`（已审查的 NOVEL-002）
状态：实现与验证完成，等待用户 Review；未进入 NOVEL-004。

## 1. Implementation Summary

实现 deterministic Chapter Workflow Engine，以版本化转换表控制 C00–C16 与
C90/C91/C92 共 20 个状态。使用同步 FakeExecutor / Fake Events 验证流程，包含两个
Human Gate、规划返工、Revision Loop、技术重试、阻塞、暂停、恢复、取消及完成。

新增五张 Workflow 表，复用现有 ChapterPlan / ChapterVersion / AuditRecord。
新增产物遵循版本、审批、锁与不可变规则。没有接入真实 Agent、LLM、Memory 或 Canon。

Review 的四项问题已修复：上游 Plan 变更使旧正文阻塞（包含质量失败进入 Revision 的路径）；
多次阻塞保留阶段恢复意图；既有实例不依赖当前 YAML；ORM 枚举 CHECK 名称与迁移一致。
详见 `docs/reports/NOVEL-003-code-review.md` 的修复复验记录。

新增依赖仅 `PyYAML >=6,<7`，锁定 `6.0.3`；现有依赖版本不变。YAML 使用 SafeLoader，
拒绝重复键、任意 Python 对象构造、不合法图、未知 Guard / effect、缺失强制审批 Guard。

主要新增文件：

- `backend/novel_os/domain/workflow.py`
- `backend/novel_os/models/workflow.py`
- `backend/novel_os/repositories/workflows.py`
- `backend/novel_os/workflow/{definitions,runtime,guards,audit,fake_executor}.py`
- `backend/novel_os/workflow/definitions/chapter-production.v1.yaml`
- `backend/novel_os/api/{workflow_routes,workflow_schemas}.py`
- `backend/alembic/versions/0003_workflow_engine_chapter_workflow_engine.py`
- `backend/alembic/versions/0004_workflow_recovery.py`（NOVEL-003 Review 修复）
- `backend/tests/core/workflow/`（测试与 fixture）

修改范围：`main.py` 注册路由、`alembic/env.py` 注册 metadata、TOML 配置增加默认关闭的
FakeExecutor 开关、版本 Service 增加事务内组合入口、原 migration 测试显式验证 0002、
README / pyproject / uv.lock。Review 修复未改写已有 0001 / 0002 / 0003 migration。

## 2. Workflow Architecture

```text
API（独立 Pydantic DTO；可信 actor 装配）
  → WorkflowRuntime（application Service / transaction owner）
      → EventDispatcher（已绑定的 Definition）
      → GuardRegistry（读取真实 Core Domain）
      → PlanningService / ChapterVersionService（版本创建与审批）
      → TransitionAudit / HumanGate
      → WorkflowRepository / CoreRepository（flush，不 commit）
          → PostgreSQL
```

Domain 使用 stdlib dataclass / Enum，无 FastAPI、SQLAlchemy、Pydantic 依赖。
Repository 显式转换 Domain 与 ORM，ORM 不作为 API DTO。
FakeExecutor 只返回带 origin token 的 EventCommand，没有 Repository，也没有 next_state。

## 3. Workflow Tables

| 表 | 作用与关键约束 |
| --- | --- |
| workflow_definitions | `(id, version)` 主键；规范化 JSONB、摘要、创建时间；不可更新或删除 |
| workflow_instances | 绑定定义与 Chapter；state_version、状态、计数、产物指针、恢复位置及 resume_new_stage；同 Chapter 仅一个活跃实例 |
| workflow_events | 全局 event_id 主键；命令指纹、actor、origin_state、预期版本、payload、持久化结果；不可更新或删除 |
| workflow_transitions | 每次转换的前后状态/版本、Guard、原因、audit_record_id；event_id 与实例内 to_version 唯一 |
| human_gates | 具体 artifact ID/version、Gate 类型和状态、决定、操作者、决定事件；同实例仅一个 WAITING Gate |

实例使用复合外键确保 Chapter 归属正确、Plan/Draft 版本属于同一 Chapter；Gate 决定与
Transition 的复合事件外键确保事件属于同一实例。数据库 trigger 禁止五张表硬删除，
保护定义、事件、转换历史、Gate 绑定及已完成决定；实例更新必须 state_version + 1，
终态不可更新。既有 AuditRecord append-only trigger 保持不变。

## 4. Workflow Definition Format

新实例的默认定义来源：`backend/novel_os/workflow/definitions/chapter-production.v1.yaml`。
放在 Python package 中，避免 Docker/wheel 缺失仓库外部资源；已验证 wheel 与镜像构建。

```yaml
id: chapter-production
version: 1
initial_state: C00_CREATED
max_technical_retries: 2
simulation: true
transitions:
  - source: C06_PLAN_APPROVAL
    event: USER_APPROVED
    target: C07_WRITING
    actor: USER
    guards: [plan_approved]
```

WorkflowDefinitionLoader 校验并生成规范化正文和 SHA-256 摘要。
WorkflowDefinitionRegistry 按 `(id, version)` 注册，拒绝同版本不同正文。
实例创建时在数据库保存定义快照，后续加载绑定的持久化版本，不跟随当前 YAML/Registry。
定义 v2 注册后，既有 v1 实例仍使用 v1 的重试预算，测试已覆盖。
Registry 延迟到创建新实例时加载；YAML 缺失/无效时，既有实例仍可读取、审批、取消及完成，
创建命令重放仍返回原结果。新建实例返回 INVALID_DEFINITION，不影响已绑定定义。

参考：[PyYAML SafeLoader](https://pyyaml.org/wiki/PyYAMLDocumentation)。

## 5. State Machine Implementation

普通转换唯一依据是定义中的 `(source, event)` 与 actor / Guard；状态实际写入只在
WorkflowRuntime 的受控转换方法中完成。创建固定为 C00；控制事件由 Runtime 独立校验。
API 没有任意 state/status 更新接口。

Happy Path：

```text
C00 → C01 → C02 → C03 → C04 → C05 → C06 → C07 → C08
    → C09 → C11 → C12 → C14 → C15 → C16
```

其他路径：C05 REVIEW_FAILED / PLAN_REVIEW_FAILED → C04；C06 USER_REJECTED → C04；
C08 DETERMINISTIC_CHECK_FAILED / C09 REVIEW_FAILED → C10；C10 REVISION_READY → C08；
C12 USER_REJECTED → C13；C13 LOCAL_CHANGE → C10、CHAPTER_REPLAN_REQUIRED → C04。

非法事件拒绝且不改状态。进入 Planning 增加 planning_iteration_count，PLAN_READY 成功时
创建新的 Plan；进入 Revision 增加 revision_count，REVISION_READY 创建新正文。
返工开始到产物返回之间不会伪造一个已完成的新版本。

## 6. Guard Implementation

GuardRegistry 注册 `writable`、`plan_current`、`plan_approved`、`draft_current`、
`draft_approved`。普通业务转换总是先检查 writable；暂停/取消等控制操作有独立规则。

- writable：读取 Project / Chapter 生命周期，检查真实 Project / Chapter 锁。
- current：Workflow 绑定版本必须等于 Chapter 当前版本，并读取对应版本记录及锁。
- approved：绑定版本必须同时匹配 current、approved pointer，记录具有 approved_at
  且状态为 APPROVED / LOCKED。
- Plan Guard 调用已有 PlanningService 校验真实 locked_dependencies。
- draft_current / draft_approved 先核验绑定的 approved Plan；上游变更立即阻塞并回到 C04。
- 进入 C10 Revision 强制检查 draft_current，兼容持久化 v1 中没有声明该 Guard 的失败边。
- 产物创建再次经过既有 Service 的锁、版本和引用校验。

从不相信 `approved=true`。进入 Writing 与 Writing/Revision 产物提交均检查真实 Plan
审批；正文后续推进、章节验收及模拟 Memory 步骤同时检查绑定 Plan 的有效性和正文版本。
Plan 失效时不批准旧正文、不记质量返工；保存 BLOCKED / STALE Gate 和审计后重新规划。

## 7. Human Gate Implementation

两个类型：PLAN_APPROVAL（C06）、CHAPTER_ACCEPTANCE（C12）。
Domain 定义 CREATED / WAITING / APPROVED / REJECTED / MODIFIED / CANCELLED / STALE。
进入 Gate 状态时原子创建 WAITING 记录；CREATED 保留为领域状态，当前无独立持久化中间步骤。

Gate 绑定 artifact_id、artifact_version、opened_state_version。只有 USER 可提交
APPROVE / REJECT / MODIFY / REQUEST_ALTERNATIVE / CANCEL。APPROVE 在当前事务内调用
版本 Service 完成真实审批，再由状态机审批 Guard 放行。MODIFY / REQUEST_ALTERNATIVE
记录 MODIFIED，并分别走重规划或反馈诊断；不直接修改已批准内容。

审批需同时匹配 expected_state_version 与 expected_artifact_version。实际产物已变更时，
原子保存 STALE Gate、BLOCKED Workflow 和事件/审计后返回 409。恢复后重新进入规划或正文检查。
重复同 event_id 返回原结果；新 event_id 再次操作已决定 Gate 被拒绝。
暂停恢复复用原 WAITING Gate，取消/失败关闭等待中的 Gate。

## 8. Idempotency Design

每个命令显式携带 UUID event_id。workflow_events 保存完整命令指纹、可信 actor 与返回快照。
在实例版本检查之前查重；同命令重复返回既有结果并标记 duplicate，不创建任何重复副作用。
相同 ID 但命令、actor 或 workflow 不同返回 IDEMPOTENCY_CONFLICT。
request_id 不参与指纹，网络重试允许新 request ID。

包括创建 Workflow、普通事件、控制事件、Fake 执行、Gate 决定。Fake HTTP 调用保存原模拟
请求，而非从最新实例重新生成命令，保证重放结果稳定。失败事务不留下部分事件记录。

## 9. Optimistic Concurrency Design

每个新事件提供 expected_state_version；成功转换恰好增加一次 state_version。
遵循 NOVEL-002 的锁顺序：Project root SELECT FOR UPDATE → Workflow 行锁 → 读取产物/Gate。
因此 Core mutation、Workflow mutation 和审批可使用同一一致性边界，不引入反向锁顺序。

两个并发不同事件看到相同版本时，一个成功、另一个 VERSION_CONFLICT / 409；同 event_id
并发时，一个处理、一个返回 duplicate。数据库唯一约束作为额外保护。
不同 Project 可并行；同 Project 的写入继续串行化，这是既有架构的吞吐限制。

## 10. Retry vs Revision Design

| 字段 | 含义 |
| --- | --- |
| retry_count | 累计技术失败次数，不包含质量返工 |
| state_retry_count | 当前执行阶段技术重试预算；v1 允许两次重试，第三次技术失败进入 FAILED |
| revision_count | 每次进入 C10 增加，包括内部评审失败、检查失败和局部反馈 |
| planning_iteration_count | 首次进入 C04 为 1；重规划增加，过期 Plan 恢复重规划也增加 |

技术失败不创建 Plan/Draft，不增加业务返工计数。新执行阶段重置 state_retry_count，
累计 retry_count 保留；暂停及同阶段阻塞恢复不刷新技术重试预算。

## 11. Block / Fail / Cancel Design

BLOCKED 保存 resume_state / resume_status、resume_new_stage、block_reason 和待重查 Guard。
锁、缺失依赖、缺少审批或外部条件均为可恢复阻塞。Resume 重查条件；仍不满足则继续 BLOCKED。
过期 Plan 恢复到 C04，新正文恢复到 C08，重新检查/评审/审批。
resume_new_stage 独立于 Guard，第二次锁阻塞不会覆盖阶段进入语义；成功恢复后清除。
新阶段恢复增加对应返工计数并重置阶段技术预算，同阶段恢复保留预算；累计技术失败不清零。

PAUSED 保留当前业务状态；Resume 恢复原运行状态。Cancel 可从非终态进入 C92，并关闭等待
中的 Gate。普通非法事件返回 ILLEGAL_TRANSITION；持久执行失败、fatal executor error、
不合法绑定定义和损坏的 state/status 组合进入 C91_FAILED。

C16_COMPLETED / C91_FAILED / C92_CANCELLED 为终态，拒绝普通事件和 Resume。

## 12. Stale Result Protection

Executor Result 绑定 origin_state + expected_state_version。
已取消、已离开原状态、离开后又返回同名状态，以及暂停之后的旧结果都不能推进。
Runtime 保存结果为 STALE_IGNORED，error_code 为 VERSION_CONFLICT；HTTP 返回统一 409。
不增加 state_version、counter，不创建 artifact、Gate、Transition 或 Audit；只保留事件证据。
重复旧结果依然幂等。

## 13. API Endpoints

| 方法 | 路径 |
| --- | --- |
| POST | /api/v1/workflows/chapter |
| GET | /api/v1/workflows/{workflow_id} |
| POST | /api/v1/workflows/{workflow_id}/events |
| POST | /api/v1/workflows/{workflow_id}/pause |
| POST | /api/v1/workflows/{workflow_id}/resume |
| POST | /api/v1/workflows/{workflow_id}/cancel |
| GET | /api/v1/workflows/{workflow_id}/history |
| GET | /api/v1/workflows/{workflow_id}/human-gates |
| POST | /api/v1/human-gates/{gate_id}/decision |
| POST | /api/v1/workflows/{workflow_id}/fake-execute |

列表使用既有 limit（1–200）/ offset。输入 extra=forbid，拒绝 actor、authority、status、
next_state 等伪造字段。普通 events 仅接收用户控制事件；模拟结果使用单独 dev 入口。
`workflow_fake_executor_enabled` 默认 false，来自 TOML 文件，关闭时 fake-execute 返回 404。

调用示例、配置与完整演示步骤见仓库 README。HTTP 继续使用既有统一错误结构和 X-Request-ID。

## 14. Migration

`0002_core_domain → 0003_workflow_engine → 0004_workflow_recovery`。
迁移冻结 DDL，不导入运行期 ORM/Domain。0003 新增五张表、索引、约束与
`novel_guard_workflow()`；Review 修复不改写旧 migration。

0004 增加 resume_new_stage，利用旧 blocked_guard 和不可变 Transition/Audit 回填恢复语义，
包括被第二次阻塞覆盖的旧标记；不改 state_version、事件、转换或审计历史。
更新实例 trigger 的可变字段白名单，并以 CHECK 限制此标记只能存在于 BLOCKED 实例。
降至 0003 时将未完成的阶段恢复意图转回旧表示，移除字段并恢复旧 trigger，保留所有业务数据。

仅 0003 降至 0002 时删除五张表和新 trigger/function，保留全部 Core Domain 表与 AuditRecord。
审计以 Chapter 为目标，JSON 中记录 workflow_id / state_version / event_id / human_gate_id，
故 downgrade 无需删除旧审计或改动 ObjectType enum。重新 upgrade 不恢复被删的 Workflow 数据。

## 15. Tests Added

新增 99 项 Workflow 测试（原 80 项，加 Review 回归 19 项），按文件分为：

- `test_paths.py`：完整流程、Plan 返工、Revision、反馈、暂停/阻塞恢复、取消、终态、重试预算。
- `test_safety.py`：伪造字段、AI/System 审批拒绝、真实审批 Guard、过期审批/结果、幂等、事务回滚。
- `test_guards.py`：Project / Chapter / Plan 锁及 locked_dependencies。
- `test_workflow_concurrency.py`：并发不同事件、并发重复事件、并发 Gate 审批。
- `test_definition.py`：Safe YAML、重复键、定义图校验、不可变注册、版本绑定、Domain 无框架依赖。
- `test_workflow_persistence.py`：Migration 往返、历史/绑定保护、禁止硬删除、Repository 无提交、
  应用单次 durable commit、定义损坏、state/status 损坏、单 Chapter 活跃实例唯一性。
- `test_workflow_review_regressions.py`：六阶段 Plan 失效与两条质量失败边、阻塞重放无重复审计、
  重新规划/审批与历史保留、多次锁阻塞的恢复计数、YAML 缺失/无效下既有实例读写和创建重放。
- `test_review_migration.py`：0004 三类旧恢复数据往返、历史保持、trigger 恢复、
  metadata CHECK 名称与迁移一致、PostgreSQL 独立 schema 的 metadata 建库。

集成测试使用实际 PostgreSQL 独立 `_test` 数据库的临时 schema；结束后仅清理各自 schema。
原有 123 项测试继续保留，包括 NOVEL-002 immutable content、版本审批与回滚测试。

## 16. Happy Path Result

PASS。C00 → C16 顺序精确匹配 15 条持久化 Transition（包含创建 C00），state_version 1–15。
两个 Gate 均 APPROVED；Chapter 的 Plan 和正文 current/approved pointer 均为 1。
每条 Transition 均可关联同一 Workflow 的 Event 和既有 AuditRecord，request_id 保持一致。
C14 / C15 不改变正文集合，不新增任何 Memory/Canon 表。

## 17. Failure Path Results

PASS。覆盖：非法转换、未审批 Plan、伪造审批字段、AI/System 审批、Plan Review 失败、
内部 Review 失败、用户拒绝/修改/替代方案、反馈重规划、真实锁阻断、依赖解锁、过期 Gate、
已批准正文后出现新 Draft、技术失败耗尽、fatal failure、定义损坏、状态组合损坏、终态拒绝。
补充覆盖上游 approved Plan 变更后的成功/失败事件、验收和完成阻断、反复锁阻塞，以及当前
YAML 无效/丢失的隔离。旧正文审批和内容保持不变，重新规划产生新 Plan / Draft 后才可完成。

失败注入验证产物已创建后审计存储报错，以及审批后 Transition 存储报错：整个事务回滚，
无遗留产物、批准指针、Gate 决定、事件或审计。

## 18. Concurrency Result

PASS。真实 PostgreSQL、两个独立 Session、线程 Barrier 同步起跑。

- 不同 event_id / 同 expected_state_version：1 个成功、1 个 VERSION_CONFLICT，只增加一次版本。
- 相同 event_id：1 个成功、1 个 duplicate，只增加一次 Transition / Event。
- 同 Gate 两次并发审批：1 个成功、1 个 VERSION_CONFLICT，只批准一次 Plan 并进入一次 Writing。

## 19. Idempotency Result

PASS。创建、Fake 产物、Human Gate 决定重复提交前后逐表比较计数，Audit、Plan、正文、Gate、
Event、Transition 均无重复增加；重复响应使用原始 Workflow 快照。
同 ID 修改命令被拒绝，已决定 Gate 使用新事件再审批也被拒绝。

## 20. Migration Result

2026-09-11 在本机开发 PostgreSQL 执行：

| 命令（backend 目录，uv run --locked） | 结果 |
| --- | --- |
| alembic upgrade head | PASS，开发库已应用 0004，无待执行迁移 |
| alembic downgrade -1 | PASS，0004 → 0003 |
| alembic upgrade head | PASS，0003 → 0004 |
| alembic check | PASS，No new upgrade operations detected |

首次 0003 → 0004 升级也已成功。执行本轮往返前确认开发库 Workflow 实例为 0；
带真实 Chapter / Plan / Workflow / Audit 的 0003 和 0004 往返测试在隔离测试 schema 中执行，
确认 0004 回填保留所有历史和状态版本，0003 降级保留 Core Domain 与 AuditRecord。
开发库最终 head 为 `0004_workflow_recovery`。此 revision 编号不表示开始 NOVEL-004 Ticket。

## 21. Lint Result

- `uv run --locked ruff check`：PASS。
- `uv run --locked ruff format --check`：PASS，79 files already formatted。
- `git diff --check`：PASS。
- `uv build --wheel`：PASS；检查 wheel 包含 versioned YAML。
- `docker compose build backend`：PASS；沿用既有 Dockerfile，无新基础设施。

全量 `uv run --locked pytest`：222 passed，2 个既有依赖弃用警告，45.74 秒。
本地 Docker backend 重建并启动后 health / health/db 均为 200，OpenAPI 包含 10 个 Workflow 接口。
镜像内验证 packaged chapter-production v1 定义可加载。Review 回归 19 项全部通过。

## 22. Acceptance Criteria PASS / FAIL

| 用户要求 | 结果 |
| --- | --- |
| Happy Path → C16 | PASS |
| Illegal state transition rejected | PASS |
| 未批准 Plan 不能进入 Writing | PASS |
| AI actor 不能批准 Human Gate | PASS |
| 用户批准 Plan 后可 Writing | PASS |
| Plan Review fail 回 Planning | PASS |
| planning_iteration_count 增加、完成返工创建新 Plan | PASS |
| Internal Review fail → Revision | PASS |
| revision_count 增加 | PASS |
| Revision → deterministic check → review | PASS |
| 用户拒绝 → Feedback Diagnosis | PASS |
| 局部反馈 → Revision | PASS |
| Block → Resume | PASS |
| Pause → Resume | PASS |
| Cancel | PASS |
| Completed 终态保护 | PASS |
| Cancelled 终态保护 | PASS |
| Duplicate event 幂等 | PASS |
| 并发 state_version conflict | PASS |
| Stale executor result 忽略且 HTTP 409 | PASS |
| Human Gate 重复决定拒绝/幂等 | PASS |
| Definition version binding | PASS |
| Guard 读取真实 Domain | PASS |
| Transaction rollback | PASS |
| Transition audit completeness | PASS |
| Domain/API/Service/Repository 边界 | PASS |
| 配置文件、无环境变量配置扩展 | PASS |
| Migration upgrade / downgrade / upgrade | PASS |
| pytest / Ruff / git diff --check | PASS |
| Plan 变更阻断旧正文成功/失败事件、审批及完成 | PASS |
| 多次阻塞保留新阶段/同阶段恢复语义与预算 | PASS |
| 当前 YAML 失效不影响既有实例 | PASS |
| ORM CHECK 命名合法且与迁移一致 | PASS |
| 不进入 NOVEL-004 | PASS |

## 23. Architecture Deviations

没有改变已确认的架构边界。以下为局部实现决策：

1. **跨用例事务组合**：NOVEL-002 的版本创建和审批原本各自开启事务。Human Gate 审批与
   Workflow/Audit 必须原子提交，因此提取 `create_version_in_transaction` /
   `approve_in_transaction`，保留原公开接口和全部校验。入口要求已有事务，重新获取
   Project root lock，保留版本/锁/引用检查；审批仍 require_user。
2. **Audit 复用**：Workflow 是 Chapter 上的应用流程，AuditRecord 目标使用 CHAPTER，
   额外 JSON 保存 Workflow/Gate 标识；WorkflowTransition 持有 audit_record_id。
   避免扩展已冻结 ObjectType 及 downgrade 时破坏审计历史。
3. **YAML 位置**：采用 Python package 资源路径，而非根目录建议示例，确保 wheel/Docker 自包含。
4. **应用层位置**：WorkflowRuntime 在 `novel_os/workflow/` 内承担 application Service 职责，
   API 只调用其用例方法。事务依旧由应用层拥有，Repository 没有 commit。
5. **恢复语义**：过期产物回到规划/检查阶段，保留所有旧版本；不会恢复到一个可批准旧内容的 Gate。

按 code-review-and-quality 进行独立模型审查，并对后续 Review 发现的四项缺陷补充修复与回归。
其中独立复验补出的质量失败边也已加入 R1 修复范围。审查不替代用户最终 Review。

事务语义参考：[SQLAlchemy Transaction 文档](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)。

## 24. Known Issues

- 未发现本 Ticket 范围内的未解决阻塞问题。
- 两个既有弃用警告来自 Starlette TestClient 的 httpx 兼容路径和 AnyIO BlockingPortal 别名；
  不影响本轮测试通过，本次不跨范围升级依赖。
- 继续采用本地单用户控制面，没有登录或多用户隔离；FakeExecutor HTTP 入口默认关闭。
- 没有后台调度/消息投递，重启后状态、历史和幂等结果保留，但需显式提交下一事件。
- 同 Project 写入继续串行化；未执行跨主机吞吐或长时间负载测试。
- BLOCK / PAUSE / RESUME、Gate 和 API 入口均有覆盖；没有把每一种枚举组合穷举为测试。
- 0004 → 0003 保留业务数据；若继续 0003 → 0002，Workflow 数据会删除，旧 AuditRecord
  保留其 Workflow UUID 历史，不恢复已删除实例。

## 25. Deferred Items

真实 Agent Runtime、worker 调度、LLM Provider、Prompt Runtime、Context Engine、Requirement /
Planning / Writing / Review / Revision / Memory Agents、MemoryChangeSet、Canon Commit、
Vector DB、Redis、Kafka、Frontend，以及后续多用户授权。

C14 / C15 只保留本 Ticket 要求的状态和 Fake 事件。没有实现任何 NOVEL-004 或后续业务功能。
工作停留在本分支等待 Review，不自动继续后续 Ticket。
