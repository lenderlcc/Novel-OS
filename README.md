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
prompts/         Prompt Library
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
- Actual Implementation: `NOVEL-002 — Core Domain & Persistence`，已完成代码审查与修复
- NOVEL-001: 已通过 Review，沿用 TOML 配置和现有基础设施
- Next Action: 等待后续开发指令；尚未开始 NOVEL-003

具体规格见 `docs/specs/`，开发任务见 `docs/tickets/`。

## Backend Development

当前实现工程基础设施、健康检查，以及 NOVEL-002 的八类核心对象、版本、审批、锁和审计。
上面的产品 Pipeline 是后续设计目标；尚未实现 Workflow、Agent、LLM 或前端。

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
NOVEL-002 每项集成测试在测试库中创建独立临时 schema，结束后清理自己的 schema。
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

当前 revision 是 `0002_core_domain`，前驱为 `0001_bootstrap`。新增八张核心业务表、
外键、唯一约束，以及保护正文、已批准内容和审计记录的 PostgreSQL trigger。
`downgrade -1` 会删除这八张业务表及其中的数据；升降级验证应使用空库或独立测试库。
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
