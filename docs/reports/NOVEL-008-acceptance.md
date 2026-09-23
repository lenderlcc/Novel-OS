# NOVEL-008 Product Acceptance Validation

日期：2026-09-15（Asia/Shanghai）
代码基线：`bc53b48e6d1680f1f95f01f3beb1245d43b2646c`
分支：`wfg/novel-008-writing-agent`

## 验收结论

**NOVEL-008 = CONDITIONAL PASS**。

工程链路和离线 Writing 行为验证结果见下表。真实 Provider credential 未配置，因此没有调用真实 API，不能满足 Ticket 的 `real model draft generation works` 验收项。人工文体验收尚未进行。本结论不代表真实模型写作质量通过，也不授权开始 NOVEL-009。

| 验收层次 | 结论 | 范围 |
|---|---|---|
| Engineering Acceptance | PASS | 全量测试、专项 E2E、lineage、迁移、Docker 和质量检查通过 |
| AI Behavior Acceptance | CONDITIONAL PASS | Mock 契约/策略行为通过；真实 Provider Writing Smoke **NOT RUN** |
| Human Prose Evaluation | NOT EVALUATED | 没有真实模型 Draft 或人工评分；已建立 13 维评阅模板 |

本次只新增验收报告、案例、只读 lineage 审计器及证据。没有修改 Backend 产品代码、架构、数据库模型、Workflow 定义、Prompt 或 Provider 配置，没有实现 Review Agent、QualityEngine、NOVEL-009，也没有提交或推送这些验收文件。

## Engineering Acceptance

### 全量自动测试及质量检查

在 `backend/` 执行无 ticket 筛选的完整 `pytest`，覆盖现有 NOVEL-001～008 测试：

```bash
uv run pytest --junitxml=/tmp/novel008-acceptance-full.xml
uv run ruff check . ../evals/writing/v0.1
uv run ruff format --check . ../evals/writing/v0.1
git diff --check
```

| 检查 | 本次结果 |
|---|---|
| 全量 pytest | **781 passed，3 skipped，2 warnings，548.34s（9分08秒）** |
| Writing 验收 runner | **32 passed，2 warnings，40.20s** |
| 独立核查契约测试 | **21 passed**；不与全量数量相加 |
| ruff check | PASS |
| ruff format --check | PASS，228 files |
| git diff --check | PASS |

三个 live 测试默认 opt-in，未传 `--live-model`。真实调用跳过不是“真实模型已通过”。两个既有 warning 来自 Starlette TestClient 的 httpx 兼容层及 anyio BlockingPortal 弃用提示。

证据：[全量 JUnit](../../evals/writing/v0.1/results/2026-09-15-mock/full-suite.xml)、[全量运行日志](../../evals/writing/v0.1/results/2026-09-15-mock/full-suite.log)、[Writing JUnit](../../evals/writing/v0.1/results/2026-09-15-mock/writing-e2e.xml)、[工程摘要](../../evals/writing/v0.1/results/2026-09-15-mock/engineering.json)。

### Migration upgrade / downgrade / upgrade

使用现有 TOML `test_database_url`，创建唯一临时 schema。临时 TOML/INI 指向该 schema，通过独立 Alembic CLI 进程执行，未对开发库执行破坏性 downgrade：

| CLI 命令 | 实际 revision | 退出码 |
|---|---|---|
| `alembic upgrade head` | `0009_writing_agent` | 0 |
| `alembic downgrade -1` | `0008_requirement_planning` | 0 |
| `alembic upgrade head` | `0009_writing_agent` | 0 |
| `alembic check` | 无新增 schema 差异 | 0 |

临时 schema、临时含连接配置的文件已删除。全量套件另含 `test_0009_roundtrip_preserves_all_prior_data`，用已生成 Draft 的数据执行 0009 downgrade/upgrade，对所有前序表逐行比较，验证旧表数据保留。0009 自己新增的生成/绑定证据表在 downgrade 时被删除，这是 rollback 行为，不应宣称其证据可无损回滚。

证据：[migration.json](../../evals/writing/v0.1/results/2026-09-15-mock/migration.json)、[migration.log](../../evals/writing/v0.1/results/2026-09-15-mock/migration.log)。

### Docker / health regression

执行 `docker compose build backend` 和 `docker compose up -d --force-recreate --wait backend`。确认运行容器使用本次构建镜像，且容器内产品 Python 文件树的 SHA-256 与工作区一致；容器内 Alembic current 为 `0009_writing_agent (head)`。Backend、PostgreSQL、PostgreSQL-test 均 healthy。

