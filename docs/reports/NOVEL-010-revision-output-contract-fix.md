# NOVEL-010 — Revision Output Contract Alignment

日期：2026-09-28。分支：`wfg/novel-010b-revision-workspace`。

**工程修复完成并已加载到本机服务；真实同章 Draft v2 验收尚未完成。** 真实输入存在章节/Review 版本歧义，已请求用户确认；本轮真实 Provider 调用为 0。不能把 Mock 链路通过写成真实 Case 05 通过。

## 1. Confirmed Root Cause

第 8 章「hh」的 `PLAN_CHAPTER_REVISION` task `251db722-5eef-4126-a38e-07bd65e08c1b` 返回一条 `PROPOSE_DRAFT` 到本章的 `proposed_changes`。

- 通用 AgentResult Schema 允许非空数组，通用 AuthorityValidator 也允许该 task capability / target。
- RevisionResultService 要求 proposal 数组为空，抛出 `AUTHORITY_DENIED`。
- 旧 A06 Prompt 没有解释 `PROPOSE_DRAFT` 只授权返回 typed result，不授权在 envelope 中发出操作提案。
- Revision Plan 未持久化，未执行正文修改，没有新 Draft。后来完成的 Review v2 仍对应 Draft v1。

已用保留的原始模型输出离线复现。历史 `chapter-revision-plan.v2` schema hash 与运行时 capture 完全一致。新 Schema 拒绝非空 proposal；仅在离线探针中清空 envelope 并补充新版本 unresolved 字段后可通过结构校验。此探针未写入业务库，不是模型复跑或真实验收结果。

## 2. Contract Alignment

新增专用 `RevisionEnvelope`：`proposed_changes` / `memory_proposals` 都使用 Pydantic `max_length=0`，缺失时为 `[]`。生成的 JSON Schema 和 Provider dialect 都保留 `maxItems: 0`。

兼容字段保留是因为运行时通用 envelope 及历史 lineage 已使用这些名称；它们在 Revision 中不能承载任何操作。

| 阶段 | 新 Schema | 新 task-template Prompt |
| --- | --- | --- |
| A06 Revision Planning | chapter-revision-plan.v3 | plan-chapter-revision v3 |
| A06 Revision Execution | chapter-revision-result.v2 | revise-chapter v3 |
| Revision Fidelity Validation | revision-fidelity-result.v2 | validate-revision-fidelity v2 |

新 Plan 增加 `unresolved_issue_ids`，必须与 `blocked_reasons.issue_id` 一一对应，禁止重复或遗漏。既有 actionable target / blocked 分区、source identity、preservation、zones、evidence 校验继续有效。

A06 Prompt 明确：只能编辑当前原稿、修复局部质量问题、在 Approved Creative Freedom 内局部发挥。不得提议/执行新的重大方向、Story Plan、批准 Plan、Locked Decision、Canon 或重大故事事实变更；无法安全解决的问题保留 unresolved 并说明 blocked reason。`PROPOSE_DRAFT` 授权 typed prose result，不能填充 proposals。

Fidelity 的改变仅为空 envelope 约定，不改语义检查规则。Writer、正式 A05 Quality Review、质量分类及 Prompt 均未改变。

## 3. History and Error Taxonomy

所有历史 Prompt 文件保持不变。历史 Pydantic model / schema version 继续用于解析与 lineage 回放；已有 Plan body 的 API 读取仍兼容。

历史 pending / retry Revision 不能继续用旧协议消耗模型调用：`AgentRuntime.prepare` 与 `execute(task, prepared)` 都在网络前拒绝四组旧 Revision schema，返回已有 `PROMPT_CONFIGURATION_ERROR`。历史记录不改写；后续工作需通过现有流程创建使用当前协议的新 task。

当前协议中的非空 proposal 在 OutputContract.parse 阶段产生 Pydantic ValidationError，归入已有 `SCHEMA_PARSE_ERROR`，不会进入 Authority/Service 持久化。Service 保留历史结果防御，非空数组用 ValueError 表示 Contract violation，不再伪装为用户权限错误。

真正的 task identity、capability、source/target Authority 校验保留。没有忽略非法字段、清洗后偷偷接受、扩展 capability 或绕过 Lock / approved / canon / source freshness。

## 4. UI and Debug

- Revision Planning 因输出错误停止时显示「修改任务未能开始。」及「尚未修改正文」。
- 正常 Planning 期间显示「AI 正在分析修改范围…」，不会提前显示正文修改。
- Debug 的 Agent Task 表显示 `Revision Planning`、`Output Validation Failed` 和原始错误码。
- 当前错误按 workflow identity / resume_state / state_version 定位，历史失败及其他 Workflow 的失败不会误显示为当前失败。

## 5. Regression Results

