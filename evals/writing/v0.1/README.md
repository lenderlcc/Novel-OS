# Writing acceptance cases v0.1

这是 NOVEL-008 的第一批验收案例、离线证据收集器与人工评阅模板，不是产品 Review Agent 或 QualityEngine。不会调度 NOVEL-009，没有自动模型评分、向量检索或外部 API 调用。

## 内容

- `cases/W001.json`～`W008.json`：输入条件、现有 pytest 测试映射、工程 oracle、待人工验证的 AI 行为。包含正向、负向和边界情况。
- `run.py`：去重后运行这些测试，复用 Backend 的独立 PostgreSQL 测试 schema。
- `lineage_audit.py`：在测试 schema 清理前，以只读查询审计全部 AGENT Draft 和 BLOCKED WritingResult；不调用 Provider。
- `templates/human-prose-evaluation.md`：真实 Writing Smoke 的人工验收表。
- `results/2026-09-15-mock/`：本次工程验收证据。日志仅去除了行尾空白以通过 diff 检查，未删减测试结果。所有正文输入为合成测试数据；UUID 对应已清理的临时测试 schema，不能拿去请求开发数据库。

## 离线复现

在仓库 `backend/` 中，沿用现有 `config.toml` 的独立 `test_database_url`，启动 PostgreSQL test service 后执行：

```bash
uv run python ../evals/writing/v0.1/run.py --output ../evals/writing/v0.1/results/new-local-run
```

输出目录必须不存在，避免覆盖旧证据。使用 Mock Provider；没有 `--live-model` 透传选项。每个 trial 使用已有测试构建、批准 Plan 和运行 Writing 的真实 Service/Repository/Database 路径。此处的批准只针对合成 fixture，不代表用户批准了生成正文。

`lineage.json` 包含每个测试的成功状态、生成 Draft 总数、逐 Draft/阻塞结果的七类 lineage、源版本、Context hash、Prompt 模块 pins、完整 ModelProfile/hash、Writing metadata 及 content hash。审计同时检查 Agent Draft → WritingResult 与 WritingResult → Draft，防止 INNER JOIN 漏掉孤立 Draft。还根据持久化 Task/Context 在本地重新编译 Prompt，核对 compiled hash、模块 pins、输出 schema hash 和模型配置；不会调用 `execute()` 或模型。

历史 Plan 可以已 SUPERSEDED。审计使用执行时 Context snapshot 的批准状态，不要求历史 Plan 永远保持当前批准状态。人工/Core API 创建的前置正文不是 Writing 生成记录，因此不计入 AGENT Draft 数量。

W003 和 W004 复用同一跨章节隔离测试。W004 的显式未来依赖边界另直接验证 ContextEngine，不能将其表述为又执行了一次完整 Provider 流程。

## 如何解释结果

| 层次 | 本批证据能证明什么 | 不能据此宣称什么 |
|---|---|---|
| Engineering Acceptance | 版本/审批隔离、事务、重试/并发、来源关系、确定性阻塞、API/DB/Docker | 生成文学质量达标 |
| AI Behavior Acceptance | Mock/显式结构化故障的契约与策略处理 | 真实模型遵循 Plan、不漏报偏离、不泄漏知识 |
| Human Prose Evaluation | 人工阅读真实 Draft 后的引用和判断 | 根据 Mock 的固定文本或模型自报字段自动给 PASS |

这是一批初始工程回归案例，不是统计基准。每个参数化案例本次执行一次；不计算 pass@k 或通过重复抽样筛选好结果。真实模型样本为 0，未配置 LLM judge。空正文、假 Authority、错绑 Plan、重大偏离等负例可在全量测试中查证。

案例 SHA-256 被写入每次结果。发布后新增/改变案例语义请使用下一版目录；旧结果保留，不能事后修改案例后把历史成绩当成新版本成绩。

## 真实 Provider：人工 opt-in

本次检测到 `config.toml` 没有 Provider credential，真实调用次数 **0**。人工先填验收模板的输入、审批版本和付费授权栏，再决定是否运行。密钥只写入现有本机忽略的 TOML 文件，不放进案例、日志或评阅表。

现有人工入口（不会被离线 runner 执行）：

```bash
cd backend
uv run pytest tests/core/writing/test_live.py --live-model
```

必须单独明确授权后才执行。该既有测试最多进行 **3 次 Writing 尝试**，使用 `openai-writing` 的固定配置（当前模型 `gpt-4o-mini-2024-07-18`，每次最多 8192 输出 token、90 秒超时），规划阶段使用 Mock。不要把它误称为只允许一个付费 API 请求。若只授权一个 API 请求，应先将本次人工执行限定为一次 `worker.run_once()`，不运行该测试的三次循环，不启动后台 Worker，不重试失败直到通过。

该测试结束会删除隔离 schema。用于文体验收时必须在清理前保存实际 Draft、批准 Plan、Context snapshot、PromptLineage、Task/Run、ModelProfile、WritingResult 和 token/延时记录到本机私有目录，并填写人工模板；仅 pytest PASS 不足以完成产品验收。未保存正文或 lineage 的执行，不补写成“人工已通过”。若 BLOCKED/解析失败，保留失败结果并如实记录，无正常 Draft 则文体维度填 NOT_EVALUATED。

下一次真实执行应在授权前确认模型可用性和费用上限；本次离线验收没有查询或验证 Provider 的在线可用性。
