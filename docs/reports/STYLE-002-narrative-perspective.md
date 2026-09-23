# STYLE-002 — Narrative Perspective Control

日期：2026-09-23。范围：Project Writing Profile 的叙事人称补丁。

## 1. Background

用户在 Case 03 人工测试中期望第三人称，但实际正文采用第一人称。本轮将叙事人称纳入已有版本化偏好链：Profile → exact approved Context → Writer Prompt。没有实现 NOVEL-009 或自动文学质量判定。

## 2. Case 03 Finding

实际 Project 为 `23c028ee-cd94-4965-af85-731e560c9633`（测试），Chapter 为 `2ad1d3b7-afca-445b-9841-76e0e0e0bc6c`（第 3 章“转折”）。

旧 Draft v1 `87d5b9ac-d04e-4a24-b88e-4a39afb9973a` 开头：“转运站的钟指向四点三十八分时，我已经站到了交接窗口前。”这属于叙述声音，不是人物对白。当时批准的 Profile v1 没有正式叙事人称字段，因此本报告不将该历史输出描述为违反已绑定的 THIRD_PERSON 配置。

该实际 Workflow 的需求与 `evals/manual/case-03.json` 当前 fixture 不同。保留两者原样，不声称已完成同一 fixture 的严格生成回归。样本、原输出 hash 与其他反馈见 [Case 03 人工反馈](../../evals/writing/v0.1/case-03/evaluation/human-review.md)。

## 3. Scope

- 新增 nullable `FIRST_PERSON` / `THIRD_PERSON` 偏好及中文 UI。
- 复用 STYLE-001 的 Profile 版本、审批、A5 authority、Context、freshness 和 lineage。
- 新增 Writer task template v4，仅追加人称段落，保留 v3。
- Manual Case Loader 增加独立测试项目提示。
- 新增自动回归与人工 smoke 模板；保存当前项目第三人称 Profile 草稿。

未改动 Canon、Requirement、Decision、Lock、ChapterPlan 或模型输出合同；没有新增 POV 类型、ContextProfile、数据库表或依赖。未增加 `narrative_perspective_used`，避免仅靠模型声明判断真实性。其他文风维度只记录。

本工作区在补丁开始前已有大量 STYLE-001、运行时及 UI 未提交变更。本报告仅归属本次增量，不将它们算作 STYLE-002 实现，也未执行提交或推送。

## 4. Domain Change

`backend/novel_os/domain/writing_profile.py` 增加 `NarrativePerspective(StrEnum)` 和 `WritingPreferences.narrative_perspective`，默认 `None`。构造与 `from_payload()` 两条入口校验枚举，非法人称被拒绝。

领域模型仍为 frozen dataclass，不依赖 FastAPI 或 SQLAlchemy。Profile 的版本号、状态与 hash 继续由既有服务控制。

## 5. Schema

`WritingPreferencesInput` 和继承它的 API view 支持 nullable enum；API 对未知值返回 422。前端 `api.generated.ts` 从本地 FastAPI OpenAPI 重新生成。

已有 `project_writing_profiles.preferences` 是 JSONB，可以安全容纳该字段，无需 migration。没有修改既有 migration，也没有回填历史记录。数据库默认值和配置环境变量均未新增。

## 6. Versioning

现有 API 保存新 DRAFT，`expected_version` 继续防止并发覆盖；批准仍是单独操作。v2 未批准时 Agent 选择 v1；批准 v2 后新 Task 选择 v2，旧绑定按 freshness 规则失效。

当前 Case 03 已通过公开 API 保存新草稿，未代替用户批准：

| 字段 | 旧批准版本 | 新草稿版本 |
|---|---|---|
| project_id / profile_id | `23c028ee-cd94-4965-af85-731e560c9633` | 同左 |
| version / status | 1 / APPROVED | 2 / DRAFT |
| record id | `71175674-6bfd-4b50-aa55-85b61defeb49` | `db33c48c-2fc3-4860-8614-647ec539b470` |
| narrative_perspective | null（DB 未存字段） | THIRD_PERSON |
| hash | `4a65f88c4e78c362435ce02d5e7a75e5b729c7f0fc8420ceeb4fada07f8236e1` | `65b5845a46d30da3db6f4fe5950029442c918035f8b7031bae8db4a6cede7ff3` |

`current_profile_version=2`，`approved_profile_version=1`。其余偏好逐项保持原值。GET state / approved / versions 与直接 DB 查询一致，见 [API 证据](../../evals/writing/v0.1/perspective-smoke/project-profile-draft.json) 和 [DB 证据](../../evals/writing/v0.1/perspective-smoke/database-verification.json)。

## 7. Authority

Profile 继续为 `A5_USER_PREFERENCE`，批准不会提升为 User Lock、Requirement 或 System Rule。人称约束决定正文叙述方式，不能修改故事事实、MUST/FORBIDDEN 或已批准 Plan。更高 authority 冲突仍按现有规则处理并报告。

## 8. Context Integration

