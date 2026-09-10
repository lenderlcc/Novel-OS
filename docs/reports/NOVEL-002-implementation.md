# NOVEL-002 — Core Domain & Persistence Implementation

> 本文保留首次交付时的实现及 102 项测试记录。后续用户已要求整体 Review 并提交 main；
> 审查修复及最新 123 项测试结果见 [代码审查报告](NOVEL-002-code-review.md)。下列分支和提交状态为首次交付时的快照。

- 日期：2026-09-10
- 状态：实现和自动验证完成，等待用户 Review；未开始 NOVEL-003。
- 分支：`wfg/novel-002-core-domain`
- 基础：NOVEL-001 已通过 Review 的工程，包括只读取 TOML 配置的修复。
- 编码前已完整阅读 `docs/specs/01-PRD.md` 至 `06-Technical-Architecture.md`、本 Ticket 和 NOVEL-001 实现报告；本次用户的阶段范围及业务规则为执行边界。
- 未执行 commit、push 或 merge。工作区原有的 NOVEL-001 配置修复仍保留，不能将整个未提交 diff 都归为 NOVEL-002。

## 1. Implementation Summary

实现八类核心对象的 Domain、Persistence、Service 和 HTTP API，覆盖创建、读取、版本历史、版本绑定审批、业务锁、乐观版本检查及审计。没有实现 Workflow Engine、Agent Runtime、LLM、Memory 或前端。

主要行为：

- Requirement / Decision 修改创建新的 PROPOSED；已批准版本拒绝普通 PATCH，只有新版本批准后才退为 SUPERSEDED。
- ChapterPlan / ChapterVersion 每次创建独立记录，Chapter 保存最新版本与批准版本两组独立指针。
- 所有审批要求 `expected_version`；过期版本返回 `VERSION_CONFLICT` / HTTP 409。
- 锁影响 Service 实际写入，并覆盖父级 Project、Chapter 及已声明的直接受影响对象。
- Service 持有事务，业务数据、版本指针和审计一起提交或回滚；Repository 只查询、写入与 flush。
- PostgreSQL 约束和 trigger 防止重复版本、无效版本指针、正文原地修改、已批准或已锁定版本内容修改、核心数据硬删除及审计修改。

本次没有新增或升级第三方依赖。沿用 Python 3.13、FastAPI 0.141.1、SQLAlchemy 2.0.52、Alembic 1.19.2、Pydantic 2.13.5 / Settings 2.15.0、psycopg 3.3.5、pytest 9.1.1、Ruff 和 PostgreSQL 16；精确依赖继续由 `backend/uv.lock` 管理。

## 2. Domain Objects Implemented

| 对象 | 实现内容 |
| --- | --- |
| Project | 名称、描述、标签及 metadata；ACTIVE / LOCKED / ARCHIVED；修改版本计数 |
| Requirement | 内容、类型、PROJECT / CHAPTER scope、优先级、persistent、有效时间、logical_id 和版本历史 |
| Decision | 问题、决策、理由、受影响对象引用；独立的审批和版本历史 |
| Lock | 目标类型、稳定目标 ID、锁定版本、原因、操作者、原状态与 authority、释放信息 |
| Chapter | 项目内 sequence、标题、current / approved 正文指针及 current / approved plan 指针 |
| ChapterPlan | objective、required_outcome、scene_plans、角色/情节推进、信息释放、结束状态、约束、锁定依赖、风险 |
| ChapterVersion | 正文、变更原因、父版本、版本号；正文不可原地修改 |
| AuditRecord | 目标记录及版本、操作、操作者、request ID、原因、操作前后状态、时间 |

Domain 使用标准库 frozen dataclass；不导入 FastAPI、Pydantic 或 SQLAlchemy。Repository 返回独立 Domain snapshot，不返回活跃 ORM 实例。嵌套 JSON 容器并非深度 frozen；持久化不可变性由写入用例和数据库共同保证。

