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
backend/novel_os/prompts/library/  版本化 Prompt Library（随 wheel / Docker 打包）
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
- Actual Implementation: `NOVEL-005 — Prompt Runtime & Model Provider`，实现、验证和独立审查完成，等待用户 Review
- NOVEL-001 / 002 / 003 / 004: 已通过 Review，沿用 TOML 配置和现有基础设施
- Next Action: Review NOVEL-005；不自动进入 NOVEL-006

具体规格见 `docs/specs/`，开发任务见 `docs/tickets/`。

## Backend Development

当前实现工程基础设施、Core Domain、deterministic Chapter Workflow、异步 Agent Runtime、
版本化 Prompt 与可替换模型 Provider。默认使用 Mock；真实 Provider 通过 TOML 显式启用。
尚未实现 Context Engine、真实业务 Agent、Memory/Canon 或前端。

需要 Python 3.13（声明支持 3.12–3.14）、uv、Docker Engine 与 Docker Compose 插件（v2 或更新版本）。
依赖的精确版本记录在 `backend/uv.lock`；Docker 构建使用 uv 0.9.30。

macOS 可使用 Colima 提供 Docker Engine。安装并启动：

```bash
brew install colima docker docker-compose docker-buildx
mkdir -p ~/.docker/cli-plugins
ln -s /opt/homebrew/opt/docker-compose/bin/docker-compose ~/.docker/cli-plugins/docker-compose
ln -s /opt/homebrew/opt/docker-buildx/bin/docker-buildx ~/.docker/cli-plugins/docker-buildx
colima start --vm-type vz --cpu 4 --memory 4 --disk 30
docker version
docker compose version
```

以上插件路径适用于 Apple Silicon Homebrew；若链接已存在，无需重复创建。
以后用 `colima start` 启动、`colima stop` 停止 Docker 环境；没有配置登录时自动启动。

首次构建若出现 Docker Hub `failed to fetch anonymous token` 网络超时，可先执行
`docker pull python:3.13-slim`，再重试 Compose 构建。本机安装时已按已有代理设置补充
Colima 内 Docker systemd 服务的代理环境；镜像下载需要当前网络代理可用。

### 配置

应用、Alembic 和 pytest 只读取当前工作目录下的 `config.toml`，由 Pydantic Settings
校验。环境变量和 `.env` 均不参与配置，也不会展开 `$` 或 `${...}`。
从仓库根目录执行：

```bash
cp backend/config.example.toml backend/config.toml
chmod 600 backend/config.toml
cd backend
uv sync --locked --python 3.13
```

编辑 `backend/config.toml`，分别替换开发库和测试库 URL 中的示例密码。
URL 中凭据的保留字符仍须进行百分号编码，例如 `@` 写成 `%40`、`/` 写成 `%2F`、
`%` 写成 `%25`。这是 URL 语法要求；TOML 字符串本身不会做变量替换。
两个 URL 均按完整 SQLAlchemy URL 传递，保留 `sslmode`、`sslrootcert`、`host` 等查询参数。
实际配置与生成的 `.runtime/` 已被 Git 和 Docker build context 忽略。

| 配置文件字段 | 默认值 / 用途 |
| --- | --- |
| `postgres_url` | 必填，`postgresql+psycopg` 开发库连接 URL |
| `test_database_url` | 完整 pytest 必填，独立且名称以 `_test` 结尾的数据库 URL |
| `log_level` | `INFO`，可选 DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `db_connect_timeout` | 2 秒，URL 未指定 `connect_timeout` 时生效 |
| `db_statement_timeout_ms` | 3000 毫秒，URL 未指定 `options` 时生效 |
| `db_pool_timeout` | 3 秒，连接池等待超时 |
| `workflow_fake_executor_enabled` | `false`；仅在 test/dev 开启 FakeExecutor HTTP 入口 |
| `agent_lease_seconds` | 30 秒，任务租约时长，范围 1–3600 |
| `agent_heartbeat_seconds` | 5 秒，须小于租约时长 |
| `agent_poll_seconds` | 1 秒，空闲轮询间隔 |
| `agent_retry_seconds` | 1 秒，技术错误退避基数，逐次翻倍，上限 60 秒 |
| `agent_mock_scenario` | `SUCCESS`，独立 Worker 的 Mock 场景 |

