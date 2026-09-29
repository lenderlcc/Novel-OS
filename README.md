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
- Actual Implementation: `NOVEL-011 — Human Feedback & Directed Revision`，等待用户 Review 与正文人工验收
- 已实现 NOVEL-001～010B、STYLE-001/002 和 Personal Creative Workspace；沿用 TOML 配置和现有基础设施
- Next Action: Review NOVEL-011；不自动进入 NOVEL-012

具体规格见 `docs/specs/`，开发任务见 `docs/tickets/`。

## Backend Development

当前实现工程基础设施、Core Domain、deterministic Chapter Workflow、异步 Agent Runtime、
版本化 Prompt、可替换模型 Provider 和结构化 Context Engine，以及需求理解、方案、写作、质量审阅、
定向修改与人工反馈链路。Vue 工作台提供个人创作入口；Memory/Canon 写入尚未实现。
默认使用 Mock；真实 Provider 通过 TOML 显式启用。

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
uv run --locked alembic check
```

当前 revision 是 `0007_context_engine`，前驱为 `0006_prompt_runtime`。
0004 已用于 NOVEL-003 Review 修复，0005 用于 Agent Runtime，0006 用于 Prompt Lineage；
NOVEL-006 顺延使用 0007，未修改旧迁移。0007 新增 `context_packages` 及不可变快照保护。
从 0007 执行 `downgrade -1` 只删除 Context 快照，保留 Core、Workflow、AgentTask、AgentRun、
PromptLineage 和审计；重新 upgrade 不会恢复删除的快照。验证使用空 Context 表或独立测试 schema。
继续从 0006 降到 0005 会删除 PromptLineage，0005 降到 0004 会删除 AgentTask/AgentRun。
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
和 `openai-structured` 两个基础 Profile。OpenAI 使用固定官方 HTTPS endpoint、显式 timeout、
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


### Context Engine / Memory Query Foundation — NOVEL-006

Worker 在模型调用前构建并持久化 ContextPackage，要求 READY，绑定当前运行尝试，然后通过
ContextSerializer 生成 Prompt 的 `UNTRUSTED_DATA_ONLY` 数据层。模型调用前与结果应用前分别
检查快照新鲜度；无数据库快照或结果引用不匹配会阻塞。Workflow 已切换阶段的结果沿用原有
`STALE_IGNORED` 路径，保留模型运行结果并阻止其修改领域数据。

Profile 位于 `backend/novel_os/context/profiles/`，以 JSON 文件发布明确版本：

| Profile | 用途 | 默认未来信息策略 |
|---|---|---|
| CP-004 v2 | Planning 上下文 | LIMITED，显式引用且最多下一章 |
| CP-005 v2 | Writing 上下文 | REQUIRED_ONLY，仅批准计划的必要依赖 |
| CP-006 v2 | Review 上下文 | LIMITED，非 FULL |
| CP-007 v2 | Revision 上下文 | REQUIRED_ONLY |
| CP-000 v1 | 既有 Mock 控制阶段与独立 smoke | NONE，仅显式任务输入 |

已发布版本的定义不可原地改写，新增版本需新增文件。Registry 同时支持 Mock 类型和通用
`CHAPTER_PLANNING/WRITING/REVIEW/REVISION` 的 Context 契约；未增加这些真实 Agent 的业务逻辑。
CP-004～CP-007 的 v1 文件保留用于历史快照；新任务使用 v2 的精确锁定依赖策略。
默认预算 48,000，扣除 Prompt overhead 与模型输出预留；UTF-8 字节估算保守计数，不代表实际计费。
P0 超预算或检索上限、缺少必要计划、同权威冲突均 BLOCKED，不能自动截断 P0 或触发模型调用。
MUST/FORBIDDEN 等集合可以合法为空；已存在且有效的匹配项必须全部纳入 P0 或阻塞。

前文章节只按 approved_version 读取，Writing 按 Workflow 绑定的已批准计划读取。
创建新 Draft 不会替换批准内容。Review/Revision 允许其精确绑定的目标 Draft。
显式锁定的 Requirement/Decision/Plan/ChapterVersion 依赖按项目、ID、版本和 active Lock 查询。
已批准计划明确声明的 A1 锁定依赖可以尚未经过独立审批；普通主计划与前文读取仍要求批准版本。
依赖解锁后，已有快照失效，模型结果不能落库。Profile 库加载异常按配置错误阻塞任务并结束运行尝试。
所有获取使用结构化 SQL，没有 Embedding、Vector DB、全文检索或 LLM 排序。

只读 Inspector：

```text
GET /api/v1/context-packages/{context_package_id}
GET /api/v1/agent-tasks/{task_id}/context
```

响应包含不可变 package、运行时计算的 freshness 和 error_code；Task 接口返回最近一次执行
尝试的快照。`package.build_status` 保留构建结果，`freshness=STALE` 不改写旧快照。
Inspector 是既有本机单用户控制面的一部分，会显示业务上下文，不返回 Provider 密钥或配置。

Character Knowledge 仅实现 GLOBAL_ONLY / CHARACTER_KNOWLEDGE 类型、角色 ID 过滤与
ContextSourceReader 扩展契约。没有 Character、Event、Canon 或 CharacterKnowledge 数据表。
扩展 reader 返回的候选必须属于被调用的 selector/source type；不匹配时返回配置错误，不能冒充必需项。

专项测试：

```bash
cd backend
uv run --locked pytest tests/context tests/core/workflow/test_context_engine.py
```

实现细节与最终验收结果见 [NOVEL-006 实现报告](docs/reports/NOVEL-006-implementation.md)。

### Requirement / Planning Vertical Slice — NOVEL-007

007 增加 `chapter-planning` v1 正式 Workflow；原 `chapter-production` v1 Mock 流程继续保留。
正式链路使用 `PARSE_CHAPTER_REQUIREMENT`、`PLAN_CHAPTER`、`REVIEW_CHAPTER_PLAN`，
复用现有 Worker、Prompt / Model Runtime、Context Engine、HumanGate 和 ChapterPlan 服务。
C02/C03 是确定性控制步骤，不额外调用模型。用户批准合格 Plan 后停在 C07_WRITING，
此定义不会调度 Writer，也不会创建 ChapterVersion。

1. 使用现有 API 创建 Project 与 Chapter，然后提交自然语言需求：

```http
POST /api/v1/workflows/chapter-planning
Content-Type: application/json