| 请求 | HTTP | 实际结果 |
|---|---|---|
| `GET /api/v1/health` | 200 | `status=ok` |
| `GET /api/v1/health/db` | 200 | `status=ok, database=ok` |
| 不存在的 `/api/v1/acceptance-missing-route` | 404 | 统一 `NOT_FOUND` 错误结构 |

三次请求均回传 `X-Request-ID: novel008-acceptance`，404 JSON 中也包含相同 request ID。

证据：[镜像、代码 hash、health 响应](../../evals/writing/v0.1/results/2026-09-15-mock/docker-health.json)、[Compose 状态](../../evals/writing/v0.1/results/2026-09-15-mock/docker-ps.jsonl)、[构建日志](../../evals/writing/v0.1/results/2026-09-15-mock/docker-build.log)。

### Writing E2E 验收矩阵

通过 `evals/writing/v0.1/run.py` 在独立测试 schema 中执行。每项引用的具体测试和输入见 [cases](../../evals/writing/v0.1/cases)。参数化场景计入 trial 数，W003/W004 共享一次隔离场景，去重后共 **32 trials**。

| Case | 场景 | 已核验的实际结果 | 结论 |
|---|---|---|---|
| W001 | normal approved-plan writing | 批准 Plan → CP-005 → Writing → 1 Draft → C08；无后续任务 | PASS |
| W002 | approved vs current Plan | 调用前/调用中新增 v2 PROPOSED，仍使用已批准 v1 的 ID/version；v2 标记未进 Context | PASS，2 trials |
| W003 | previous approved chapter isolation | 上一章 approved v2/current v3；只取 approved v2，排除旧/新 Draft、跨项目和未批准 Requirement | PASS |
| W004 | future plan leakage protection | 排除非必要未来 Plan/正文；ContextEngine 中精确必要依赖也必须 approved + locked | PASS，3 trials（含 W003 共享场景） |
| W005 | major plan deviation | 重大偏离和伪装 LOCAL 的核心改变被 BLOCK；9 条阻塞记录均无 Draft；LOCAL/MODERATE 等对照允许 | PASS，13 trials |
| W006 | technical retry / duplicate delivery | 两种技术失败均同 Task、不同 Run、最终仅 1 Draft；并发重复交付 APPLIED + DUPLICATE | PASS，3 trials |
| W007 | stale result | approval/requirement/lock/chapter lock/cancel/pause/正文并发变更均拒收失效结果；另拒绝空正文和错绑 Plan | PASS，9 trials，0 Agent Draft |
| W008 | current_version vs approved_version | 既有 approved v1；Writing v2、用户再生成 v3，仅更新 current；v1/v2 保留，重复 event 幂等 | PASS |

W004 的额外显式依赖边界是直接 ContextEngine 检查，没有把它包装成额外的完整模型执行。W005 的 PASS 指阻塞逻辑符合预期，并非偏离正文被接纳。历史正文与 fixture 用户正文不计入本次生成 Draft 总数。

### 每个生成 Draft 的完整 lineage

本次专项 E2E 实际生成 **15 个 Agent Draft**，逐个验证全部七类 lineage；共审计 **24 条 WritingResult/Generation**，其中 **9 条 BLOCKED** 无正文版本。

| 关系 | 核验方式 |
|---|---|
| Draft ↔ WritingResult | 双向集合相等、每个 Draft 恰有一个 PASS Generation，正文 SHA-256 相同；BLOCKED 无 Draft |
| Plan | 精确 ID/version/project/chapter，与 WritingTaskBinding 和执行时 CP 中 approved-plan 相同；有审批时间 |
| ContextPackage | 同 Task/Run、项目/章节/工作流；CP-005 v3 READY；重新计算 package hash；导出全部源 ID/version/status/knowledge scope |
| PromptLineage | 同 Task/Run；从冻结 Task/Context 本地重新编译，核对 compiled hash、所有 module pins 和 output schema hash |
| AgentTask / AgentRun | WRITE_CHAPTER / A04_WRITING，result_ref 精确对应；run SUCCEEDED，成功 Draft 为 APPLIED，重试 attempt 可追溯 |
| ModelProfile | 持久化完整 profile 与 hash；与 Prompt、Run、Generation 的 provider/model 一致；此次均 mock-writing |
| WritingResult | 元数据通过同一 WritingMetadata schema；Chapter/Plan/version 精确绑定，content 独立存于不可变 ChapterVersion |