示例文件使用开发端口 55432、测试端口 55433。连接外部 PostgreSQL 时直接编辑 URL；
应用无须执行 Docker 配置生成命令。程序内测试可显式构造 `Settings(...)` 或调用
`Settings.from_file(path)`，也不会从环境读取缺失字段。

### Docker 启动

Compose 各服务使用只读挂载文件，不配置 `environment` 或 `env_file`。
先在 `backend/` 目录生成挂载文件，然后从仓库根目录启动：

```bash
uv run --locked python -m novel_os.infrastructure.prepare_docker
cd ..
docker compose up --build -d --wait
docker compose run --rm backend /app/.venv/bin/alembic upgrade head
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/health/db
docker compose logs -f backend
```

`prepare_docker` 从同一个 `config.toml` 生成 `.runtime/config.toml` 和数据库初始化文件。
容器中的后端连接地址改为 `postgres:5432`，不包含测试库凭据；两个 PostgreSQL 服务各自
只挂载自己的账号、密码和库名文件。PostgreSQL 使用 `initdb --pwfile` 及命令行参数初始化，
不读取 `POSTGRES_*` 环境变量。生成目录权限为 0700；目录内挂载文件允许容器非 root 用户读取。

该命令用于随项目提供的本机 Compose 服务，要求 URL host 为 `localhost` 或 `127.0.0.1`，
且没有覆盖地址的 `host`、`port`、`service` 查询参数。初始化凭据不支持换行或 NUL。
随项目提供的 PostgreSQL 未启用 TLS；准备命令拒绝 `sslmode=require/verify-ca/verify-full`
和证书等其他 `ssl*` 参数，也拒绝 `channel_binding=require`、`gssencmode=require`。
需要 TLS 时使用已配置 TLS 的外部 PostgreSQL，直接运行 Python
服务，完整 URL 参数仍会保留。移除 `test_database_url` 后重新生成，会清理旧的测试服务凭据目录；
已经运行的测试容器需用 `docker compose --profile test stop postgres-test` 停止。
修改配置后需重新生成文件并重启服务；只修改 TOML 不会自动更新运行中的进程。

API 文档位于 `http://127.0.0.1:8000/docs`。端口仅绑定本机回环地址。
默认启动 backend 与 PostgreSQL 16；开发数据保存在 `postgres_data` volume。
后端以非 root 用户运行，数据库入口完成数据目录权限准备后切换到 postgres 用户。
迁移必须显式执行，应用启动不自动迁移或建表。`docker compose down` 保留开发数据。

首次初始化 volume 后，修改配置文件不会自动修改 PostgreSQL 已有的账号、密码或数据库；
需要同步修改数据库中的账号。开发库和测试库分别映射 55432、55433，避免与本机 5432 冲突。
若端口已占用，需同步调整 Compose 映射和本地 URL。

### 本地 Python 开发

首次配置及 Docker 文件生成完成后，从仓库根目录执行：

```bash
docker compose up -d --wait postgres
cd backend
uv run --locked alembic upgrade head
uv run --locked uvicorn novel_os.main:create_app --factory --reload --no-access-log
```

若已有 PostgreSQL 16，可手工创建相互独立的开发库和测试库，设置 `config.toml` 后直接运行
Python 服务、pytest 与迁移，无须 Docker。

### 测试与 Lint

首次配置及 Docker 文件生成完成后，从仓库根目录执行：

```bash
docker compose --profile test up -d --wait postgres-test
cd backend
uv run --locked pytest
uv run --locked ruff check
uv run --locked ruff format --check
```