{
  "event_id": "<新的 UUID>",
  "project_id": "<Project UUID>",
  "chapter_id": "<Chapter UUID>",
  "raw_requirement": "本章必须找到线索，不能杀死主角，保留人物之间的信任。"
}
```

2. 保持现有 Workflow 的显式提交语义，对返回的 Workflow 发送 USER_SUBMITTED：

```http
POST /api/v1/workflows/<workflow_id>/events
Content-Type: application/json

{"event_id":"<新的 UUID>","expected_state_version":1,"event_type":"USER_SUBMITTED"}
```

3. 在 `backend/` 启动 Worker（配置继续只使用 `config.toml`）：

```bash
uv run --locked python -m novel_os.worker --config config.toml
```

默认 Mock 是确定性契约样例，不能代表自然语言理解质量。真实业务理解使用版本化 Prompt
和 NOVEL-005 的真实 Provider；通过已有 `agent_model_profile` / `openai_api_key` TOML
配置选择 Provider。CI 不需要密钥，不自动运行付费调用。

4. 使用以下查询检查结果；返回 Domain / Pydantic DTO，不暴露 ORM：

| Endpoint | 内容 |
| --- | --- |
| `GET /api/v1/workflows/{id}/creative-brief` | 最新 Brief 及状态、原始输入、版本和 lineage |
| `GET /api/v1/workflows/{id}/creative-brief/versions/{version}` | 精确历史 Brief |
| `GET /api/v1/workflows/{id}/planning/plan` | 当前 Workflow 绑定 Plan 与完整结构化生成证据 |
| `GET /api/v1/workflows/{id}/planning/plan/versions/{version}` | 同一 Workflow 的指定 Plan 版本 |
| `GET /api/v1/workflows/{id}/planning/review` | 当前 Plan 的 focused review，包含有效 verdict |
| `GET /api/v1/workflows/{id}/planning/history?limit=100&offset=0` | 分页 Brief / Plan generation / Review 历史 |
| `GET /api/v1/workflows/{id}/planning/metrics` | 本 Workflow 的解释、修正、规划、审批、硬门槛和技术重试统计 |

现有 AgentRun 查询可读取 PromptLineage；新产物保存 `agent_run_id`、`prompt_lineage_id`、
`context_package_id` 与 source versions。业务内容只进入相应 Artifact / Context 表，
不会写入普通运行日志。

5. Review PASS 或 PASS_WITH_WARNINGS 后，使用已有
`GET /api/v1/workflows/{id}/human-gates` 和
`POST /api/v1/human-gates/{gate_id}/decision` 提交用户决定。
必须传入当前 `expected_state_version` 及 Gate 绑定的 `expected_artifact_version`。
支持 APPROVE / REJECT / MODIFY / REQUEST_ALTERNATIVE / CANCEL。
后三种规划反馈以 `reason` 保存结构化 directive，进入下一轮 Planning Context；不会直接改写旧 Plan。
过期审批返回 409 / VERSION_CONFLICT。对象级 Decision / Plan Lock 沿用已有 Lock API。

6. 需求出现必须由用户决定的歧义时，Brief 为 NEEDS_HUMAN，Workflow 为 BLOCKED。
先查询 Brief 中的 issue / impact / user_decision_needed，再提交澄清：

```http
POST /api/v1/workflows/<workflow_id>/requirement
Content-Type: application/json

