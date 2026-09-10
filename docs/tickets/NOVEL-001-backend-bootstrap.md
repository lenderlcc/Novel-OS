# NOVEL-001 — Bootstrap Novel OS Backend

**Priority:** P0  
**Status:** READY FOR DEVELOPMENT

## Goal

建立最小可运行 Backend：

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic Settings
- Structured Logging
- Request ID
- Health API
- pytest
- Docker Compose

## Non-Scope

禁止提前实现：

- Project / Chapter 业务模型
- Agent
- Prompt
- Workflow
- LLM
- Redis / Kafka / Vector DB

## Required Structure

```text
backend/
├── pyproject.toml
├── alembic.ini
├── .env.example
├── alembic/
├── novel_os/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── domain/
│   ├── services/
│   ├── repositories/
│   ├── workflow/
│   ├── agents/
│   ├── memory/
│   ├── context/
│   ├── quality/
│   └── infrastructure/
└── tests/
```

## Required Endpoints

- `GET /api/v1/health`
- `GET /api/v1/health/db`

DB down 时 `/health` 仍 200，`/health/db` 返回 503。

## Architecture Rules

- API → Service → Repository → DB
- Domain 不依赖 FastAPI
- Repository 不自行 commit
- Migration 不在 app startup 自动执行
- Secret 不进 Git
- Test DB 与 dev DB 分离

## Deliverables

- FastAPI create_app
- PostgreSQL service
- SQLAlchemy session/base
- Alembic initial migration
- `.env.example`
- structured logging
- request-id middleware
- unified error schema
- Dockerfile / docker-compose
- pytest fixtures
- README

## Acceptance Criteria

1. `docker compose up --build` 正常
2. `/api/v1/health` = 200
3. `/api/v1/health/db` = 200
4. DB down 时 `/health/db` = 503
5. `alembic upgrade head` 成功
6. `alembic downgrade -1` 成功
7. `pytest` 全过
8. `ruff check` 通过
9. Response 含 X-Request-ID
10. 无 hard-coded secret
11. Domain 不依赖 FastAPI
12. 未提前实现 NOVEL-002

## Codex Instruction

只执行 NOVEL-001。完成后输出：
- Implementation Summary
- Files Created/Modified
- Dependencies
- Migration Result
- Test Result
- Lint Result
- Acceptance Criteria PASS/FAIL
- Known Issues
- Scope Deviations

不得自行继续 NOVEL-002。