Enum：`Status`、`Authority`、`ActorType`、`ObjectType`、`RequirementType`、`ScopeType`、`AuditAction`。定义规范中的公共状态/Authority 常量不意味着实现对应的后续业务。

Value Object：`VersionToken` 校验精确整数版本；`ObjectRef` 表示同项目对象引用；`CommandContext` 表示服务端操作身份与 request ID。

## 3. Database Tables Added

| 表 | 主要约束 |
| --- | --- |
| `projects` | UUID 主键、版本与状态约束 |
| `requirements` | `UNIQUE(logical_id, version)`；同逻辑对象至多一个有效批准；项目外键；有效时间范围 |
| `decisions` | `UNIQUE(logical_id, version)`；同逻辑对象至多一个有效批准；项目外键 |
| `locks` | 同一 `target_type / target_id` 至多一个 active lock 的 partial unique index |
| `chapters` | `UNIQUE(project_id, sequence)`；四个版本指针的 deferred composite FK |
| `chapter_plans` | `UNIQUE(logical_id, version)`、`UNIQUE(chapter_id, version)`；logical_id 等于 chapter_id；同项目 Chapter 复合外键 |
| `chapter_versions` | 同 Plan 的版本/所属关系约束；parent / supersedes 外键；正文不可变 trigger |
| `audit_records` | 项目外键、目标版本及操作记录；禁止 UPDATE / DELETE |

稳定属性使用关系列；Plan 的灵活结构、引用集合、tags、metadata 和审计快照使用 JSONB。八张表以外仅保留 Alembic 自身的版本表，没有后续 Ticket 业务表。

## 4. Migration

新增：`backend/alembic/versions/0002_core_domain_add_core_domain_persistence.py`。

- revision：`0002_core_domain`
- down_revision：`0001_bootstrap`
- 先创建八张表，再添加 Chapter 与其版本表之间的循环引用外键。
- 迁移 DDL 独立固化，不依赖运行时 ORM model 的未来变化。
- `novel_guard_core_record()` 及八个表 trigger 执行持久化保护。
- downgrade 先移除 trigger、函数及循环外键，再删除业务表，退回 NOVEL-001。
- `alembic/env.py` 注册 metadata，并支持测试传入已隔离的 connection；正常 CLI 仍使用原来的 TOML 配置读取与 Database 基础设施。

升降级会删除业务表数据；最终开发库验证前已确认八张表均为零条记录。日常迁移回归使用测试库独立 schema。

## 5. Repository Changes

新增 `CoreRepository`，集中八类 Domain / ORM 的显式映射以及项目、章节、历史版本、有效批准、锁和审计查询。

- `add` / `save` 只调用 flush，不调用 commit 或 rollback。
- 读取返回 Domain snapshot；JSON 字段复制后交给上层。
- 提供 Project `SELECT ... FOR UPDATE`，供 Service 在同一事务内序列化写入。
- Requirement / Decision 默认列表返回每个 logical_id 的最新记录；`effective=true` 返回有效批准；历史版本独立查询。
- HTTP 列表统一分页，`limit` 最大 200。
- 没有 hard delete 方法。

## 6. Service Changes

| Service | 职责 |
| --- | --- |
| ProjectService | 创建、读取、修改和软归档；检查 expected_version、项目锁及归档状态 |
| RequirementService | scope / 时间范围校验；提案、版本、审批与取代；scope Chapter 锁检查 |
| DecisionService | 问题/决策校验；版本与审批；affected_objects 同项目引用及直接影响范围锁检查 |
| LockService | 锁定、释放、原状态/authority 恢复；版本绑定与父级锁约束 |
| ChapterService | 创建和查询章节；项目内 sequence 唯一 |
| PlanningService | 新 Plan 版本、审批、两组 Plan 指针；锁定依赖校验 |
| ChapterVersionService | 新正文版本、审批、current / approved 正文指针 |
| CoreService | 用例事务、引用解析、公共锁检查、审计及 Chapter 指针更新 |