| 检查 | 结果 |
| --- | --- |
| 最终 Backend 非 core 回归 | 588 passed / 1 skipped；skip 为未启用的付费 Provider smoke |
| 初步 Revision contract / fidelity / full slice | 54 passed |
| Revision DB / safety / fidelity / budget 专项 | 首轮 90 passed / 1 failed；失败为新增测试把旧 Review 的动态 freshness 误要求为 CURRENT |
| 上述断言修正 + Contract / DB 复测 | 22 passed；旧 Review 正确变为 STALE，body / identity 保持不变 |
| Frontend 全部测试（含新 UI/Debug 断言） | 121 passed / 8 files |
| Playwright Revision E2E | 2 passed：成功 successor + 精确重审绑定；Fidelity FAIL 保留 v1 |
| Ruff check / format check | PASS |
| Frontend lint / typecheck / build | PASS |
| git diff --check | PASS |
| Migration | 无新增 DDL；专项中的 isolated upgrade / downgrade / upgrade / Alembic check 通过 |
| Docker Worker build / runtime contract versions | PASS |
| Backend health / DB / frontend proxy / historical revisions API | 全部 HTTP 200 |

两条旧 TestClient 依赖 deprecation warning 仍存在。未声称重新跑过完整 NOVEL-001～010 数据库全量测试。

覆盖用户要求：

- A：三个 Revision 阶段均接受 absent / [] proposals，生成 Schema 明确 maxItems=0。
- B：重大故事变更需求保留 unresolved / blocked，无操作提案；两个列表不一致会拒绝。
- C：三个阶段的非法非空 proposal 都是 SCHEMA_PARSE_ERROR；一次尝试后停止，无 artifact、新版本或自动重试。
- D：合法空 envelope 不会导致 AUTHORITY_DENIED。
- E：Mock 的 Plan → A06 candidate → Fidelity PASS → Draft v2 → 正式 Review v2 完整通过；Review 精确绑定新 chapter_version_id，原稿不可变，approved_version 不变，结束后停止。
- 四组历史协议分别验证普通 prepare 与预编译 execute 都为零 Provider 调用。

测试均使用隔离测试库或 Mock，未把生产案例硬编码为特判。测试文件按既有要求保留本地，本轮没有提交/推送。

## 6. Real Case Identity / Source Conflict

当前 DB / API 核对：

| 项目 | 报告中的 Case 05 | 本次实际 Contract 报错章节 |
| --- | --- | --- |
| Chapter | 第 7 章「继续3」 | 第 8 章「hh」 |
| Chapter ID | 8a345f75-f673-4efb-8a93-342da83d2180 | 0db2fea7-db58-4cc6-9947-4fcee48bdb21 |
| Workflow | 15aaf3b7-6c6f-4832-b490-fcb03f3dfffa | c96f61c2-da12-4b05-9051-073a63d7f079 |
| Source Draft v1 | ac433c00-5906-470a-9fcf-e300621c533b | 13a93dad-089e-429e-b2dd-59bffbcb5a7e |
| 最新 Review（均仍对应原稿 v1） | f774f445-44d8-49b3-b3a3-15f41ef1e5d3 / v2 | 6fce870e-ddf7-44ea-9420-34ee58a3c3d2 / v2 |
| 状态 | BLOCKED：已有合法业务阻塞 Plan | WAITING_HUMAN：可按最新 Review 显式发起修改 |

第 7 章此前的 Plan 已成功通过结构校验，因缺少安全具体化重大故事事实的依据而业务 BLOCKED，与第 8 章的 envelope Contract failure 不同。

两章均已有 Review v2。现有 source freshness 边界要求使用最新 Review，不能为了「Draft v1 + Review v1」验收而删除 Review v2、伪造 binding、清空旧 artifact 或绕过 stale check。已就目标章节及使用最新 Review 发出澄清；尚未得到回复。

本轮未创建 Chapter、未重新 Writing、未修改原稿、未重新审阅、未发起真实 Revision。真实 Draft v2 / 新 Review ID 暂不存在，本项验收 **PENDING**。

## 7. Deployment / Acceptance

本机原有运行方式保持：native Backend 8000 + Vite 5173 + Docker Worker / PostgreSQL。启动前确认无活动 task，更新 Backend / Worker；保留本地配置文件、chapter-quality scope、单次 attempt 上限及原始 capture。数据库未重建。

**Engineering Acceptance：PASS。Real Revision Acceptance：PENDING（输入身份/Review 版本待确认）。Human Prose Evaluation：NOT RUN。**

独立代码审查发现的历史任务网络入口缺口已修复并复核关闭。未新增依赖、迁移、业务 Authority 或 Workflow 状态；未修改 Writer/Quality Review；未开始 NOVEL-011。只有真实同章新 Draft 通过 Fidelity 并获得精确绑定的新 Review 后，才进入正文质量验收。