现有 `WritingProfileContext.query()` 只选择 approved 记录，调用领域 `preferences.payload()` 序列化。显式人称会进入 CP-005 的 `PROJECT_WRITING_PROFILE` item；没有批准 Profile 或只有 Draft 时不会凭空生成该 item。

已有 Planning Profile selector 可看到同一偏好字段。本补丁没有修改 Planning Prompt、选择器或剧情策略，没有新增 ContextProfile。集成测试校验 Profile v1 approved / v2 draft 时 Writer 收到 v1，批准 v2 后新任务才收到 v2。

## 9. Writing Prompt Integration

新增 `backend/novel_os/prompts/library/task_template/write-chapter/v4/`，manifest 为 STABLE，content hash：`f26a1a252164967ac19d22b4d73962093d30de1314c68cdc163771b4a0950235`。

v4 保留 v3 全文，末尾只追加叙事人称说明：依照 exact approved Profile；THIRD_PERSON 的主体叙述使用姓名、他/她等第三人称，FIRST_PERSON 使用第一人称；对白中的“我”“你”“我们”允许；null 保持原行为。自动测试检查 v4 的版本、内容 hash、增量范围及两种指令。

没有修改 Natural Prose skill、描写密度、节奏、创意探索或其他风格段落。没有新增代词 regex、词频阈值或 NLP 检测器。

## 10. UI

写作偏好增加“叙事人称”下拉：未指定 / 第三人称 / 第一人称。已批准摘要使用中文显示。打开编辑器、保存、刷新均保留选择；清空保存为 null。

保存草稿与批准版本保持分离，保存 v2 不改变 v1 的已批准摘要。浏览器 E2E 验证保存 THIRD_PERSON、刷新保留、明确批准 v1，然后保存 FIRST_PERSON v2 并确认 v1 仍批准，最后显式批准 v2（全部使用隔离测试数据）。

Manual Case Loader 只增加独立项目提示，不复制前一个 Case 的正文。正常同项目的前文 Context 选择仍生效，后续 Case 04/05 应由用户选择独立项目以隔离。

本地 Backend 与 Docker Worker 已加载补丁；数据库 health 与前端首页均可访问。

## 11. Lineage

沿用 `writing_profile_id` / `writing_profile_version` / `writing_profile_hash`，通过具体 Profile 证明该版本的人称。ContextPackage 保存 item 及 approved source snapshot；PromptLineage 保存实际使用的 write-chapter v4；WritingResult / AgentRun 可回溯已有链路。

没有新增 lineage 表。测试校验持久化 Context 与请求一致、PromptLineage 对应 Task / v4，以及审批新 Profile 后旧 Context 未变。

## 12. Freshness

沿用 STYLE-001 校验，新测试分别覆盖：Task 排队后更换批准人称、组装 Prompt 后而模型调用前更换、模型执行期间更换。前两种不调用 Provider；最后一种丢弃旧结果。均返回 CONTEXT_STALE、阻塞且不生成 ChapterVersion 或 WritingResult，不会暗中切换任务绑定。

批准新 Profile 后，已绑定旧 Profile 的 Plan / Task 可能要求显式重新规划。这是已有防 stale 行为；批准新 Profile 不会改写旧 Draft，也不会自动重写本次第三章。

## 13. Tests

| 覆盖要求 | 证据 |
|---|---|
| FIRST_PERSON、THIRD_PERSON、非法值 | Domain / API contract 单测、HTTP 422 集成测试 |
| historical absent / null 与 hash 不变 | 旧 fixture 规范化 hash 单测、历史 DB 字段与行快照核对 |
| Draft 不进入 Context、v1 approved / v2 draft | CP-005 与 Provider 请求集成测试 |
| 批准 v2 后新任务绑定 v2 | 新章节 Writing 测试，旧 Context 保留 |
| perspective / Profile binding / Prompt lineage | 持久化 Context item、ID/version/hash 与 v4 断言 |
| queued / before-model / in-flight freshness | 3 个独立时点测试，验证调用次数与无输出落库 |
| THIRD/FIRST 指令、对白“我/我的/我们/你”不误杀 | Prompt 单测及真实结果处理链 Mock 测试 |
| A5 不能覆盖 MUST/FORBIDDEN、Lock、Canon/Plan | 扩展既有 authority 测试，核对批准 Plan 前后未变 |
| frontend view/edit/save/approve | Vitest 与浏览器 E2E |
| 独立 Case 提示 | ManualCaseLoader 组件测试 |

| 检查 | 结果 |
|---|---|
| backend `uv run pytest`（修正旧断言后完整重跑） | **939 passed / 4 skipped / 2 warnings**，666.07s |
| Profile / Perspective 定向后端测试 | 43 passed，45.02s |
| `uv run ruff check` | PASS |
| `uv run ruff format --check` | PASS，264 files already formatted |
| `git diff --check` | PASS |
| frontend `npm test` | 57 passed，5 files，1.08s |
| frontend `npm run lint` | PASS |
| frontend `npm run build` | PASS（包含 vue-tsc） |
| `npm run test:e2e -- perspective.spec.ts` | 1 passed，3.9s；隔离测试库 / Mock |
| Docker Worker / Backend / Frontend | Worker 确认 THIRD_PERSON enum 与 write-chapter v4；DB health OK；首页 HTTP 200 |
| migration | 无新 migration；原有迁移往返 / metadata 检查纳入完整测试 |

