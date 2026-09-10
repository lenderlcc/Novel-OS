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
- Actual Implementation: `NOVEL-001 — Backend Bootstrap`，待 Review
- Next Action: Review NOVEL-001；尚未开始 NOVEL-002

具体规格见 `docs/specs/`，开发任务见 `docs/tickets/`。

## Backend Development — NOVEL-001

当前仅实现工程基础设施和健康检查。上面的产品 Pipeline 与后续目录是设计目标，
不是已实现的功能。`workflow/agents/memory/context/quality/infrastructure` 仅保留包占位。

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

从仓库根目录执行：

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，将 `POSTGRES_PASSWORD` 替换为本地开发密码，并同步修改
`TEST_DATABASE_URL` 中的密码（URL 特殊字符需编码）。示例密码仅是占位符。
`.env` 已被 Git 与 Docker build context 忽略，不要提交实际密码。

Settings 从 `backend/.env` 读取配置，环境变量优先；Compose 同样读取这个文件。
应用的数据库 URL 由 `POSTGRES_*` 字段通过 SQLAlchemy `URL.create` 生成，
因此应用侧的 `POSTGRES_PASSWORD` 可以直接包含特殊字符。

| 配置 | 默认值 / 用途 |
| --- | --- |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `127.0.0.1` / `55432`；Compose 后端覆盖为 `postgres:5432` |
| `POSTGRES_USER` / `POSTGRES_DB` | `novel_os` / `novel_os_dev` |
| `POSTGRES_PASSWORD` | 必填，无代码默认密码 |
| `LOG_LEVEL` | `INFO`，可选 DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `DB_CONNECT_TIMEOUT` | 2 秒，单次建连超时 |
| `DB_STATEMENT_TIMEOUT_MS` | 3000 毫秒，SQL 语句超时 |
| `DB_POOL_TIMEOUT` | 3 秒，连接池等待超时 |
| `TEST_DATABASE_URL` | pytest 使用，必须指向独立的、名称以 `_test` 结尾的 PostgreSQL 库 |

### Docker 启动

```bash
docker compose up --build -d
docker compose run --rm backend alembic upgrade head
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/health/db
docker compose logs -f backend
```

API 文档位于 `http://127.0.0.1:8000/docs`。端口仅绑定本机回环地址。
默认启动 backend 与 PostgreSQL 16；开发数据保存在 `postgres_data` volume。
镜像内进程使用非 root 用户。迁移必须显式执行，应用启动不自动迁移或建表。
`docker compose down` 停止服务并保留开发数据。

首次初始化 volume 后，修改环境变量不会自动修改 PostgreSQL 已有的账号或数据库。
开发库与测试库分别映射宿主机 55432、55433，避免与已有的本地 PostgreSQL 5432 冲突。
若 55432、55433 或 8000 已占用，需调整 Compose 端口映射和本地连接配置。

### 本地 Python 开发

```bash
docker compose up -d --wait postgres
cd backend
uv sync --locked --python 3.13
uv run --locked alembic upgrade head
uv run --locked uvicorn novel_os.main:create_app --factory --reload --no-access-log
```

若已有 PostgreSQL 16，也可手工创建相互独立的开发库和测试库，设置 `.env` 后运行相同命令。
无需 Docker 即可运行 Python 服务、pytest 与迁移；Docker 容器验收仍需可用的 Docker runtime。

### 测试与 Lint

从仓库根目录执行：

```bash
docker compose --profile test up -d --wait postgres-test
cd backend
uv sync --locked --python 3.13
uv run --locked pytest
uv run --locked ruff check
uv run --locked ruff format --check
```

测试服务使用 55433 端口和独立的 `novel_os_test` 数据库，数据放在 tmpfs，
与开发数据库 volume 分离。测试 fixture 拒绝非 `_test` 数据库和与开发库同名的数据库。
完整测试包含真实 PostgreSQL 查询与事务回滚验证；缺少测试库配置或连接失败会报错，不会静默跳过。
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

当前 revision 是 `0001_bootstrap`。此迁移刻意不创建业务表，数据库中仅有 Alembic
自身的 `alembic_version`；downgrade 将版本退回 base，保留空的版本表。
`Base.metadata` 已为后续迁移准备好，但本次没有注册任何业务实体。

### API 与错误约定

| 请求 | 正常状态 | 数据库故障 |
| --- | --- | --- |
| `GET /api/v1/health` | 200，`{"status":"ok"}` | 仍返回 200 |
| `GET /api/v1/health/db` | 200，`{"status":"ok","database":"ok"}` | 503，统一错误结构 |

所有 HTTP 响应都包含 `X-Request-ID`。客户端可传入 1–128 个 ASCII 字母、数字、
点、下划线或连字符；缺失、重复或无效的值会替换成 UUID。
404、405、422、503 和未捕获异常均使用统一结构，例如：

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
├── domain/                 不依赖 FastAPI 的异常定义，无业务模型
├── services/health.py       健康检查编排、数据库异常翻译
└── repositories/health.py   SELECT 1，无 commit
```

数据库请求链为 API → Service → Repository → Database。同步数据库调用由同步路由执行，
由 FastAPI 放入线程池。Session 按请求创建，异常时 rollback，退出时关闭；
成功退出也不会自动 commit。未来需要写入的 Service 必须显式拥有事务边界，Repository 不得提交。
进程退出时 dispose 连接池；liveness 与应用启动均不要求数据库可连接。

相关语义参考 [SQLAlchemy Session 文档](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、
[FastAPI 异常处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)、
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 和
[Compose 启动依赖](https://docs.docker.com/compose/how-tos/startup-order/)。
Colima 安装与 Docker 代理配置分别参考 [Colima 文档](https://colima.run/docs/installation/) 和
[Docker daemon 代理文档](https://docs.docker.com/engine/daemon/proxy/)。