{
  "event_id":"<新的 UUID>",
  "expected_state_version":5,
  "expected_brief_version":1,
  "raw_requirement":"完整的修正后需求，包括本次澄清。"
}
```

版本值取自实际查询，不使用示例数字。此操作取消过期任务与 Gate，将旧 Brief 标为
SUPERSEDED，重新解释并生成下一 Brief；历史内容不可修改。C07 后不再接受本阶段的需求修正。
低/中影响歧义应记录 assumption 后继续；仅高影响、低置信度且无法安全推断时升级决策。

CP-003A v1 只读取自然语言输入、目标章节、相关有效约束及最小 Project 信息；
CP-004 v3 强制 exact current Brief P0，同一 Brief 的重规划显式读取上一 Plan / Review；需求修正后排除旧 Brief 的 Plan、Review 和返工指令；
CP-004R v1 只评审 exact Brief 与 exact Plan，不复用正文 Review 的 CP-006。
旧 Mock Planning 继续使用 CP-004 v2。上一章只读取 approved_version，新增 Draft 不替换已批准正文。
Brief 的用户约束保留原文引用；既有七类 Requirement 保持原类型与完整正文，QUALITY_EXPECTATION / CHANGE_REQUEST 分别进入 quality_expectations / change_requests。
推断单列为 assumptions；重大变更始终为 PROPOSAL_ONLY，
长期偏好只生成候选，不自动创建 Requirement / Decision / Canon。
Plan 的 coverage 区分 SCENE 与 PLAN_GLOBAL：全局叙事/保留约束可通过 constraints 或 preserved_elements 说明覆盖，不强制创建场景。

迁移 head 现在是 `0008_requirement_planning`，新增 `creative_briefs`、`plan_generations`、
`plan_review_reports`。0007 已归属 Context Engine，所有历史迁移保持原样。
`downgrade -1` 会删除这三个新增证据表，保留 0001–0007 的业务、Workflow、Run、Context、
Lineage 和审计记录；再次升级不会恢复已删除的 007 证据。迁移往返在隔离测试库验证。

```bash
uv run --locked pytest -q tests/test_planning_contracts.py tests/core/workflow/test_planning_vertical_slice.py
# 以下命令明确选择付费真实模型，需人工执行；默认完整 pytest 会跳过。
uv run --locked pytest -q tests/core/workflow/test_planning_live.py --live-model
```

真实模型测试最多执行七次尝试并使用隔离测试 schema；它不代表全面的语义质量评估。
实现与最终验收记录见 [NOVEL-007 实现报告](docs/reports/NOVEL-007-implementation.md)。

### Writing Vertical Slice — NOVEL-008

NOVEL-008 将正式流程推进到 `C08_DETERMINISTIC_CHECK`。沿用规划流程的 Brief、Plan Review 和 Human Plan Gate；批准 Plan 后自动调度 `A04_WRITING / WRITE_CHAPTER`。Worker 通过 CP-005 v3、版本化 Writing Prompt 和同一个 Pydantic 输出契约生成正文。确定性校验通过后，系统创建不可变 `ChapterVersion DRAFT` 和可追溯生成记录。

新入口：`POST /api/v1/workflows/chapter-writing`。请求字段与已有规划入口相同：

```json
{
  "event_id": "<new UUID>",
  "project_id": "<existing Project UUID>",
  "chapter_id": "<existing Chapter UUID>",
  "raw_requirement": "两人在雨夜会合，决定沿河寻找失落的信件。不要新增核心能力。"
}
```

1. 复用 `/workflows/{id}/events` 提交 `USER_SUBMITTED` 和当前 `expected_state_version`。
2. 启动 Worker：在 `backend/` 执行 `uv run python -m novel_os.worker --config config.toml`。默认 Mock，不调用外部模型。
3. 等待 C06，通过 `/human-gates/{gate_id}/decision` 提交 `APPROVE`、准确的 `expected_artifact_version` 与工作流状态版本。
4. Worker 自动执行 Writing；读取 `/workflows/{id}/writing/history` 查看生成记录，通过已有 `/projects/{project_id}/chapters/{chapter_id}/versions/{version}` 查看正文。
5. 流程停在 C08，没有正文 Review/Revision/Memory Agent 任务。

新入口使用 `chapter-planning` **v2**；原 `/workflows/chapter-planning` 仍使用 v1 并停在 C07。历史实例和已发布定义不改写。迁移为 `0009_writing_agent`，其父版本为 `0008_requirement_planning`。

Writing 绑定具体已批准 Plan 的 ID/version，不取 current/latest。即使存在 Plan v2 PROPOSED，已批准 v1 仍是 Writing 输入。任务创建时冻结输入指纹，在调用模型前和保存结果前重新验证审批、锁、Brief、Context 与工作流状态。只有有效的批准版本进入 CP-005；未来信息只通过精确、必要的依赖进入，未来 Plan 还必须已批准。GLOBAL_ONLY 不构成人物知识授权。

生成新正文仅更新 `current_version`，保留 `approved_version`。LOCAL 偏离可继续，MODERATE 留下显式元数据；MAJOR、requires_replan、明确的禁止项违反、核心方向改变和确认的人物知识泄漏会 BLOCK，保存检查原因但不保存为正常正文版本。小型 proposed facts 仅为生成元数据，没有 Canon 写入。

`GET /api/v1/workflows/{id}/writing/history?limit=100&offset=0` 返回正文版本 ID、Task/Run、Plan、Brief、PromptLineage、ContextPackage、模型配置、正文哈希、Writing metadata 和确定性检查结果。正文不混入元数据，也不重复存进生成记录。

在 C08 可由用户通过 `POST /api/v1/workflows/{id}/writing/regenerate` 请求新的业务版本：

```json
{
  "event_id": "<new UUID>",
  "expected_state_version": 9,
  "expected_draft_version": 1,
  "reason": "在同一个已批准计划内生成另一版表达"
}
```

两个版本令牌应使用实际查询值。该操作创建新 Task 和新正文版本，不修改历史正文，也不属于技术重试。模型超时或格式错误仍使用原 Task 的新 Run，成功前不创建正文版本。

正式流程从暂停或阻塞恢复到 C08 时，保留已经通过 Writing 检查的 `draft_version`。期间通过 Core API 独立创建的正文不会被自动绑定到工作流；当它与工作流正文版本不一致时，再生成返回版本冲突，保留用户编辑。如果 C08 所绑定的批准 Plan 已失效，再生成或恢复会记录 BLOCKED，并将恢复目标设为 C04；再次 RESUME 后重新规划、审查并通过用户 Plan Gate，才会生成新正文。

Writing 启用 `scene-execution`、`dialogue`、`character-voice`、`narrative-rhythm`、`natural-prose` 五个技能。自然性规则是文学表达指导，不是词语禁令、句长配额或 AI detector 规避；Writer 不输出可被系统信任的 quality_pass。

仍使用 TOML 文件配置。`agent_model_profile = "mock-default"` 为 Writing 选择 `mock-writing`；显式配置 `openai-structured` 时选择 `openai-writing`。Writing profile 默认预留 8192 输出 token、90 秒超时，记录到 PromptLineage；单章单次生成，技术重试另开 Run。Mock 正文是固定离线契约样例，不衡量任意用户需求的文学完成度。

```bash
cd backend
uv run pytest tests/test_writing_contracts.py tests/core/writing
uv run pytest
uv run ruff check
uv run ruff format --check
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run alembic check
uv build
```

真实 Writing smoke 默认跳过。仅在本机忽略的 `config.toml` 配好密钥且明确同意外部调用费用后，手动执行：

```bash
uv run pytest tests/core/writing/test_live.py --live-model
```

该测试使用独立测试 schema、Mock 规划后经用户门批准的测试 Plan，最多进行三次 Writing 调用。文学质量、角色一致性、完整需求 Review 和正文验收属于后续 Ticket。本阶段的确定性检查只证明契约、权限、来源和持久化关系正确，不证明文学质量。

## DEV-UI-001 / UX-001：个人创作工作台

`frontend/` 提供 Vue 3 + TypeScript + Vite 单页个人创作工作台。默认界面只呈现项目、章节、需求、方案和正文；Workflow、AgentRun、ContextPackage、PromptLineage 和原始 JSON 收纳到 Debug 抽屉。它复用正式 `chapter-planning v2` Workflow，到 `C08_DETERMINISTIC_CHECK` 停止；不提供 NOVEL-009 的审校或章节验收。

### 启动三个进程

首次使用先按上文准备 `backend/config.toml`、Docker 配置和数据库。推荐保留默认 `agent_model_profile = "mock-default"`，先跑通工程流程。Mock 的内容是固定契约样例，不能用它评价任意自然语言需求的理解能力或文笔。真实模型仍只在 Backend TOML 配置；切换前自行确认外部调用与费用。控制台没有密钥输入框。

1. 在仓库根目录启动数据库和 Backend（更新代码后应重建镜像）：

   ```bash
   docker compose up --build -d --wait backend
   docker compose run --rm --no-deps backend /app/.venv/bin/alembic upgrade head
   ```

2. 在另一个终端启动独立 Worker，保持进程运行：

   ```bash
   cd backend
   uv run --locked python -m novel_os.worker --config config.toml
   ```

   也可在仓库根目录执行 `docker compose --profile worker up --build -d worker`，使用同一份渲染后的 TOML 启动独立 Worker 服务；用 `docker compose logs --tail=30 worker` 检查状态。Worker 不随 FastAPI 启动。不要同时启动两种 Worker 以免混用执行范围。停止容器执行器用 `docker compose stop worker`。

3. 使用 Node.js 22.12+（本次验证 22.22.0）启动前端：

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

   浏览器打开 **http://127.0.0.1:5173**。Vite 将 `/api` 代理到 `http://127.0.0.1:8000`，没有扩大 Backend CORS。前端单独运行 Vite，用于本机单用户创作和人工测试。

