# Novel OS — 提交 main 前整体代码审查

日期：2026-09-10。范围：现有 NOVEL-001 基础设施与 TOML 配置修复、NOVEL-002 Core Domain & Persistence。未扩展到后续 Ticket。

## 结论

审查发现七项需要修复的问题，均已修复并补充回归验证。本次新增 21 个测试实例，全量结果为 **123 passed**；Ruff、格式、迁移升降级和 diff 检查通过。当前范围没有已知未处理的 Required 缺陷。

按 code-review-and-quality 流程，从正确性、可读性、架构、安全边界、性能五个维度检查。主审覆盖 API / Service / 事务并负责复现与修复；独立复核分别覆盖版本/锁/数据库约束与配置/容器/日志基础设施。修复后再次核对对应补丁。

## 已修复问题

### 1. P1：Project 更新写入无法被响应 DTO 接受的标签数量

- 位置：`backend/novel_os/api/core_schemas.py` 的 `ProjectUpdate.tags`。
- 触发：PATCH Project 时提交 101 个 tags。
- 原行为：更新输入没有 100 个的上限，Service 成功提交；响应模型继承的上限校验随后失败，返回 500。已持久化记录也会使后续 Project 查询/列表的响应校验失败。
- 修复：新增共享 `TagsValue`，创建、更新和响应使用一致的最大长度约束。
- 验证：回归测试先得到 500；修复后返回 422，Project 内容与版本、审计记录均不变。

### 2. P2：Project 更新丢失用户提供的审计原因

- 位置：`backend/novel_os/api/core_routes.py` 的 `update_project`，`backend/novel_os/services/projects.py` 的 `ProjectService.update`。
- 触发：PATCH 提交非默认 `reason`。
- 原行为：API 接受字段，但没有传给 Service，AuditRecord 永远记录固定字符串 `Update project`。
- 修复：将已验证的 reason 传入用例，并用于同事务内的 UPDATE 审计。
- 验证：回归测试先断言失败；修复后 AuditRecord 保留原始用户原因。

### 3. P2：章节序号超过数据库整数范围时返回 500

- 位置：`backend/novel_os/api/core_schemas.py` 的 `ChapterInput`，`backend/novel_os/services/projects.py` 的 `ChapterService.create`。
- 触发：提交 `sequence = 2147483648`。
- 原行为：Pydantic 只校验正整数，写入 PostgreSQL Integer 时发生 DataError，返回 500。
- 修复：Domain 明确 `MAX_CHAPTER_SEQUENCE = 2**31 - 1`，API 与 Service 均校验支持范围；不修改表结构。
- 验证：溢出值由 500 改为 422 且不创建章节；`2147483647` 边界值仍可创建。

### 4. P2：数据库允许在批准/锁定转换的同一语句中更改内容

- 位置：`backend/alembic/versions/0002_core_domain_add_core_domain_persistence.py` 的 `GUARD_FUNCTION`。
- 触发：对 PROPOSED Requirement 执行同一 UPDATE，既修改 content 又设为 APPROVED；或对 Decision 同时修改 decision 并设为 LOCKED。
- 原行为：trigger 只查看 OLD 的批准时间和 locked 值，未保护这次转换；两种 SQL 均能成功。
- 影响：当前 Service 不执行这种组合更新，但持久化层未能阻止脚本或未来 Repository 将审批/锁定和内容修改混在一起，破坏版本绑定。
- 修复：OLD 或 NEW 任一侧已批准/锁定时都比较不可变 payload，同时保留纯生命周期元数据转换的能力。
- 验证：新增 approve / lock 两项真实 SQL 回归，先复现未抛出异常；修复后均由数据库拒绝，记录与转换前完全相同。正常批准、锁定、释放及取代生命周期继续通过。
- 迁移处理：0002 尚未提交或发布，直接修正这份初始迁移；开发库确认八张表均为空后重新升降级，安装最终 trigger。未添加无关 revision。

### 5. P2：核心集成测试丢弃 PostgreSQL options 并绕过默认超时

- 位置：`backend/tests/core/conftest.py`。
- 触发：隔离 schema 时用 search_path 覆盖整个 URL options；无自定义 options 时也会使 Database 不再注入默认 statement_timeout。
- 原行为：真实查询发现默认 statement_timeout 为 0；配置的 lock_timeout=1700 / statement_timeout=2300 也变为 0。
- 修复：保留原 options；若缺失先应用 Settings 的默认 statement_timeout，最后追加安全生成的随机 search_path。
- 验证：新增真实 PostgreSQL 测试，检查默认 3000ms、自定义 1700ms / 2300ms 及独立 schema 都生效。