版本共用逻辑放在 `VersionService`、`ProposalService`、`ChapterArtifactService`，分别处理审批、Requirement / Decision 提案和 Chapter 下的版本创建；没有加入 Workflow 调度。

Plan `locked_dependencies` 与 Decision `affected_objects` 采用 `{object_type, object_id}`，校验对象存在且属于本项目。Decision 修改前仍检查原引用，不能通过先删引用绕过锁。Plan 在批准时重新检查所声明依赖是否仍有 active lock。

## 7. API Endpoints

以下路径统一加 `/api/v1/projects`。`{p}` 为 Project ID，`{c}` 为 Chapter ID，`{id}` 为 Requirement / Decision 的 logical_id，`{v}` 为内容版本号。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST / GET | 空路径 | 创建 / 列出 Project |
| GET / PATCH / DELETE | `/{p}` | 查询 / 修改 / ARCHIVED；不删除数据库行 |
| POST / GET | `/{p}/requirements` | 创建 / 列出最新 Requirement |
| GET / PATCH | `/{p}/requirements/{id}` | 最新版本 / 普通修改；已批准拒绝 PATCH |
| POST | `/{p}/requirements/{id}/approve` | 绑定 expected_version 批准 |
| POST | `/{p}/requirements/{id}/supersede` | 创建下一 PROPOSED；批准前保留旧有效批准 |
| GET | `/{p}/requirements/{id}/versions`、`.../versions/{v}` | 历史列表 / 指定版本 |
| POST / GET | `/{p}/decisions` | 创建 / 列出最新 Decision |
| GET / PATCH | `/{p}/decisions/{id}` | 最新版本 / 普通修改 |
| POST | `/{p}/decisions/{id}/approve`、`.../versions` | 批准 / 新 PROPOSED |
| GET | `/{p}/decisions/{id}/versions`、`.../versions/{v}` | 历史列表 / 指定版本 |
| POST / GET | `/{p}/chapters` | 创建 / 列出 Chapter |
| GET | `/{p}/chapters/{c}` | Chapter 及四个版本指针 |
| POST / GET | `/{p}/chapters/{c}/plans` | 创建下一版本 / 历史列表 |
| GET / POST | `.../plans/{v}` / `.../plans/approve` | 指定 Plan / 批准 Plan |
| POST / GET | `/{p}/chapters/{c}/versions` | 创建下一正文版本 / 历史列表 |
| GET / POST | `.../versions/{v}` / `.../versions/approve` | 指定正文 / 批准正文 |
| POST / GET | `/{p}/locks` | 锁定 / 锁记录列表 |
| POST | `/{p}/locks/{lock_id}/release` | 释放锁 |
| GET | `/{p}/audit` | 审计记录列表 |

Pydantic 输入采用 `extra=forbid`；客户端提供 status、authority_level、version、approved_at、approved_by、locked、actor 等服务端字段返回 422。审批版本为必填严格正整数；首个 Plan / 正文创建使用 0。

API 只做输入验证、依赖装配与 Domain snapshot → DTO 转换。沿用统一错误体和 request ID；增加 DomainError 的 403 / 404 / 409 / 422 映射。常见业务拒绝为 `VERSION_CONFLICT`、`LOCKED_OBJECT`、`INVALID_STATE`、`DUPLICATE_CHAPTER_SEQUENCE`。

## 8. Versioning Design

Requirement、Decision、ChapterPlan、ChapterVersion：每条历史记录有独立 `id`，逻辑对象由稳定 `logical_id` 标识；`version` 从 1 递增，`supersedes_id` 指向上一版本。Plan / 正文的 logical_id 固定为 chapter_id；正文还记录 parent_version_id。

Requirement / Decision：

```text
v1 PROPOSED → v1 APPROVED
创建新版本 → v1 APPROVED + v2 PROPOSED
批准 v2   → v1 SUPERSEDED + v2 APPROVED
```