### 浏览器操作

1. 在左侧展开 **＋ 新建项目** 和 **＋ 新建章节**；已有项目用顶部 Select 切换，章节直接从列表选择。
2. 在 **章节需求** 输入自然语言，点击 **生成方案**。页面会依次显示“AI 正在理解需求”和“AI 正在设计方案”，无需处理 JSON 或内部 ID。
3. 阅读 **AI 对需求的理解** 和 **章节方案**。可以点击 **批准并开始写作**、**换一个方案** 或 **我想修改**；修改仍经正式 HumanGate 生成新 Plan 版本。
4. Writing 完成后在居中阅读器阅读 Draft。点击 **人工评价** 可将评价导出为本地 JSON，不会修改 Workflow 或正文。
5. **写作偏好** 位于左侧项目区；保存新版本和批准仍是两个独立操作。
6. 开发模式下可用 **测试** 载入 `evals/manual/` 的 Case 01—05 原始需求。Case 只能在尚未开始的章节载入，仍完整经过 Requirement、Planning 和 Writing。
7. 点击右上角 **Debug** 查看 Workflow History、Task/Run、ContextPackage、PromptLineage、WritingProfile 版本和原始结构化数据。Debug 默认关闭。

界面在运行阶段每 1.5 秒查询，人工审批、暂停、Blocked、Failed、Cancelled 和本阶段终点停止轮询。点击 **刷新** 获取最新状态。浏览器本地只记住上次项目、章节、未提交的需求草稿和 Debug 开关；Backend 仍是 Workflow 与业务数据的 source of truth。