测试服务使用 55433 端口和独立的 `novel_os_test` 数据库，数据放在 tmpfs，
与开发数据库 volume 分离。测试配置拒绝非 `_test` 数据库及与开发库同名的数据库。
完整测试包含真实 PostgreSQL 查询、迁移、API 生命周期、并发和事务回滚验证。
Core Domain 与 Workflow 的每项集成测试在测试库中创建独立临时 schema，结束后清理自己的 schema。
缺少测试库配置或连接失败会报错，不会静默跳过。
普通单元测试使用本机未监听端口验证 DB 故障，不访问开发库。

只运行不依赖 PostgreSQL 的测试：

```bash
uv run --locked pytest -m 'not integration'
```

### 迁移验证

在 `backend/` 下执行：

```bash
uv run --locked alembic upgrade head
uv run --locked alembic downgrade -1
uv run --locked alembic upgrade head
uv run --locked alembic current
```

当前 revision 是 `0005_agent_runtime`，前驱为 `0004_workflow_recovery`。
0004 已用于 NOVEL-003 Review 修复，因此 NOVEL-004 顺延使用迁移编号 0005；不代表实现 NOVEL-005。
0005 新增 `agent_tasks`、`agent_runs`、索引、约束和执行历史保护 trigger。
从当前 head 执行 `downgrade -1` 会删除这两张表及执行记录，保留 Core、Workflow 和审计数据。
重新升级后 Worker 可为仍在等待 Agent 的旧 Workflow 补建当前阶段任务，但不能恢复被删除的 Run。
继续从 0004 降至 0003 会移除阶段恢复字段，并转回 0003 的表示，保留 Workflow 和审计数据。
若继续从 0003 降至 0002，会删除五张 Workflow 表及其中的数据，保留 Core Domain 和已有
AuditRecord；重新 upgrade 不会恢复被删除的实例。升降级验证应使用空库或独立测试库。
`uv run --locked alembic check` 可检查 ORM metadata 与当前表结构是否一致。

### API 与错误约定

| 请求 | 正常状态 | 数据库故障 |
| --- | --- | --- |
| `GET /api/v1/health` | 200，`{"status":"ok"}` | 仍返回 200 |
| `GET /api/v1/health/db` | 200，`{"status":"ok","database":"ok"}` | 503，统一错误结构 |

所有 HTTP 响应都包含 `X-Request-ID`。客户端可传入 1–128 个 ASCII 字母、数字、
点、下划线或连字符；缺失、重复或无效的值会替换成 UUID。
403、404、405、409、422、503 和未捕获异常均使用统一结构，例如：

```json
{
  "error": {
    "code": "DATABASE_UNAVAILABLE",
    "message": "Database is unavailable",
    "request_id": "example-request-id",
    "details": []
  }
}
```

422 的 `details` 提供字段位置与错误类型，不回显输入值。
内部异常响应不暴露数据库连接信息、SQL 参数或异常原文。
日志为 stderr 上逐行 JSON，包含 UTC 时间、级别、logger、事件名和 request ID；
请求日志另含 method、path、status_code、duration_ms。异常仅记录类型，
不会输出原始异常消息、请求体或 query string。运行命令关闭 Uvicorn 自带 access log，避免重复记录。

### 代码边界

```text
backend/novel_os/
├── main.py                 create_app 与 lifespan
├── api/                    路由、DTO、依赖装配、request ID、异常映射
├── core/                   Settings、JSON logging
├── db/                     DeclarativeBase、engine、session 生命周期
├── domain/                 纯 Python Entity、Enum、Value Object、业务异常
├── models/                 SQLAlchemy ORM、关系和数据库约束
├── services/               用例事务、版本、审批、锁、审计、健康检查
├── workflow/               Workflow 应用用例、定义、Guard、Human Gate、FakeExecutor
├── agents/                 Mock Provider、结构化结果、Registry 和权限校验，无持久化调用
├── worker.py               独立执行进程；轮询、执行、心跳
└── repositories/           Domain / ORM 映射、查询、flush，无 commit
```

数据库请求链为 API → Service → Repository → Database。同步数据库调用由同步路由执行，
由 FastAPI 放入线程池。Session 按请求创建，异常时 rollback，退出时关闭；
成功退出也不会自动 commit。写入用例由 Service 的 `session.begin()` 显式拥有事务边界，
业务数据、版本指针与审计一起提交或回滚；Repository 不得提交。
进程退出时 dispose 连接池；liveness 与应用启动均不要求数据库可连接。