首轮完整后端测试为 936 passed / 3 failed / 4 skipped。4 条 skip 均为需要显式 `--live-model` 的真实调用（Provider、Requirement、Planning、Writing），按本轮授权范围保留跳过。

首轮全量发现旧 `test_contradictory_review_is_rejected_before_persistence` 的 3 个参数用例期待 C91_FAILED。移除本补丁的临时代码副本也复现同样 3 个失败。既有一次尝试 Worker 会产生 SCHEMA_PARSE_ERROR / MANUAL_RETRY_REQUIRED / C90_BLOCKED，等待显式重试。仅修正过期断言并增加错误码、失败状态、一次尝试和 disposition 校验；保留矛盾 Review 不落库、不自动重试的检查。未修改运行策略。该文件单独回归 9 passed。

## 14. Real Provider Smoke

**NOT_RUN**。没有本次 Profile 的用户明确批准，也没有本次新 smoke 的模型调用授权。此前 Case 03 的重试授权不复用于此阶段；本轮自动验证均使用 Mock / RecordedProvider，没有真实模型消费。

已提供 [人工 smoke 模板](../../evals/writing/v0.1/perspective-smoke/human-review.md)：独立 Project、第一章、简单车站需求，保持其他偏好不变。授权后才执行并记录完整 lineage；人工通读主体叙事人称，不因对白出现“我”“你”判失败。不把工程链路通过等同于真实生成效果通过。

## 15. Historical Compatibility

`payload()` 在人称为 None 时省略新字段，使旧规范化 JSON、Profile hash 与 Context source snapshot 不改变。API 仍显式返回 null，支持用户查看未指定状态。只有明确 FIRST_PERSON / THIRD_PERSON 才参与新版本 payload 和 hash。

部署及创建 v2 前后直接比较数据库行的规范化 JSON hash：旧 Profile 1 行、Chapter 3 行、Plan 9 行、ChapterVersion 2 行、WritingGeneration 2 行、PromptLineage 30 行、ContextPackage 30 行全部一致。未改写任何 Case 01/02/03 旧输出。

无新 migration，未对开发库执行 downgrade；完整测试中的 migration roundtrip 使用隔离测试 schema。

## 16. Known Issues

- Prompt 约束不能证明模型必然遵守，实际第三人称效果等待真实 smoke 与人工阅读。
- 当前项目 v2 仍为 DRAFT，需要用户在写作偏好中明确批准；当前生效的仍是未指定人称的 v1。
- FastAPI / Starlette 测试依赖有两条上游 deprecation warning，本补丁不升级基础依赖。
- 本轮“Case 03”实际样本与仓库同名 fixture 的差异已明确记录，不能混用作为严格回归证据。

## 17. Deferred Writing Findings

`UNSELECTIVE_DETAIL`、`LOW_IMMERSION`、`GENERIC_INNER_VOICE`、`SAFE_GENERIC_CREATIVE_CHOICE`、`LOW_CREATIVE_NOVELTY`、网文感不足已录入 Case 03 human review。它们是用户反馈，尚未逐段评分；不伪造检测结果。等 Case 04 / 05 后统一分析。本轮没有调整对应规则或开始 NOVEL-009。

## 18. Acceptance Result

独立 agent 对本次增量及相关调用链完成审查：未发现 Critical / Required 问题。重点检查了 A5 authority、null 历史兼容、Draft 隔离、stale task、exact binding、Prompt 版本、无脆弱代词检测、显式批准 UI 及范围边界。补充审查确认旧 Plan Review 测试修正没有掩盖行为变化（与修改前副本的运行时代码一致），并检查了浏览器 E2E、反馈与 smoke 文档。独立审查没有宣称验证真实模型效果，线上 DB 核对由主任务完成。

| 验收层 | 结果 |
|---|---|
| Engineering Acceptance | **PASS**：完整后端、前端、浏览器流程、lint/build、数据兼容和独立审查通过 |
| AI Behavior Acceptance | **NOT_RUN**：本轮真实模型 smoke 未授权、未执行 |
| Human Perspective Evaluation | **NOT_EVALUATED**：待人工阅读新生成正文 |
| STYLE-002 overall | **CONDITIONAL PASS**：工程部分完成，等待 Profile v2 明确批准与真实生成的人称验收 |

未发现未解决的工程阻塞项。完整回归日志保存在本机 `/tmp/novel-style002-pytest-final.log`，前端测试日志为 `/tmp/novel-style002-frontend-test.log`，浏览器测试日志为 `/tmp/novel-style002-e2e.log`；这些是本次运行的临时证据，长期可复验依据为仓库中的测试代码及上述 DB/API 证据文件。

停止于 STYLE-002。用户下一步为查看并明确批准 Profile v2；真实 smoke 需单独授权后执行。