遇到 `VERSION_CONFLICT` 会提示“当前方案已发生变化，请刷新后重新审批。”，并禁用该次审批；不会自动重试。重新刷新、阅读当前版本后再决定。错误展示 code、message、request_id。后台持久化失败状态没有原 HTTP request_id 时会明确标记，可改用 Debug 的 Run ID 排查。Blocked 会展示原因；可在 **流程控制** 使用已有恢复/暂停/取消操作。需求澄清的专用重提表单未纳入本界面，遇到 `NEEDS_HUMAN` 可取消该流程，在新流程提交澄清后的需求。

### 前端配置与 Debug

默认无需额外配置。`frontend/.env.example` 只保留公开的同源 API 路径示例：

```dotenv
VITE_API_BASE_URL=/api/v1
```

这是**公开的浏览器配置**，Backend 仍只读取 TOML。API base 仅允许同源相对路径；修改后需与 Vite proxy / Backend 前缀匹配。不要放 Provider Key、数库地址或任何秘密；Vite 禁止从项目外读取 Backend 配置。界面只展示 Backend 提供的模块版本与哈希，不重建 Prompt。人工 Case 入口只在 Vite 开发模式显示。

### 验证与 API 类型同步

在 `frontend/` 执行：

```bash
npm run typecheck
npm run lint
npm test
npm run build
```

浏览器 E2E 使用真实 Backend / Worker / PostgreSQL API，强制 Mock。在仓库根目录启动测试库，再运行：

```bash
docker compose --profile test up -d --wait postgres-test
cd frontend
npx playwright install chromium
npm run test:e2e
```

测试使用 8011 / 5174 端口和测试库中的临时 schema，结束后清理；不改开发库、不增加测试控制 API、不消费真实模型 API。测试中的 `[E2E:MODEL_FAILURE]` 只由测试宿主识别，普通开发 Worker 没有该入口。开发环境如需手测失败，可按上文 TOML 配置 `agent_mock_scenario = "ALWAYS_FAIL"` 并重启 Mock Worker，完成后恢复 `SUCCESS`。

`src/types/api.generated.ts` 来自实际 FastAPI OpenAPI，纳入源码管理；普通构建无需运行 Backend。后端 DTO 变更后启动最新版 Backend，在 `frontend/` 执行 `npm run types:api`，审查生成差异并运行上述检查。前端运行时仅依赖 Vue，无 Router、Pinia 或大型 UI 库。

控制台使用的附加只读 API：

- `GET /api/v1/projects/{project_id}/chapters/{chapter_id}/workflows`：按项目/章节找回流程，支持分页。
- `GET /api/v1/agent-runs/{run_id}/context`：读取具体运行尝试的 Context，避免用 Task 的最新 Context 误解释早期重试。
- `GET /api/v1/agent-execution/config`：返回 Backend 的模型和任务执行范围、次数上限，不返回凭据，也不表示 Worker 已在线。Backend 与 Worker 应使用同一配置。