### Core Domain — NOVEL-002

接口统一以 `/api/v1/projects` 为前缀，完整输入与响应见运行中的 `/docs`。
下表的路径相对于该前缀，`{p}` 表示 project ID，`{c}` 表示 chapter ID，
`{id}` 表示 Requirement / Decision 的稳定 `logical_id`，`{v}` 表示版本号。

| 对象 | 接口 |
| --- | --- |
| Project | `POST /`、`GET /`、`GET/PATCH/DELETE /{p}`；DELETE 执行 ARCHIVED |
| Requirement | `POST/GET /{p}/requirements`；`GET/PATCH /{p}/requirements/{id}`；`POST .../approve`、`POST .../supersede`；`GET .../versions`、`GET .../versions/{v}` |
| Decision | `POST/GET /{p}/decisions`；`GET/PATCH /{p}/decisions/{id}`；`POST .../approve`、`POST .../versions`；`GET .../versions`、`GET .../versions/{v}` |
| Chapter | `POST/GET /{p}/chapters`、`GET /{p}/chapters/{c}` |
| ChapterPlan | `POST/GET /{p}/chapters/{c}/plans`、`GET .../plans/{v}`、`POST .../plans/approve` |
| ChapterVersion | `POST/GET /{p}/chapters/{c}/versions`、`GET .../versions/{v}`、`POST .../versions/approve` |
| Lock | `POST/GET /{p}/locks`、`POST /{p}/locks/{lock_id}/release` |
| AuditRecord | `GET /{p}/audit` |

列表支持 `limit`（1–200）和 `offset`。Requirement / Decision 普通列表返回每个逻辑对象的
最新版本；`?effective=true` 返回当前有效的已批准版本，历史通过 `/versions` 查询。

创建正文的第一次请求使用 `expected_version: 0`；以后每次创建版本使用已读取的
`Chapter.current_version`。例如创建第二个版本：

```json
{
  "expected_version": 1,
  "content": "第二版正文",
  "change_reason": "调整本章结尾"
}
```

批准具体版本使用 `POST .../versions/approve`：

```json
{
  "expected_version": 2,
  "reason": "用户确认第二版"
}
```

新 Draft 仅推进 `current_version`，保留原 `approved_version`；批准成功才推进批准指针。
Plan 使用独立的 `current_plan_version` / `approved_plan_version`，规则相同。
过期 `expected_version` 返回 HTTP 409 / `VERSION_CONFLICT`，应重新读取再由用户确认。
Requirement / Decision 已批准后不能 PATCH；通过 `/supersede` 或 `/versions` 创建
新 PROPOSED，新版本批准前旧批准仍有效，批准后旧版本变为 SUPERSEDED。所有历史版本保留。

锁请求需要 `target_type`、`target_id`、`expected_version` 和 `reason`。
Project / Chapter 的 target ID 是自身 ID；Requirement / Decision 使用 logical ID；
ChapterPlan / ChapterVersion 使用所属 chapter ID（即其 logical ID）。对象锁也检查父级
Project / Chapter 锁；Decision 直接引用的受影响对象也参与锁检查。Plan 的
`locked_dependencies` 必须引用同项目内已锁定对象，并在批准时再次检查。
释放使用 lock ID 和目标对象当前的版本；Project / Chapter 的锁定、释放会增加其版本计数，
应先 GET 目标获取最新 `version`。版本化内容的锁定、释放不会生成新的内容版本。

客户端只提交内容及操作意图。`version`、`status`、`authority_level`、`locked`、
`approved_at`、`approved_by`、actor 等字段由 Service 产生，传入会被拒绝。
本阶段 HTTP 调用者固定为本地用户 `local-user`，忽略客户端 actor headers；
尚未实现登录、多用户身份或 Agent 身份接入，继续使用 Compose 的本机回环端口。

