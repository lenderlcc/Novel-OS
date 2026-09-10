# NOVEL-001 配置 Review 修复

日期：2026-09-10。范围仅为 NOVEL-001，等待用户 Review。

## 1. Implementation Summary

- 按用户最新要求改为 TOML 文件配置，替换原 `.env.example`；Pydantic Settings 只接受
  显式传入的文件数据或程序内参数，禁用环境变量、dotenv 和环境 secrets 配置来源。
- API、Alembic 和 pytest 统一读取工作目录中的 `config.toml`。
- `postgres_url` 和 `test_database_url` 保留完整连接 URL，测试配置不再拆解、重建 URL。
  `sslmode`、证书、多主机、`application_name` 和显式超时参数完整传递给驱动。
- Compose 删除 `environment` 和 `env_file`，通过 `prepare_docker` 从 TOML 生成只读挂载文件。
  后端不接收测试库凭据；开发库和测试库各自只接收自己的初始化文件。
- PostgreSQL 使用 `initdb --pwfile`、`createdb` 及启动参数读取文件配置。复用已有开发数据
  volume，测试服务仍使用独立 tmpfs，未创建业务表。
- 已将本机已有凭据迁移到权限 0600 的 `backend/config.toml`，验证一致后移除旧 `.env`。
  生成目录 `.runtime/` 权限为 0700；实际凭据均被 Git 和 Docker build context 排除。

## 2. Files Created/Modified

新增：

- `backend/config.example.toml`
- `backend/novel_os/infrastructure/prepare_docker.py`
- `backend/docker/postgres-start.sh`
- 本修复报告

修改：

- `backend/novel_os/core/config.py`、`main.py`、`db/session.py`、`backend/alembic/env.py`
- `backend/tests/conftest.py`、`test_config.py`、`backend/pyproject.toml`
- `docker-compose.yml`、`backend/Dockerfile`、`.gitignore`、`backend/.dockerignore`
- `README.md`、首次实现报告的历史说明

移除：`backend/.env.example`，由 TOML 示例替代。Spec、Ticket 和业务层未修改。

## 3. Dependencies

未新增或升级第三方依赖，`uv.lock` 未改变。TOML 解析使用 Python 标准库 `tomllib`，
继续使用现有 Pydantic Settings、SQLAlchemy 和 PostgreSQL 16 镜像。
`uv lock --check` 通过。

## 4. Test Result

`uv run --locked pytest`：**38 passed，0 failed，0 skipped，2 dependency warnings**。
包含 4 项真实 PostgreSQL 集成用例。

新增回归覆盖：实际 TOML 解析、环境与 dotenv 不生效、特殊字符密码在生成配置中一致、
测试 URL 的 TLS/多主机/超时选项到达驱动、测试库隔离、不同服务凭据隔离、严格 umask 下容器读取权限、无效配置失败及脱敏。

Docker 验证：

- backend 镜像构建成功，三个 Compose 服务均 healthy。
- 两个健康接口均返回 200。
- 独立临时 PostgreSQL 容器使用含 `${...}`、引号及 URL 保留字符的假密码，
  通过 TOML → 挂载文件 → initdb 初始化后真实认证并执行 `SELECT 1`；错误密码被拒绝。
  探针容器及临时文件已清理。
- 检查 Compose 展开结果及运行容器，确认没有应用/数据库凭据环境变量。
- 已有开发 volume 复用成功；测试库从空 tmpfs 初始化成功。

## 5. Migration Result

宿主机和后端容器内分别执行以下顺序，均退出 0：

```text
alembic upgrade head
alembic downgrade -1
alembic upgrade head
alembic current
```

最终为 `0001_bootstrap (head)`；宿主机 `alembic check` 返回
`No new upgrade operations detected`。迁移文件和业务 schema 均未改变。

## 6. Lint Result

- `uv run --locked ruff check`：PASS。
- `uv run --locked ruff format --check`：PASS，35 files already formatted。
- `git diff --check`：PASS。
- `docker compose config --quiet`：PASS。
- `docker compose --progress plain build backend`：PASS。

独立只读五轴代码复核未发现 Required 问题；动态验证由主执行者完成。

## 7. Known Issues

- 保留现有 2 条 Starlette/AnyIO 依赖弃用警告；未隐藏警告或升级依赖。
- 本次验证环境为 Python 3.13、PostgreSQL 16 和 macOS/Colima Linux arm64。
- 完整 URL 中的凭据保留字符仍需百分号编码；这是 URL 语法要求，不涉及环境变量插值。
- 修改 TOML 后需要重新生成 Docker 挂载文件并重启服务；配置不是热更新。
- 初始化文件不会自动修改既有数据库账号。已有 volume 的密码变更仍需同步修改数据库。
- 配置生成器用于本机 Compose 服务，拒绝外部 host、地址覆盖 query、换行或 NUL 凭据。
  直接连接外部 PostgreSQL 的应用/测试仍可使用完整 URL 的连接参数。

## 8. 是否存在超出 NOVEL-001 Scope 的实现

**不存在。** 未增加任何 Project、Chapter、Agent、LLM、Workflow 等业务实现，
未引入 Redis、Kafka 或 Vector DB，未使用 sudo 生成项目文件。未提交或推送代码。