其余操作复用既有 API；审批只调用 HumanGate，客户端不能提交 authority、actor、approved state 或直接运行 Agent。实现与验证结果见 [DEV-UI-001 报告](docs/reports/DEV-UI-001-implementation.md) 和 [UX-001 报告](docs/reports/UX-001-personal-creative-workspace.md)。

### Requirement 单次语义测试：Lingzhi

Novel OS 使用自己的 `backend/config.toml`，不读取环境变量或 Codex CLI 配置：

```toml
agent_model_profile = "mock-default"
requirement_smoke_profile = "lingzhi-requirement"
lingzhi_base_url = "https://lingzhi.agibot.com/v1"
# lingzhi_api_key = "只写入本机被 Git 忽略的配置文件"
```

`backend/novel_os/providers/profiles.toml` 中的 `lingzhi-requirement` 选择
`gpt-5.6-sol`，Responses API、120 秒 timeout、8192 输出 token 上限。独立密钥字段
避免 Lingzhi 凭据被误发给 OpenAI 官方端点。后台 Worker 仍保持 Mock；这个测试设置
不会启动 Worker，也不会自动开启真实 Planning/Writing。

同一配置文件的 `[context_windows.<provider>]` 按实际 model 声明输入与输出合计的窗口上限。
Context 预检采用 `min(Context Profile budget, model window)`，扣除 Prompt/Schema 和输出预留，
使用现有保守 UTF-8 估算；P0 放不下会阻断，不截断原文。发送前还会检查完整 Prompt。
真实模型缺少窗口配置时拒绝执行；Gateway 若限制更小，应降低对应配置并重启 Worker。
窗口配置独立于生成参数，不改变历史 ModelProfile hash；ContextPackage 记录本次实际预算。
已冻结在旧 RevisionRequest 中的 Context Profile 不随配置更新；此类预算阻断需显式重新审阅，
再发起新修改请求。

获得一次真实调用授权后，停止后台 Worker，从 `backend/` 执行：

```bash
uv run pytest tests/core/workflow/test_requirement_semantics.py::test_case01_one_live_requirement_attempt --live-model -s
```

只执行一条 Case01 Requirement 尝试，失败不自动重试，隔离测试库，保存完整链路证据。
再次运行就是一次新的外部调用。默认 `pytest` 跳过真实调用。细节见
[Requirement eval](evals/requirements/v0.1/README.md) 和
[Case01 诊断](docs/reports/requirement-case01-diagnosis.md)。

### 在浏览器人工运行一次 Requirement

在本机 `backend/config.toml` 设置以下字段，密钥仍只写入该文件：

```toml
agent_model_profile = "lingzhi-requirement"
agent_execution_scope = "requirement-only"
agent_max_attempts = 1
```

它与 `requirement_smoke_profile` 不同，控制真正领取页面任务的 Worker。仅领取正式
`PARSE_CHAPTER_REQUIREMENT`，包括该类型过期租约的恢复；不领取 Planning、Plan Review、
Writing 或模拟任务，也不为旧流程补调度其他阶段。尝试上限写入不可变 AgentRun 的
`input_metadata.attempt_limit` 并随 Run 审计；不修改不可变的 Task 原始预算，且后续恢复
只能收紧上限。超时或进程失联后不会进行第二次模型调用。默认 `all` / Mock 保留原有执行行为。

启动 Worker 会消费已有待执行需求。要由测试者手动决定调用时间，应**先在界面暂停
已有流程**，然后重新渲染配置、重建 Backend，并启动本机独立 Worker（以下命令从 `backend/` 执行）：

```bash
uv run python -m novel_os.infrastructure.prepare_docker
docker compose -f ../docker-compose.yml up --build -d backend
uv run --locked python -m novel_os.worker --config config.toml
```

Lingzhi 是内网域名。本机网络验证可访问，但本次 Docker 容器出现 DNS 解析失败，因此
本机 Worker 是当前已验证的运行方式。不要同时启动 Compose Worker。只有确认容器自身
能够解析并通过 TLS 访问该域名后，才改用可选的 Compose Worker；不要固定内网 IP 或关闭 TLS 验证。

重载浏览器后应显示 `lingzhi / gpt-5.6-sol` 和仅执行 Requirement。点击暂停流程上方的
**继续理解需求（调用真实模型）**，复用原 Workflow Resume 操作；不需重填原文。
新测试点击 Start Workflow 也会产生一次模型尝试。每次手动提交或恢复都是新的执行决定，
不是整个服务器总共只允许一次调用。页面本身不调用 Provider，也不提交模型名或密钥。

状态显示：`PENDING` 为“等待后台执行”，`CLAIMED` 为“任务已领取，准备执行”，
`RUNNING` 才显示“正在理解需求”。Requirement 成功后阅读 CreativeBrief；下一阶段显示
“本阶段执行已停用”，停止自动轮询，Planning / Writing 保持等待。失败显示终态及错误码。
后台配置更改需要重启两个进程并重载页面。