Draft / Proposal 的 PATCH 也创建新记录。已批准内容禁止普通 PATCH，只能显式新建下一版本。历史内容保留；APPROVED → SUPERSEDED 等生命周期元数据可以更新。

Chapter 分开保存：

```text
正文：current_version = 2，approved_version = 1
计划：current_plan_version = 2，approved_plan_version = 1
```

新 Draft / Plan 只修改 current；审批成功才修改 approved。旧版本仍可读取。Chapter 自身的 `version` 是该容器记录的修改计数，不能与正文 / Plan 的内容版本号混用。

Service 获得 Project 行锁后读取最新版本并检查 expected_version。页面读到 v2，但现在已有 v3，则批准 v2 返回 409；不会默默批准 v3。重复审批已批准版本返回 INVALID_STATE。

ChapterVersion 的 content、变更原因、父版本等 payload 自创建即禁止原地修改；ORM UPDATE 和直接 SQL UPDATE 均由数据库拒绝。Service 没有正文更新方法，API 没有正文 PATCH 路由。

## 9. Lock Design

Lock 是独立持久记录；active lock 的目标为对象的稳定 ID，而不是某次请求中的布尔字段。锁定时目标进入 LOCKED / A1_USER_LOCKED，释放恢复锁定前状态和 authority，保留完整锁记录。

目标 ID 约定：Project / Chapter 使用自身 ID；Requirement / Decision 使用 logical_id；Plan / ChapterVersion 使用所属 chapter ID。锁记录同时绑定锁定时的 target_version。

- 同一 target 只允许一个 active lock，Service 与 partial unique index 双重约束。
- 受锁保护的内容创建、修改、创建下一版本、批准和父级相关写入均执行 Lock Check。
- Project 锁阻止后代写入；Chapter 锁阻止该 Chapter 的 Plan、正文及 chapter-scoped Requirement 写入。
- Decision 对直接 affected_objects 执行锁检查；未实现递归依赖图或影响传播。
- 释放子对象锁之前，必须先解除父 Project / Chapter 锁；释放本对象锁本身不会被本对象锁阻断。
- Project / Chapter 锁定、释放增加其修改计数；内容版本的锁定、释放不增加内容版本号。客户端释放前使用目标当前版本。

## 10. Transaction Design

API → Service → Repository → Database。Service 的 `session.begin()` 覆盖完整写入用例；事务中校验 Project、锁、版本、引用，写入对象、指针和审计，成功提交，任一步失败整体回滚。

同一 Project 的所有写用例首先锁定 Project 行，序列化版本分配、审批和锁状态变化。不同 Project 使用不同数据库行，不通过进程内全局锁。当前方案优先保证 Prototype 的业务一致性，未实现更细粒度并发调度。

唯一约束提供竞争兜底；IntegrityError 转换为统一 VERSION_CONFLICT，响应不泄露 SQL 或参数。Project 创建没有既存根记录，在独立 Service 事务中同时创建 Project 和审计。

测试通过注入审计失败验证新版本行、current 指针、approved 指针、旧版本 supersede 状态与审计同时回滚。Repository flush 后，另一连接不可见尚未提交的数据，证明事务没有被 Repository 偷偷提交。

