# NOVEL-003 Code Review

日期：2026-09-11

范围：`wfg/novel-003-workflow-engine` 相对 `fa62afa` 的全部未提交实现，包括新增文件、
NOVEL-002 事务组合改动、API、定义、持久化和测试。

当前状态：**四项问题已修复，等待用户 Review**。下文保留首次审查的缺陷证据；
当时结论为 Request changes（1 个 P1、3 个 P2）。最终修复与复验记录见文末。

## Findings（修复前）

### R1 — P1：Approved Plan 变更后，旧正文仍可审批并完成 Workflow

位置：`backend/novel_os/workflow/definitions/chapter-production.v1.yaml:18`、`:25`、`:29`。
相关代码：`backend/novel_os/workflow/guards.py:35`。

`docs/specs/04-Workflow-State-Machine.md` 第 11 节明确要求
`Approved Plan Change → Existing Draft STALE`。当前仅在进入 Writing 及创建 Writing/Revision
产物时检查 `plan_approved`。正文产生后的检查、评审、章节验收及模拟 Memory 步骤，只检查正文
自身的 current/approved version，不再检查 Workflow 绑定 Plan 是否仍有效。

通过公开 API 复现：

1. 正常推进到 C08，已有基于 Approved Plan v1 生成的 Draft v1。
2. 使用 Core API 创建 Plan v2，再批准 v2。
3. Fake deterministic check 仍成功进入 C09。
4. 继续评审、Human Gate APPROVE 和模拟完成，最终进入 C16。
5. 最终 `Workflow.plan_version = 1`、`Chapter.approved_plan_version = 2`，旧 Draft v1 已批准。

影响：上游已批准计划发生变化后，下游旧正文可被静默当成有效结果完成，违反冻结的 stale 规则。

建议：在正文后续推进及章节验收/完成的 Guard 中核验绑定的 approved Plan；失效时阻塞并要求
重新规划或显式重新验证，保存原版本和审计。补充 Plan 在 C08、C12、C14 变更的回归测试。

复现：`/tmp/novel003-review/test_combinations.py::test_approved_plan_change_invalidates_existing_draft`。
实际结果：预期 C90_BLOCKED，实际 C09_INTERNAL_REVIEW，随后可到 C16_COMPLETED。

### R2 — P2：第二次阻塞覆盖恢复类型，导致返工计数和技术预算错误

位置：`backend/novel_os/workflow/runtime.py:479-499`。
使用该标记的位置：`:376-378`、`:522-526`。

`blocked_guard` 同时承担“待重查 Guard”和“恢复是否进入新阶段”两个职责。
第一次因 Plan 过期设置 `blocked_guard=None` 表示应进入新 Planning；随后 Resume 若再遇到
Project 锁，`_block()` 将该字段覆盖为 `writable`，原本的新阶段标记丢失。

复现：

1. 到 C07，模拟两次技术失败，`state_retry_count = 2`。
2. 创建新 Plan v2；提交旧 Writing 结果，进入 BLOCKED，恢复目标为 C04。
3. 锁住 Project，调用 Resume，仍为 BLOCKED。
4. 解锁 Project，再调用 Resume。
5. 已进入 C04，但 `planning_iteration_count = 1`、`state_retry_count = 2`；预期分别为 2 和 0。

影响：本次重规划未被计数，且新 Planning 错误继承已耗尽的 Writing 重试预算，下次技术失败
就会进入 FAILED。

建议：独立保存恢复目标的进入语义/原始阶段，第二次阻塞只更新缺失条件；成功恢复时再清除
恢复上下文。不要用 Guard 是否为空来推导阶段切换。

复现：`/tmp/novel003-review/test_combinations.py::test_replan_recovery_survives_second_block`。
实际断言：`(planning_iteration_count, state_retry_count) == (1, 2)`，预期 `(2, 0)`。

### R3 — P2：既有实例仍依赖当前磁盘 YAML 可用

位置：`backend/novel_os/workflow/runtime.py:67`、
`backend/novel_os/workflow/definitions.py:150-156`。

每次创建 WorkflowRuntime 都立即构造默认 Registry 并加载当前 package YAML，包括仅用于
GET / history / gates / cancel / dispatch 的 Runtime。虽然实例已持久化完整定义，磁盘 YAML
失效、缺失或部署升级移除旧文件时，这些操作会在读取绑定定义前失败。