同一 Project 的写入以数据库行锁串行化；并发创建下一正文版本时，一个成功，另一个因
版本过期得到 409。不同 Project 可以独立写入。数据库额外通过唯一约束、外键及 trigger
阻止重复版本、无效指针、正文原地修改、已批准或已锁定版本的内容修改、审计修改和核心记录硬删除。

本阶段实现与验证结果见 [NOVEL-002 实现报告](docs/reports/NOVEL-002-implementation.md)。
提交 main 前的整体审查与最终验证见 [NOVEL-002 代码审查报告](docs/reports/NOVEL-002-code-review.md)。

相关语义参考 [SQLAlchemy Session 文档](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、
[FastAPI 异常处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)、
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 和
[Compose 启动依赖](https://docs.docker.com/compose/how-tos/startup-order/)。
Colima 安装与 Docker 代理配置分别参考 [Colima 文档](https://colima.run/docs/installation/) 和
[Docker daemon 代理文档](https://docs.docker.com/engine/daemon/proxy/)。


### Chapter Workflow — NOVEL-003

状态表唯一来源为
[`backend/novel_os/workflow/definitions/chapter-production.v1.yaml`](backend/novel_os/workflow/definitions/chapter-production.v1.yaml)。
它随 wheel 和 Docker 镜像打包。实例创建时保存定义正文、摘要和 `(id, version)`，
运行中只读取数据库中绑定的定义；修改已有定义版本会被拒绝，升级必须使用新版本号。

| 接口 | 用途 |
| --- | --- |
| `POST /api/v1/workflows/chapter` | 为已有 Project / Chapter 创建 Workflow |
| `GET /api/v1/workflows/{id}` | 读取状态、state_version、计数和绑定版本 |
| `POST /api/v1/workflows/{id}/events` | USER_SUBMITTED / BLOCK / PAUSE / RESUME / CANCEL |
| `POST /api/v1/workflows/{id}/pause` | 保留当前业务状态并暂停 |
| `POST /api/v1/workflows/{id}/resume` | 重新检查 Guard 后恢复 |
| `POST /api/v1/workflows/{id}/cancel` | 进入 C92_CANCELLED，并取消等待中的 Gate |
| `GET /api/v1/workflows/{id}/history` | 按 state_version 排序的转换历史；支持 limit / offset |
| `GET /api/v1/workflows/{id}/human-gates` | 按打开顺序列出 Gate；支持 limit / offset |
| `POST /api/v1/human-gates/{id}/decision` | 用户 APPROVE / REJECT / MODIFY / REQUEST_ALTERNATIVE / CANCEL |
| `POST /api/v1/workflows/{id}/fake-execute` | test/dev 模拟一步执行；默认关闭并返回 404 |

手工验证可在 `backend/config.toml` 设置 `workflow_fake_executor_enabled = true` 后重启本地
Python 服务。Docker 用户先重新运行 `prepare_docker`，再重建并启动 backend。通过 `/docs`
创建 Project、Chapter，然后依次提交下列请求（UUID 使用实际值；每个新操作使用新的 event_id）：

```json
{
  "event_id": "<新的 UUID>",
  "project_id": "<project UUID>",
  "chapter_id": "<chapter UUID>",
  "definition_id": "chapter-production",
  "definition_version": 1
}
```

创建接口返回 `workflow`、`outcome`、`duplicate`、`error_code`。对 `/events` 提交：

```json
{
  "event_id": "<新的 UUID>",
  "expected_state_version": 1,
  "event_type": "USER_SUBMITTED",
  "reason": "开始本章"
}
```

随后从每次响应取得最新 `current_state` 和 `state_version`，在非 Human Gate 状态调用
`/fake-execute`：

```json
{
  "event_id": "<新的 UUID>",
  "expected_state_version": 2,
  "origin_state": "C01_REQUIREMENT_INTAKE",
  "outcome": "success"
}
```

`outcome` 可选择 `success`、`review_failure`（Plan Review / Deterministic Check / Internal Review）、
`technical_failure`、`fatal_failure` 或 `replan`（Feedback Diagnosis）。重复传输必须保留原始
event_id 和完整请求；同 ID 同命令返回原处理结果，同 ID 换命令返回 `IDEMPOTENCY_CONFLICT`。
并发或过期 state_version 返回 409 / `VERSION_CONFLICT`。过期执行结果会以 `STALE_IGNORED`
记录在 workflow_events 中，不创建转换、版本、Gate 或审计；HTTP 同样返回 409。

在 C06 / C12 读取 `/human-gates` 的 WAITING Gate，对它的 `/decision` 提交：

```json
{
  "event_id": "<新的 UUID>",
  "expected_state_version": 7,
  "expected_artifact_version": 1,
  "decision": "APPROVE",
  "reason": "用户确认当前版本"
}
```

数值必须取自最新 Workflow 和 Gate，示例仅代表第一轮 Plan Approval。Human Gate 绑定具体
artifact ID/version；过期审批返回 409，并原子地保存 STALE Gate 和 BLOCKED Workflow。
恢复后，旧 Plan 回到规划，新正文回到检查，重新经过 Review 和用户审批。
正文检查、评审、进入 Revision、验收和模拟完成前均核验绑定的 Plan 仍为当前已批准版本；
Plan 变更后旧正文不能继续推进或审批，需回到规划。旧版本和既有审批历史仍然保留。
批准、Gate 决定、Workflow 转换、版本指针和审计在一个应用事务内提交。普通事件不能提交
`USER_APPROVED`；所有 actor 信息由可信服务端入口产生。

第一次进入 Planning 时 `planning_iteration_count = 1`；重规划时增加，新的 Plan 在该次
`PLAN_READY` 返回时创建。进入 Revision 增加 `revision_count`，`REVISION_READY` 创建新的正文。
两者与技术重试分离：v1 定义每个执行阶段允许两次技术重试，第三次失败进入 C91_FAILED；
`retry_count` 保留累计次数，`state_retry_count` 在进入新的执行阶段时重置，同阶段暂停/阻塞恢复不刷新预算。

BLOCKED 独立保存恢复位置、是否进入新阶段和缺失 Guard；再次阻塞不会覆盖阶段恢复意图。
条件仍不满足时 Resume 仍返回 BLOCKED。PAUSED 不改变业务
状态；Resume 保留原 Gate，不重复创建。COMPLETED / FAILED / CANCELLED 均为终态。
每个 Chapter 同时只允许一个未终结的 Workflow。
当前 YAML 只在创建新实例时读取；既有实例的读取、控制、审批和推进均使用数据库保存的定义。

C14 / C15 只模拟事件交接，不产生 MemoryChangeSet，不写入 Memory 或 Canon；COMPLETED 仅表示
本阶段的模拟流程完成。FakeExecutor 无 Repository、无状态写权限，也不能批准 Human Gate。
NOVEL-003 保留 FakeExecutor 用于控制流程测试；NOVEL-004 的独立 Worker 见下节。
控制面仍为本地单用户，尚未实现登录或多用户权限。

快速执行完整 Workflow 验证：

```bash
cd backend
uv run --locked pytest tests/core/workflow
```

实现、验收和局限见 [NOVEL-003 实现报告](docs/reports/NOVEL-003-implementation.md)。

### Agent Runtime — NOVEL-004

先执行 `alembic upgrade head`，再分别启动 FastAPI 和 Worker。在另一个终端从 `backend/` 执行：

```bash
uv run --locked python -m novel_os.worker
```

单步执行与指定配置文件：

```bash
uv run --locked python -m novel_os.worker --once --config config.toml
```

也可以复用后端 Docker 镜像启动独立进程（从仓库根目录运行）：

```bash
docker compose run --rm --no-deps backend /app/.venv/bin/python -m novel_os.worker
```

Worker 不随 FastAPI 自动启动，HTTP 请求只提交事务并返回。可启动多个 Worker；
每个进程使用独立 worker ID，一次执行一个任务。SIGINT/SIGTERM 等待当前执行结束后退出，
强制终止留下的租约可在到期后恢复。`--once` 没有可领取任务时正常退出。

按前节创建 Workflow 并提交 `USER_SUBMITTED` 后，Worker 自动执行到 C06 Plan Approval；
用户通过原 Human Gate 接口审批，再执行至 C12 Chapter Approval；第二次审批后抵达 C16。
正常路径有 11 个 Task。Plan / Draft 使用固定 Mock 内容，C14 / C15 仅模拟交接，没有 Canon 写入。
自动流程无须开启 `workflow_fake_executor_enabled`。

| 只读接口 | 用途 |
| --- | --- |
| `GET /api/v1/agent-tasks/{task_id}` | 任务状态、尝试次数、租约期限、结果摘要 |
| `GET /api/v1/agent-tasks/{task_id}/runs` | 每次尝试的状态、耗时、错误码和结果处置 |
| `GET /api/v1/workflows/{workflow_id}/agent-tasks` | Workflow 的任务历史 |

列表支持 `limit` / `offset`，不返回内部 fencing token。不提供 Task 创建或 mock-execute HTTP 接口。

`agent_mock_scenario` 支持 SUCCESS、BLOCKED、FORMAT_ERROR_ONCE、MODEL_ERROR_ONCE、ALWAYS_FAIL、
AUTHORITY_VIOLATION、LOW_CONFIDENCE、NEEDS_HUMAN、SLOW_SUCCESS、MALFORMED_OUTPUT、QUALITY_FAIL。
修改 TOML 后重启 Worker；Docker 使用新配置前重新执行 `prepare_docker`。
ONCE 场景由数据库中的 attempt number 决定，重启不会重置第一次错误。

每次领取生成新的 AgentRun 和租约 token。租约到期后的旧 Worker 不能提交或续租，
旧 Run 标记 ABANDONED；新 Worker 使用新 Run 继续同一 Task。Task 的 technical retry 默认最多
3 次执行，不增加 Workflow 的 revision / planning iteration，也不借用 FakeExecutor 的重试计数。
Review FAIL 由固定映射进入 Revision 或 Replanning，不触发技术重试。

权限来自 Agent Definition、Task Type、Workflow State、Task Scope 的共同约束。
AgentResult 禁止 next_state / next_event；所有事件由系统 ResultHandler 生成，并经过原 Workflow Guard。
权限违规不会写入提案或推进业务阶段；Run 保存 AUTHORITY_DENIED，Task BLOCKED，系统进入 C90 等待用户处理。
BLOCKED / NEEDS_HUMAN / 低置信结果同样阻塞，绝不自动审批。用户 Resume 后按新的 state_version 创建任务。
取消或状态版本变化后的运行结果标记 STALE_IGNORED，不创建内容或转换；取消的 Task 不会再次被领取。

验证与独立审查记录见 [NOVEL-004 实现报告](docs/reports/NOVEL-004-implementation.md)。


### Prompt Runtime / Model Provider — NOVEL-005

Worker 保留原领取、租约、重试和结果处理流程；执行前解析并绑定每次 Run 的精确 Prompt
模块版本。新增 migration 为 `0006_prompt_runtime`（`0005_agent_runtime` 已在上一阶段发布）。

```bash
cd backend
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked python -m novel_os.prompt_demo --text "一个发生在海边的温暖短篇"
```

Demo 使用 `INTERNAL_SMOKE_TEST` / A02 和 RequirementSpec，只验证编译、Provider、结构化输出
与权限检查。不创建 AgentTask、Requirement、ChapterPlan 或 Workflow，也不写数据库。
默认仍走完整 Mock pipeline，不需要 API Key。

真实 OpenAI Responses Provider：在本地、已忽略的 `backend/config.toml` 配置：

```toml
agent_model_profile = "openai-structured"
openai_api_key = "在本地配置实际密钥"
```

模型参数来自 Git 文件 `backend/novel_os/providers/profiles.toml`；当前仅有 `mock-default`
和 `openai-structured` 两个 Profile。OpenAI 使用固定官方 HTTPS endpoint、显式 timeout、
无客户端内部重试，重试预算仍由 AgentTask 管理。改为真实 Profile 后，Worker 也会调用真实
模型，但已有任务 Prompt 仍明确属于 simulation，不提供 NOVEL-007 及以后的业务能力。
HTTP 200 中的 `failed` 响应也按错误码分类：`server_error` 和 `rate_limit_exceeded` 分别进入
MODEL_UNAVAILABLE / MODEL_RATE_LIMIT 技术重试，认证或额度配置错误保持不可重试。
配置不读取环境变量。不要把真实密钥写进 example、Prompt module 或模型 Profile。
Docker 使用变更后的配置前，按上文重新运行 `prepare_docker`。

显式真实调用测试（会发起付费 API 请求；未提供密钥则 skip）：

```bash
uv run --locked pytest tests/prompts/test_providers.py -m live_model --live-model
```

普通 `pytest` 始终跳过真实调用；真实 Adapter 的 HTTP 格式、结构化验证、错误映射与秘密保护
由 MockTransport 测试覆盖。流式输出、远程 token counting 尚未实现，接口明确拒绝不支持的能力。

Prompt 文件位于 `backend/novel_os/prompts/library/{system,agents,tasks,skills,quality}/`，
每个模块版本包含 `manifest.json` 和 `content.md`。manifest 声明版本、状态、依赖、兼容范围和
规范化正文 SHA-256。新增版本创建新目录；不得原地修改已使用版本的正文或执行 metadata。
状态可以从 EXPERIMENTAL 晋升 STABLE。未指定版本时只选择最高 STABLE，历史绑定始终保存
具体 version/hash。RETIRED 不可新编译；DEPRECATED 不参与默认选择，但允许显式版本检查。
每个 pin 另含自动计算的 `execution_hash`，覆盖除 status 外的全部 manifest 字段（含正文 hash）。
依赖或兼容范围变化也必须创建新版本；状态晋升不改变该摘要。Compiler v2 将它纳入 compiled hash。

修改正文后可在本地计算 LF 规范化摘要，将结果填入**新版本** manifest：

```bash
uv run --locked python -c 'from pathlib import Path; from novel_os.prompts.contracts import digest, normalize; print(digest(normalize(Path("path/to/new/content.md").read_text())))'
```

编译顺序固定为 System Policy → Agent Role → Task Template → Skills（按 ID/version 排序）
→ Quality → Authority/Constraints → Context DATA → Pydantic Output Contract。
Context 只接受调用方传入的数据，不读取 DB/Memory；依赖必须显式包含于所选组合中。

查看某次持久化运行的配置：

```text
GET /api/v1/agent-runs/{run_id}/prompt-lineage
```

接口返回精确模块 ID/version/hash、Schema ID/version/hash、模型 Profile 的安全参数与摘要、
compiled hash；不返回正文、Context 或密钥。升级前的 Run、编译前失败/失去租约的 Run 没有
Lineage，接口返回 404。已有 AgentRun 不被回填或修改。
修复前 compiler v1 的旧 pin 若没有 execution_hash，接口返回 null 表示未知，不用当前文件补造历史。
遇到这种旧 pin，无法验证其执行 metadata 的同版本新绑定会被拒绝；需为涉及的模块发布新版本。
升级时应停止旧 Worker，避免继续产生缺少 execution_hash 的记录。本次修复前开发库 Lineage 为 0 行。

模型调用前，Service 在短事务中保存 Lineage 和审计。并发首次绑定同一模块版本使用 PostgreSQL
事务锁，发现与已有历史相冲突的 hash 会拒绝新执行。Provider 调用期间不持有此事务。
每次技术重试使用新 Run、新 Lineage，旧历史不变。模块正文的唯一来源仍是 Git。

开发验证：

```bash
uv run --locked pytest
uv run --locked ruff check
uv run --locked ruff format --check
uv build
uv run --locked alembic check
```

实现详情及最终验证结果见 [NOVEL-005 实现报告](docs/reports/NOVEL-005-implementation.md)。