逐个可查的证据：[lineage.json](../../evals/writing/v0.1/results/2026-09-15-mock/lineage.json)。所有成功记录都保存 `prompt_recompiled_and_verified=true`。临时数据库已清理，证据中的 UUID 是测试执行标识。

[独立验证记录](../../evals/writing/v0.1/results/2026-09-15-mock/independent-verification.json)：验证者以 fresh context 复核：32 trials/JUnit 一致；全部 case hash、24 个 ModelProfile hash、WritingMetadata、输出 schema hash、216 个 Prompt module pins 均匹配。没有发现工程验收阻塞缺陷。工程成功不是根据模型自报评分判断的。

## AI Behavior Acceptance

**Mock 可观测契约/策略行为：PASS。真实模型 Writing 行为：NOT RUN。**

已验证 approved/current 隔离、未来信息精确选择、GLOBAL_ONLY 与 Character Knowledge 标注边界、显式重大偏离阻塞、提案不自动 Canon 化、技术重试/失效结果不污染正文。这些来自实际输入/持久化状态断言和结构化故障注入。

当前确定性检查依据 `plan_deviations`、`scene_execution`、`knowledge_risk_flags` 等显式证据。若模型在正文里改变 required outcome、泄露人物未知信息，却没有在 metadata 上报，本阶段没有语义审阅器能证明或发现全部此类问题。固定 Mock 正文也不能证明任意 Plan 的语义完成度。本次没有新增 Review Agent/QualityEngine 去填补这个后续阶段能力。

真实 Provider 探测仅检查本机配置是否含 credential，结果为 **未配置**，默认 profile 为 `mock-default`。没有读取或展示密钥值，没有执行 `--live-model`，真实 API 调用次数 **0**。

仓库已有 opt-in Writing 测试，最多三次 Writing 尝试；其通过只代表那次真实模型契约/落库成功，不代表人工文体通过。如何授权、限制调用、保存正文与 lineage 见 [验收 README](../../evals/writing/v0.1/README.md)。

## Human Prose Evaluation

**NOT EVALUATED**。真实输出样本数为 0；没有虚构文体分数，没有把 Mock 固定正文当真实模型评测，没有调用 LLM judge。

已生成 [人工 Writing Smoke 验收模板](../../evals/writing/v0.1/templates/human-prose-evaluation.md)，逐项记录 `PASS / CONCERN / FAIL / NOT_EVALUATED`、严重程度、段落证据与影响，覆盖：

1. Plan adherence
2. Required outcome
3. Mechanical plan expansion
4. Major deviation
5. Knowledge leak
6. Over explanation
7. Emotion labeling
8. Uniform rhythm
9. Template transition
10. Dialogue functionalization
11. Character voice collapse
12. Excessive closure
13. Over-signposting

模板还要求记录人工付费 opt-in、实际调用/重试/token、批准的具体 Plan、生成前后 current/approved 指针和完整 lineage。重大方向偏离、必需结果缺失或确认知识泄漏不能被其他文体优点抵消。

## Known Issues 与进入 NOVEL-009 前的条件

**当前验收没有确认需要修复的产品代码阻塞项。** CONDITIONAL PASS 的原因是下列验收证据尚缺失，不将其伪装成代码缺陷：

1. **必须补齐真实 Writing Smoke**：在本机 TOML 配置 credential 后，由用户明确 opt-in 并约定调用/费用上限；保留一次执行的实际正文、批准 Plan、Context、Prompt、Task/Run、ModelProfile、WritingResult。未授权不能自动调用。
2. **必须补齐人工文体评阅**：按 13 项模板逐项填写，确认该 Draft 对批准 Plan/required outcome 的执行及人物知识边界。若出现阻塞问题，先记录根因、修复和复测，再请求下一阶段 Review。
3. **须完成用户 Review**：确认上述真实/人工验收结果或明确接受其未完成限制。此报告不会自行推进 NOVEL-009。

非阻塞事项：两条既有测试依赖弃用 warning；现有跨关联负向测试以不存在 UUID 为主，后续可强化“存在但属于另一 Task/Run”的关联拒绝案例。确定性检查不覆盖未上报语义偏离是既定能力边界，不应据此提前实现下一阶段 Agent。

本次变更位于 `evals/writing/v0.1/` 和本报告；第一批 8 个案例已建立，完整工程证据可复现。**停在 NOVEL-008，等待 Review。**