如果先前尝试已经进入 FAILED，旧记录会保留，不会被重写为成功。使用相同原文创建新
Workflow 进行下一次人工测试；点击 Start Workflow 才发起新尝试。

若人工测试返回 `SCHEMA_PARSE_ERROR`，诊断前可在本机 `backend/config.toml` 设置
`agent_capture_outputs = true` 并重启 Worker。默认关闭；它只保存之后实际执行的响应，
不会触发调用，也无法恢复此前未保存的响应。仍须人工决定是否发起新的付费尝试。

捕获文件位于 Worker 工作目录下的 `.runtime/agent-output/<task_id>-<attempt>.json`，
包含模型原文、模型/Prompt/Schema 标识和用量摘要。目录权限 0700、文件 0600，
Git 忽略且不由 API 提供下载；不保存密钥、请求头或 Provider 错误正文。内容可能含
故事文本，只供本机诊断；完成后关闭配置并自行清理这些文件。捕获失败不会覆盖
历史文件、改变模型返回值或额外重试模型；原有 Parser 与业务校验继续严格执行。

### 开放后续 Planning / Writing 阶段

在人工确认继续真实模型流程后，把本机 `backend/config.toml` 改为：

```toml
agent_model_profile = "lingzhi-structured"
agent_execution_scope = "chapter-writing"
agent_max_attempts = 1
```

这个独立 Profile 使用同一 Lingzhi 网关、`gpt-5.6-sol`、120 秒 timeout、8192 输出
token 上限，只领取四种正式业务任务（不领取模拟任务），用于 Requirement、Planning、Plan Review 和 Writing。旧的
`lingzhi-requirement` 保留原来的执行范围约束与历史 hash。配置仍只来自 TOML。

停止当前 Worker，按上文重新渲染 Docker 配置、重建 Backend，再启动本机 Worker，
并重载页面。已排队的 Planning 会从原 Workflow 继续，无须重新创建或重复执行
成功的 Requirement。每个任务最多一次模型尝试；方案质量未通过时，现有 Workflow
可能创建新的 Planning 迭代，这与技术重试不同。继续流程会调用真实模型。

Plan Review 之后仍须在页面完成人工方案审批；Worker 不代替用户批准。
通过审批后，Writing 流程才调度正文生成；未实现后续 NOVEL-009 阶段。

若本机 Docker 重建受依赖下载影响，可使用已有锁定依赖运行 Backend。先在仓库根目录
执行 `docker compose stop backend worker`，确认 8000 端口已释放；PostgreSQL 保持运行。
然后在 `backend/` 的两个终端分别启动：