复现先建立有效实例，然后用 monkeypatch 模拟 Loader.load() 返回 INVALID_DEFINITION。
此时连 `WorkflowRuntime(session).get(existing_id)` 都无法执行；异常发生在构造函数，
无法进入 `_dispatch()` 对数据库定义的校验及 FAILED 处理。

影响：运行中的实例与当前定义资源仍有无关的可用性耦合，不能依靠已保存定义继续读取、控制
或推进；定义升级/打包错误影响既有实例。

建议：只在 create() 需要选择新定义时加载 Registry；既有实例的读取和执行使用其数据库绑定
定义。对读接口、取消和既有实例推进分别增加“当前 YAML 不可用”的测试。

复现：`/tmp/novel003-review/test_combinations.py::test_running_instance_does_not_require_current_yaml`。
实际：Runtime 构造时抛出 DomainError / INVALID_DEFINITION。

### R4 — P2：ORM 的枚举 CHECK 约束重名，与 Migration 不一致

位置：`backend/novel_os/models/workflow.py:99-100`、`:149-153`。

WorkflowInstanceModel.status / resume_status 都使用 `name="status_enum"`，
WorkflowTransitionModel.from_status / to_status 也都使用此名称。命名约定会在同一表内生成
重名 CHECK constraint。0003 migration 已为这些字段使用不同名称，ORM metadata 却未同步。

在独立 PostgreSQL 测试 schema 中调用 `Base.metadata.create_all()`，直接报：

```text
psycopg.errors.DuplicateObject:
check constraint "ck_workflow_instances_status_enum" already exists
```

影响边界：当前应用和测试通过 Alembic 建库，不调用 create_all，因此现有部署路径未因此
失败。问题是 ORM metadata 本身不能生成合法 schema，并已与冻结 migration 的约束命名漂移。
本轮 `alembic check` 的既有通过记录也不能证明 CHECK 命名一致。

建议：让 resume_status、from_status、to_status 使用与 0003 migration 一致且表内唯一的
枚举约束名；补充 metadata 约束命名检查。无需改已正确的 migration 或改用 create_all 部署。

复现：`/tmp/novel003-review/test_combinations.py::test_workflow_metadata_creates_valid_postgres_schema`。
临时 schema 在同一事务结束时回滚，无开发库变化。

## Verification（修复前）

| 验证 | 结果 |
| --- | --- |
| 原有完整 pytest | 203 passed，2 个既有弃用警告，40.56 秒 |
| ruff check | PASS |
| ruff format --check | PASS，76 files already formatted |
| git diff --check | PASS |
| 组合恢复补充用例 | FAIL，确认 R2 |
| 当前 YAML 不可用补充用例 | FAIL，确认 R3 |
| Approved Plan 变更补充用例 | FAIL，确认 R1 |
| ORM metadata 建库补充用例 | FAIL，确认 R4 |

补充用例和 fixture 适配位于 `/tmp/novel003-review/`，未加入仓库测试集，避免把审查中故意
失败的复现混入既有回归结果。运行方式（从 backend 目录）：

```bash
uv run --locked pytest -c pyproject.toml /tmp/novel003-review/test_combinations.py \
  -q --tb=short --show-capture=no
```

所有补充数据库操作使用已验证的 `_test` 数据库及隔离 schema。未执行开发库 downgrade，
未修改业务代码、分支、提交或运行中的服务。两位独立审查者分别检查了控制路径和持久化；
最终结论只保留与规格及实际复现相符的问题。

## Coverage Gaps and Recommendation（修复前）

现有测试充分覆盖 Happy Path、单次 Block/Resume、审批权限、事件幂等、同版本并发和回滚。
缺口集中于上游审批变更、多个恢复条件叠加、定义资源失效隔离，以及 ORM/migration 约束一致性。

先修复上述四项并把复现转为正式回归，再重跑完整 pytest、Ruff、migration 往返验证和最终 Review。
本报告的 Request changes 取代前一份实现报告中“未发现阻塞问题”的审查结论；不改变既有测试
当时通过的事实。

## Fixes and Reverification — 2026-09-11

### R1 — 已修复