### 6. P2：移除测试库配置后残留旧 Docker 测试凭据

- 位置：`backend/novel_os/infrastructure/prepare_docker.py`。
- 触发：同一输出目录先生成含 test_database_url 的配置，再移除该字段重新生成。
- 原行为：旧 `postgres-test` 目录和密码仍存在，test profile 仍可从旧文件启动。
- 修复：验证全部输入并成功生成当前配置后，清理当前配置不再包含的已知测试服务目录；保留开发库配置。
- 验证：回归先复现目录仍存在；修复后目录消失、开发凭据和 backend TOML 保留。README 说明已经运行的测试容器仍须显式停止；生成器不自动操作 Docker。

### 7. P2：本地 Compose 接受不支持的加密连接条件

- 位置：`backend/novel_os/infrastructure/prepare_docker.py`。
- 触发：开发库或测试库 URL 使用 sslmode=require / verify-ca / verify-full、证书等 ssl 参数、channel_binding=require 或 gssencmode=require。
- 原行为：随项目提供的 PostgreSQL 未启用相应加密能力，但生成器仍生成这些 URL，随后连接失败。
- 修复：本地 Compose 准备阶段明确拒绝该配置，并在修改 runtime 之前完成全部校验。直接连接外部 PostgreSQL 的 Settings / Database 路径继续保留完整 TLS 参数。
- 验证：十二个开发/测试 URL 组合均在准备阶段抛出清晰 ValueError，既有 runtime 文件保持原样；原有外部 TLS 参数透传测试继续通过。

## 架构及边界复核

| 维度 | 结果 |
| --- | --- |
| 分层 | API → Service → Repository → Database；Domain 无 FastAPI / SQLAlchemy 依赖；ORM 不直接作为 DTO |
| 事务 | Repository 无 commit；Service 控制事务；审计失败使新版本、指针和旧审批状态一起回滚 |
| 版本 | 历史记录保留；正文 immutable；current / approved 分离；审批绑定 expected_version |
| 并发 | 同 Project 行锁串行化写入；两个相同 expected_version 的正文创建请求得到一个 201、一个 VERSION_CONFLICT / 409 |
| 锁 | 检查目标、父级以及声明的直接引用范围；释放保留记录并恢复原 authority / status |
| 客户端权限 | 服务端生成 actor、status、authority、version、approval 字段；客户端伪造字段被拒绝 |
| 数据保护 | 核心表不 hard delete，审计不更新，数据库唯一约束及版本指针外键生效 |
| 配置及日志 | 文件配置不接受环境变量覆盖；运行凭据不进入 Git/镜像；统一错误不泄露 SQL/密码；request ID 和结构化日志保留 |
| 性能 | 列表分页；跨 Project 独立写入；未做压力测试或同项目锁粒度优化 |
| Scope | 未新增 Workflow、Agent、LLM、Memory、Frontend 或其他后续功能 |

## 最终验证

| 检查 | 实际结果 |
| --- | --- |
| `uv run --locked pytest` | 123 passed, 2 warnings in 11.25s |
| `uv run --locked ruff check` | All checks passed |
| `uv run --locked ruff format --check` | 58 files already formatted |
| `uv run --locked alembic upgrade head` | PASS |
| `uv run --locked alembic downgrade -1` | PASS，0002 → 0001 |
| `uv run --locked alembic upgrade head` | PASS，0001 → 0002 |
| `uv run --locked alembic check` | No new upgrade operations detected |
| `git diff --check` / staged diff check | PASS |

新增回归位于 `tests/core/test_review_regressions.py`、`tests/core/test_connection_options.py`，以及现有 `test_persistence.py` / `test_config.py`。开发库升降级前确认全部业务表为空；所有失败复现与业务写入测试均使用隔离测试 schema 或临时目录。

Docker 镜像已按最终代码重建，运行 smoke 检查保留健康接口、Project 列表和 OpenAPI；容器迁移 head 为 0002_core_domain。

## 保留的限制

- 本地单用户 `local-user` 适配器，未实现登录、多租户或真实 Agent 身份认证。
- 同 Project 写入采用较粗粒度的行锁，尚无负载测试结果。
- 两条既有依赖弃用警告来自 Starlette TestClient / httpx 和 AnyIO BlockingPortal；没有为消除警告升级依赖。
- 审计保存状态与指针快照，正文通过不可变版本关联；没有通用字段级变更日志、幂等键系统或依赖失效传播。
- `docs/.DS_Store` 是历史已跟踪文件，本次未修改它；没有将新的本机配置或运行凭据加入提交。

完成本轮 Review 与提交后停止，未开始 NOVEL-003。