```bash
uv run --locked uvicorn novel_os.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

```bash
uv run --locked python -m novel_os.worker --config config.toml
```

本机 Backend 和 Worker 均读取 `backend/config.toml`，仍连接原 Docker PostgreSQL。
不要同时在同一端口启动 Docker Backend；切回 Docker 时先停止本机 Backend。

### Plan Review 校验与自动迭代边界

新 Review 使用 `chapter-plan-review-result.v2`：`MISSING_MUST` 和
`FORBIDDEN_VIOLATION` 必须绑定 Brief 中相应硬约束 ID；`missing_requirements`、
`forbidden_violations` 存放 ID，描述放在对应 issue 的 `description`。
这些 ID 的 coverage 必须为 `false`，硬错误只能对应 FAIL。
旧报告仍以只读形状展示，历史矛盾不会被改写，也不能作为新 v2 输出重新接受。

Planning 的 CP-004 v4 将输入分成 `authoritative_constraints`（带来源的 Brief
硬约束投影）、`review_revision_targets`（仅上一轮真实硬问题）、`recommendations`
（仅上一轮可选建议）。Review 保持 `A7_AI_INFERENCE`。Service 只允许 Brief
MUST/FORBIDDEN/CHANGE_REQUEST 的原文进入 Plan.constraints，PRESERVE 进入
preserved_elements；合法类别/ID 标签可以被规范化，其他新增约束被拒绝。具体创意留在
scenes、assumptions 等提案字段，Review 文本不得累积成用户或系统规则。

同一 Brief、同一次人工规划指令最多自动生成两份 Plan。第二轮仍 FAIL 时保留失败报告，
进入 `C90_BLOCKED / PLANNING_ITERATION_LIMIT`；直接 RESUME 不会再消费模型调用。
检查失败原因后，可通过现有需求修正入口提交人工澄清，生成新 Brief。人工在通过后的
Plan Gate 请求修改也会开始新的两轮预算。质量建议、over-specification 本身只能警告，
不会为了凑 PASS 而忽略真实硬错误。

人工只测 Requirement → Planning → Review 时，在本机 `backend/config.toml` 设置：

```toml
agent_model_profile = "lingzhi-structured"
agent_execution_scope = "planning-only"
agent_max_attempts = 1
```

此范围不领取 Writing。修改后重启 Worker；Docker 配置也需重新运行 `prepare_docker`。
发布 v2 Review contract 前应停下 Worker、排空旧 v1 的 unfinished tasks，或通过带审计的
取消/重新启动流程处理；不要修改不可变任务的 `expected_output_schema` 或旧 Prompt pin。
旧 v1 未完成任务不能直接交给仅支持新 contract 的 Worker。本次本机发布已确认无此类任务。


### Project Writing & Audience Profile（STYLE-001）

测试台选择项目后可编辑读者与写作偏好。`Load Web Fiction Test Profile` 只填表，
必须先 **Save Draft**，再单独 **Approve Profile vN** 才会影响后续模型上下文。
当前 Draft 与批准版本分离；所有版本均保持 `A5_USER_PREFERENCE`，不能覆盖章节硬要求、
Canon、锁定方向或已批准 Plan。没有批准 Profile 时不注入默认受众偏好。

Profile API 位于 `/api/v1/projects/{project_id}/writing-profile`：GET 根路径读取
current/approved；GET `/approved`、`/versions`；POST `/drafts` 创建不可变新版本；
POST `/approve` 绑定 `expected_version` 批准当前 Draft。已批准内容不可原地修改。
新版本批准会使旧上下文失效，必要时须重新 Planning 并重新通过人工 Plan Gate。

修改前先运行 `uv run --locked alembic upgrade head`（0010）。本阶段不增加依赖，
不配置环境变量，不自动从 Human Reject 学习偏好，也不实现 NOVEL-009。

Case 01 原始证据和受控人工 A/B 步骤见
[case01_style_ab](evals/writing/v0.1/case-01/case01_style_ab.md)。真实 A/B 需要新的明确 opt-in；
只读 `scripts/case01_style_ab.py` 不调用模型。完整实现报告见
[STYLE-001](docs/reports/STYLE-001-project-writing-profile.md)。

### NOVEL-009 正文审阅

新建的工作台流程使用 `chapter-planning.v3`：正文 → 约束审阅 → 叙事/受众审阅 → 等待人工决定。已有流程保持原定义，审阅不会自动修订正文。

审阅期间新增正文版本会使旧任务失效。刷新工作台后，“重新审阅正文 vN”会提交页面所见的当前版本，创建新的两轮审阅，保留旧结果。API 调用 `POST /api/v1/workflows/{id}/resume` 时可传 `expected_draft_version`；正文已变化但未提供正确版本时返回 409。审阅完成后，也可通过 `POST /api/v1/workflows/{id}/quality-review` 提交当前正文版本进行显式复审。未批准的 Plan Draft 不影响基于原批准 Plan 的审阅。

在本机 TOML 中设置 `agent_execution_scope = "chapter-quality"` 才允许执行两个新审阅任务。离线验证使用 `agent_model_profile = "mock-default"`。真实 Provider 扩大执行范围会允许付费调用，应仅用于用户明确授权的运行；本次开发和测试没有修改现有付费 Worker 的本机配置。配置继续使用文件，不需要环境变量。

历史 Case 01～05 评估与显式真实调用步骤见 [evals/quality](evals/quality/README.md)。设计与 API 见 [Quality Engine](docs/specs/07-Quality-Engine.md)，验证结果见 [009 实施报告](docs/reports/NOVEL-009-quality-review-engine.md)。

### NOVEL-011：用自然语言修改当前正文

在当前 Draft 页面点击 **我想修改**，描述不满意之处和需要保留的内容，点击 **发送并修改**。系统理解反馈后执行一次局部修改、Fidelity 检查与重新审阅，然后停止。可在历史版本中查看原稿和反馈；人工评价保持独立。

修改已批准故事方向会要求显式返回方案流程；持续写作偏好会打开已有 Profile 编辑/审批路径；锁定或矛盾指令不会被静默覆盖。历史版本只读，当前版本变化时需要重新阅读后提交。

更新后先执行 `alembic upgrade head`（当前 0015），重建/重启 Backend 和 Worker。`chapter-quality` 执行范围新增 `INTERPRET_CHAPTER_FEEDBACK`。仍只使用 `config.toml`；真实 Provider 会消费 API，按本机配置的单任务尝试上限执行。数据库已有反馈记录时，0014 downgrade 会拒绝删除不可变历史；0015 在已有澄清关联时也拒绝降级。

“补充修改要求”会结合原反馈和问题处理，保留原有范围与保留要求。如果等待解读时正文或批准的写作依据发生变化，可点击“放弃本次反馈，返回当前正文”，再针对当前版本重新提交；放弃不会修改正文或删除历史，也不会调用模型。

设计与接口见 [Human Feedback](docs/specs/09-Human-Feedback.md)。未实现 NOVEL-012。