`GuardRegistry.draft()` 先校验 Workflow 绑定 Plan 仍是 Chapter 当前且已批准的版本。
正文检查、评审、验收及模拟完成因此不能继续消费旧计划下的正文。Plan 失效进入 BLOCKED，
恢复目标为 C04；验收时将旧 Gate 标为 STALE 并返回 VERSION_CONFLICT / 409，保留旧版本及
原有审批，不新增审批或正文副作用。

独立复验还发现旧定义的 C08 / C09 质量失败边没有 draft Guard，会先进入 Revision 才阻塞。
Runtime 现对所有目标为 C10 的转换补查 draft_current，在计数或转换前拦截 stale 产物。
保持原 YAML 和持久化 v1 定义正文不变，既有实例同样受保护。

正式测试：`test_workflow_review_regressions.py::test_approved_plan_change_blocks_old_draft_and_requires_replanning`。
覆盖 C08、C09、C11、C12、C14、C15 和两条 review_failure 边；核验直接阻塞、revision_count
不增加、旧内容/批准时间不变、阻塞重放无重复审计，以及重规划产生新版本后完成。

### R2 — 已修复

Domain / ORM 独立保存 resume_new_stage，blocked_guard 仅表示待重查条件。
重复锁阻塞保留阶段恢复意图；成功进入新阶段才增加 planning_iteration_count 并重置
state_retry_count，同阶段恢复保留技术预算，累计 retry_count 不变。

新增 `0004_workflow_recovery`，不改写已执行的 0003 migration。升级利用旧标记和历史
Transition / Audit 回填，包含被二次阻塞覆盖的标记；不改变事件、审计或 state_version。
降级转回 0003 表示并恢复旧 trigger，保留 Workflow 业务数据。0004 是修复 revision，
没有实现 NOVEL-004 Ticket。

正式测试：`test_recovery_intent_survives_repeated_lock_blocks`，以及
`test_review_migration.py::test_0004_roundtrip_preserves_pending_recovery_and_history`。
覆盖同阶段、新阶段和旧标记已覆盖三类恢复，校验预算、计数、重放、历史及 trigger。

### R3 — 已修复

默认 Registry 仅在创建新实例时加载。既有 get/history/gates/dispatch/decide/cancel 使用
数据库保存的绑定定义；创建命令的幂等重放也不依赖当前 YAML。
新建实例遇到缺失或无效 YAML 返回受控 INVALID_DEFINITION。

正式测试：`test_persisted_workflow_runs_without_current_yaml`。
分别模拟缺失与损坏的 package YAML，验证读、Gate、创建重放、完整完成和取消均可用，
新建实例被正确拒绝。

### R4 — 已修复

ORM resume_status / from_status / to_status 使用与 0003 migration 一致的独立 CHECK 名称。
正式测试逐表比较 metadata 与迁移库的 CHECK 名称，并在临时 PostgreSQL schema 验证
`Base.metadata.create_all()` 成功。应用部署继续使用 Alembic。

正式测试：`test_workflow_metadata_constraint_names_match_migrated_schema`、
`test_metadata_creates_valid_postgres_schema`。

### Final Verification

新增正式回归 19 项。两位独立复核者分别检查 Runtime/Guard 与 Persistence/Migration；
后续补出的质量失败边已修复并复验通过，未发现新的 Required 问题。

| 最终验证 | 结果 |
| --- | --- |
| 完整 pytest | PASS，222 passed，2 个既有弃用警告，45.74 秒 |
| 新增正式回归 | PASS，19 项 |
| ruff check | PASS |
| ruff format --check | PASS，79 files already formatted |
| git diff --check | PASS |
| alembic upgrade head / downgrade -1 / upgrade head | PASS，最终 0004_workflow_recovery |
| alembic check | PASS，No new upgrade operations detected |
| Docker build / restart | PASS，backend healthy |
| health / health/db | HTTP 200 / 200 |
| 镜像定义资源 | PASS，chapter-production v1 可加载 |

数据库集成测试在 `_test` 数据库隔离 schema 执行。开发库另外完成 0003 → 0004 升级及
upgrade head / downgrade -1 / upgrade head / check；最终 head 为 0004_workflow_recovery。
本轮重建本地 Docker backend；配置仍来自 TOML，未新增依赖或后续 Ticket 功能。

最终命令结果与运行耗时同时记录在 `NOVEL-003-implementation.md` 第 20–21 节。
实现与修复位于 `wfg/novel-003-workflow-engine`，等待用户 Review；未合并至 main。