事务与锁语义参考 [SQLAlchemy Session transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) 和 [PostgreSQL row locks](https://www.postgresql.org/docs/16/explicit-locking.html)。

## 11. Audit Design

覆盖 CREATE、UPDATE、ARCHIVE、VERSION_CREATE、APPROVE、SUPERSEDE、LOCK、UNLOCK。首次 Requirement / Decision / Plan / 正文记录也记为 VERSION_CREATE。

每条 AuditRecord 包含：project_id、目标类型、实际版本记录 ID、目标版本、服务端 actor、request_id、reason、前后状态及时间。锁操作附 lock_id；Chapter 指针变动额外记录 Chapter UPDATE，包含 current / approved 前后值。一次命令的多条审计通过 request_id 关联。

快照保存 ID、版本、状态、authority、锁和指针等状态；正文内容通过目标版本记录读取，不在每条审计中重复复制全文。审计不提供客户端写入或编辑接口，数据库禁止 UPDATE / DELETE。

本地 HTTP 调用固定绑定 USER / `local-user`，不从 body 或 actor headers 读取身份声明。Service 拒绝 AGENT / SYSTEM context 执行用户用例。审批和锁的 authority 均由 Service 产生，没有通用客户端状态赋值接口。

## 12. Tests Added

新增 64 个测试实例；原有 NOVEL-001 的 38 个测试继续通过。

| 文件 | 覆盖 |
| --- | --- |
| `backend/tests/test_domain.py` | frozen snapshot、版本 token、不可普通编辑状态、用户权限、Domain 不依赖框架 |
| `backend/tests/core/conftest.py` | 独立 schema、真实迁移、Database / TestClient fixture |
| `backend/tests/core/test_lifecycle_api.py` | Project CRUD / archive、Requirement、Decision、Plan、正文完整生命周期与审计 |
| `backend/tests/core/test_negative_api.py` | 伪造字段、非法 expected_version、跨项目目标、父级锁、非法输入 |
| `backend/tests/core/test_references.py` | Decision 引用范围与锁；Plan 依赖在批准时复查 |
| `backend/tests/core/test_persistence.py` | SQL / ORM 不可变、唯一约束、外键、审计 append-only、禁止硬删除、Repository 不 commit |
| `backend/tests/core/test_service_transactions.py` | 审计失败整体 rollback、非 USER 拒绝、服务层服务端字段校验 |
| `backend/tests/core/test_concurrency.py` | 两个同时创建下一正文版本的 HTTP 请求 |
| `backend/tests/core/test_migration.py` | upgrade / downgrade / upgrade、表集合、指针 FK、metadata 一致性 |

每个集成测试在已验证的独立 `_test` 数据库内新建随机 schema，迁移后执行测试，最后只清理自己的 schema。不使用开发库执行数据测试，也不以 SQLite 替代 PostgreSQL 行锁和 trigger 行为。

## 13. Test Result

实际执行：`cd backend && uv run --locked pytest`。

```text
collected 102 items
102 passed, 2 warnings in 10.61s
```

退出码 0，无失败、无跳过。运行环境为 macOS Python 3.13.12，测试数据库为 Docker PostgreSQL 16。

额外 Docker 验证：`docker compose up --build -d --wait backend` 成功，backend 和 postgres healthy。构建使用现有 Dockerfile，容器 Python 为 3.13.15。

| HTTP 验证 | 结果 |
| --- | --- |
| `/api/v1/health` | 200，status ok |
| `/api/v1/health/db` | 200，database ok |
| `/api/v1/projects` | 200，空列表 |
| `/openapi.json` | 200，26 个 path，含正文审批、锁释放及审计接口 |

上述响应均带 X-Request-ID。Docker 冒烟验证只读，不向开发库写入示例业务数据；写入生命周期由真实 PostgreSQL 集成测试验证。

## 14. Lint Result

| 命令 | 结果 |
| --- | --- |
| `uv run --locked ruff check` | PASS；All checks passed |
| `uv run --locked ruff format --check` | PASS；56 files already formatted |
| `git diff --check` | PASS；退出码 0，无输出 |

## 15. Migration Upgrade / Downgrade Result

2026-09-10 已在开发库显式、依次执行：

| 命令 | 结果 |
| --- | --- |
| `uv run --locked alembic upgrade head` | PASS，退出码 0 |
| `uv run --locked alembic downgrade -1` | PASS，0002_core_domain → 0001_bootstrap |
| `uv run --locked alembic upgrade head` | PASS，0001_bootstrap → 0002_core_domain |
| `uv run --locked alembic current` | 0002_core_domain (head) |
| `uv run --locked alembic check` | No new upgrade operations detected |
| `docker compose exec -T backend /app/.venv/bin/alembic current` | 0002_core_domain (head) |

独立迁移测试还断言：upgrade 后有八张业务表和 alembic_version；downgrade 后仅剩 alembic_version，版本为 0001；再次 upgrade 后表集合和四个 Chapter 指针外键恢复。

## 16. Concurrency Test Result

`test_two_requests_cannot_create_same_next_chapter_version`：先创建并批准 v1，两个线程经 Barrier 同时发送 `expected_version=1` 的下一正文创建请求。

- 一个请求 201，另一个 409 / VERSION_CONFLICT。
- 数据库版本列表恰好为 `[1, 2]`，没有重复版本号，也没有额外失败请求记录。
- Chapter.current_version 为 2，approved_version 仍为 1。
- PASS。此结果验证指定双请求竞争场景，不代表压力或吞吐量测试。

## 17. Negative Test Result

| 负向场景 | 结果 |
| --- | --- |
| Approved Requirement 普通修改 | PASS，INVALID_STATE / 409；已批准内容保持 |
| Locked Decision 修改 | PASS，LOCKED_OBJECT / 409；解除锁后可继续版本生命周期 |
| 同 Project 重复 Chapter sequence | PASS，DUPLICATE_CHAPTER_SEQUENCE / 409 |
| stale expected_version | PASS，VERSION_CONFLICT / 409 |
| 缺失、零、负数、bool、字符串、小数审批版本 | PASS，422 |
| Client fake APPROVED status | PASS，422 |
| Client fake authority_level、version、approved 字段或 actor | PASS，422；actor headers 不改变服务端身份 |
| Direct ChapterVersion content update | PASS，ORM 与 SQL 均被数据库拒绝，包括未批准 Draft |
| Approved Requirement / Locked Decision 直接 SQL 内容修改 | PASS，被 trigger 拒绝 |
| Repository unexpected commit | PASS，禁止 commit 的探针未触发，另一连接不可见未提交写入 |
| Transaction rollback | PASS，审计失败后版本、审批、指针、旧状态与审计全部回滚 |
| 跨 Project scope / Chapter / lock / reference | PASS，拒绝 |
| 父 Project / Chapter 锁下写入或释放子锁 | PASS，拒绝 |
| 删除 Decision 旧引用以规避引用对象锁 | PASS，拒绝 |
| Plan 依赖已解锁但继续批准旧 Plan | PASS，INVALID_STATE |
| 八类核心记录 hard delete | PASS，数据库拒绝 |
| 审计 UPDATE | PASS，数据库拒绝 |
| 重复 active lock / version | PASS，唯一约束拒绝 |
| Chapter 指向不存在的版本 | PASS，deferred FK 在提交时拒绝 |

## 18. Acceptance Criteria PASS / FAIL

| 用户指定验收场景 | 结果 |
| --- | --- |
| 1–3：创建 Project、创建 Requirement、批准 Requirement | PASS |
| 4–5：Approved Requirement 直接修改拒绝、创建新版本成功 | PASS |
| 6–10：创建/批准/锁定 Decision、锁定修改拒绝、解锁恢复生命周期 | PASS |
| 11–12：创建 Chapter 1、重复 sequence 拒绝 | PASS |
| 13–17：创建/批准 Plan v1、创建 v2、保留 v1、stale approval 拒绝 | PASS |
| 18–21：创建/批准正文 v1、创建 v2、current=v2 / approved=v1 | PASS |
| 22–23：批准 v2、保留历史且正文不可修改 | PASS |
| 24：Approval / Lock / Version 操作均有 AuditRecord | PASS，另覆盖 Chapter 指针变化审计 |
| Entity / Enum / VO、ORM、Migration、Repository、Service、Schema、Route | PASS |
| Approval Version Binding、Optimistic Check、Lock、Audit | PASS |
| Unit / Repository / Service / API / Migration / Negative / Concurrency tests | PASS |
| API → Service → Repository → DB；Domain 不依赖框架；DTO ≠ ORM | PASS |
| Repository 不 commit；Service 控制事务；不 hard delete | PASS |
| pytest、Ruff、格式、迁移升降级、git diff --check | PASS |
| 仅 NOVEL-002；未实现 NOVEL-003 及之后业务 | PASS |

自动验收全部通过；用户 Review 尚未进行，不以自动检查替代 Review。

## 19. Architecture Deviations

没有改变已确认分层，也没有重构 NOVEL-001 的配置、日志、Session 生命周期或 Docker 基础设施。局部接入点仅为路由注册、Domain 错误映射、ORM metadata 注册和测试用 Alembic connection 注入。

本次明确的实现选择：

1. Project 行锁作为 Prototype 写入串行化边界；不引入分布式锁、Redis 或 Workflow。
2. Project / Chapter 是可更新的容器，带乐观修改计数；Requirement / Decision / Plan / 正文采用历史版本记录。Lock 和 Audit 使用专用事件字段，未套用完整内容版本 DTO。
3. 审批、取代、锁定允许修改状态元数据；不可变性约束保护版本 identity 和 payload，避免把正常生命周期转换误判为内容修改。
4. 当前 HTTP 身份来自服务端固定的本地用户适配器；未引入账号系统。仅预留 Domain CommandContext，不提供 Agent 调用入口。

按 code-review-and-quality 流程完成独立代码复核。复核发现的 Chapter 指针审计遗漏、Decision 引用/锁范围校验缺失已修复，并加入回滚和引用回归测试；修复后复核未留下 Required 问题。

本次文件清单：

| 类别 | 新增 / 修改 |
| --- | --- |
| Domain | 新增 `backend/novel_os/domain/core.py`、`enums.py`；扩展 `domain/errors.py` |
| ORM | 新增 `backend/novel_os/models/__init__.py`、`models/core.py` |
| Migration | 新增 `backend/alembic/versions/0002_core_domain_add_core_domain_persistence.py`；扩展 `backend/alembic/env.py` |
| Repository | 新增 `backend/novel_os/repositories/core.py` |
| Service | 新增 `backend/novel_os/services/core_base.py`、`projects.py`、`versioning.py`、`locks.py` |
| API | 新增 `backend/novel_os/api/core_schemas.py`、`core_routes.py`；扩展 `api/errors.py` 和 `backend/novel_os/main.py` |
| Tests | 新增本报告第 12 节列出的九个文件 |
| Docs | 更新 `README.md`；新增本报告 |

原有未提交 NOVEL-001 TOML、Docker 配置及相关测试修复详见 `NOVEL-001-config-review-fixes.md`，本阶段予以保留。

## 20. Known Issues

- 没有已知阻塞 NOVEL-002 验收的问题。
- pytest 有两条已有依赖弃用警告：Starlette TestClient 的 httpx 兼容接口、AnyIO BlockingPortal alias。未为本阶段升级稳定依赖；测试均通过。
- 固定 `local-user` 是本地单用户 Prototype 身份边界；尚无登录、多租户权限、可信 Agent 身份接入。
- 同一 Project 的写入串行化，未做吞吐量评估或细粒度并发优化。
- Audit 保存状态和指针快照，并可关联不可变正文版本；不是完整业务字段的通用变更追踪系统。
- 没有通用请求幂等键持久化；已有版本命令依靠 expected_version 拒绝过期重放。
- Lock 支持 OBJECT 范围与直接父级/引用检查；没有字段级锁或递归影响传播。

## 21. Deferred Items

未实现并留待后续 Ticket：Workflow Engine / runtime、Agent Runtime、Prompt、LLM Provider、Context Engine、Memory Agent、Character / Event Memory、Review / Revision Agent、Vector DB、Redis、Kafka、Frontend，以及依赖失效传播和自动 Canon / Memory Commit。

没有从设计文档提前执行 NOVEL-003。NOVEL-002 完成后停止开发，等待用户 Review。
