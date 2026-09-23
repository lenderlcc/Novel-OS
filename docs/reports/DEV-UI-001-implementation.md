# DEV-UI-001 — Novel OS Internal Test Console

日期：2026-09-15。分支：`wfg/dev-ui-001-test-console`，基于 `bc53b48`。

## 1. Implementation Summary

新增内部浏览器测试控制台，连接现有自然语言需求 → CreativeBrief → Planning → Plan Review → HumanGate → Writing → Draft 链路。用户不需要复制 UUID 或拼 JSON。**DEV-UI-001 = PASS**。前端 35 项测试、8 条浏览器 E2E、Backend 全量 784 项测试通过；独立 Review 无剩余 Critical / Required。

## 2. Purpose / Scope

仅 DEV-UI-001；没有开始 NOVEL-009。没有引入登录、RBAC、正式产品前端、LLM 新 Provider、Review Agent、QualityEngine、Revision、Memory Commit 或 Human Chapter Acceptance。模型行为沿用现有 Backend；本次测试全部 Mock，真实模型调用数为 0。

编码前已读取六份 specs、NOVEL-001～008 implementation reports，以及实际 FastAPI routes / OpenAPI。历史设计中的后续业务不作为本 Ticket 的实现范围。

## 3. Frontend Architecture

Vue 3 + TypeScript + Vite；单页面、一个状态 composable、集中 API client、功能组件。无需 Router / Pinia。运行时依赖仅 Vue。API 类型从真实 OpenAPI 一步生成并存入源码，不要求构建时运行 Backend。

`src/api/client.ts` 统一 HTTP、错误、JSON、超时、request_id、分页；`src/api/console.ts` 封装现有业务接口；`useConsole.ts` 管理选择、快照、命令、版本与轮询；Component 不自行 `fetch`。Debug 组件调用同一 API 层进行按需查询。

## 4. Page Structure

单页从上到下：Project/Chapter/Workflow、进度、Requirement、CreativeBrief、Plan/Review/HumanGate、Draft、流程控制、Advanced/Debug。顶部有页内跳转。普通表单、列表、表格与阅读区域；无富文本编辑器、大型 UI 框架、仪表盘或主题系统。

## 5. API Integration

下表均位于 `/api/v1`：

| 用途 | 接口 |
| --- | --- |
| 项目、章节 | GET/POST `/projects`、`/projects/{p}/chapters`；GET `/projects/{p}/chapters/{c}` |
| 找回 Workflow | GET `/projects/{p}/chapters/{c}/workflows`（新增） |
| 创建、提交需求 | POST `/workflows/chapter-writing`，POST `/workflows/{w}/events` 的 `USER_SUBMITTED` |
| 当前流程、历史、门 | GET `/workflows/{w}`、`/history`、`/human-gates` |
| 人工方案决策 | POST `/human-gates/{g}/decision` |
| 既有流程控制 | POST `/workflows/{w}/pause`、`/resume`、`/cancel` |
| 需求、规划证据 | GET `/workflows/{w}/creative-brief`、`/planning/history` |
| 方案、正文历史 | GET `/projects/{p}/chapters/{c}/plans`、`/versions` |
| Writing lineage | GET `/workflows/{w}/writing/history` |
| Task / Run | GET `/workflows/{w}/agent-tasks`、`/agent-tasks/{t}/runs` |
| 精确 Context / Prompt | GET `/agent-runs/{r}/context`（新增）、`/agent-runs/{r}/prompt-lineage` |

所有列表按 Backend 分页读取，不会因为默认 100 条而漏掉后续 Gate 或版本。普通界面通过关系自动管理 ID，内部标识集中放在 Debug。

## 6. Project / Chapter Selection

创建项目只需名称；创建章节只需标题和序号，遵守 Backend 校验。项目/章节切换后清空旧 Workflow 快照并取消旧查询。重新进入页面选择项目和章节后可找回 Workflow；不引入浏览器持久化。新增查询严格按 project/chapter 两个字段限制。

## 7. Requirement Input

直接提交用户原始自然语言（最大 12000 字符），不要求结构化 must/forbidden 等字段。创建正式 Writing Workflow 后再提交 `USER_SUBMITTED`，Worker 按现有机制调度。创建成功但提交失败时可刷新找回 C00 流程，继续提交，不需要重新创建。网络异常不会自动重放写请求。

## 8. Workflow Progress

C00～C08、C90/C91/C92 提供中文说明与 machine state。Requirement → Context → Planning → Review → Human Approval → Writing → Draft 显示已完成/当前阶段。暂停、Blocked、Failed、Cancelled 有独立展示；未知状态安全显示且停止自动轮询。C08 只是本次测试终点，不宣称正文已批准或质量已通过。

## 9. CreativeBrief View

显示 Intent、Objective、Must/Should/Preferences/Forbidden/Preserve、Required Outcome、Reader Effect、Creative Freedom、Assumptions、Ambiguities、Conflicts、Confidence。结构化内容按列表和字段阅读，源码引用等内部字段可在 Debug 原始证据中查看。

## 10. ChapterPlan View

显示目标、结果、开场作用、每个 Scene 的作用/冲突/关键变化/信息释放/人物变化/结束条件、人物和情节推进、结尾、约束、保留元素、风险、新元素和重大变更提议、需求覆盖。Plan Review 与所选 Plan ID 匹配，展示 verdict、硬问题、质量问题、冲突与建议。历史 Plan 不会混入当前方案的 Review。

## 11. HumanGate Interaction

APPROVE / REJECT / REQUEST_ALTERNATIVE / MODIFY 只调用已有 HumanGate API。后三种动作要求填写自然语言反馈，原文交给 Backend。审批请求携带当前所见 Workflow state_version 与 Gate artifact_version，不发送 actor、authority 或 approved state。

只有所选 Plan 与当前等待门完全匹配时才展示审批控件；历史版本不可借用当前 Gate。`VERSION_CONFLICT` 显示“当前方案已发生变化，请刷新后重新审批。”并撤下审批操作。无自动重试或先偷偷读取新 token 再提交旧决策。

## 12. Writing / Draft View

批准后自动轮询既有 Worker 执行结果；没有运行 Agent 的前端捷径。正文来自 `ChapterVersion.content`，纯文本渲染、保留段落、适合阅读的宽度、可滚动，不用 JSON `<pre>` 展示正文，不解释模型 HTML。

默认正文必须有当前 Workflow 的 WritingGeneration 绑定。新 Workflow 从 Chapter 继承旧 draft_version 时不会误显示旧稿为本次产物，历史稿仍可手动查看。Writing metadata 默认折叠，覆盖 Ticket 指定全部九项字段。

## 13. Version Display

普通视图和 Debug 均分别显示 Plan / Chapter 的 Current 与 Approved。Plan 和正文版本下拉保留历史；当前流程默认正文与章节最新稿分开。浏览器通过正式 Core API 构造 `Plan current=v2 PROPOSED / approved=v1`，确认显示分离、旧批准方案和已生成正文不受影响。UI 未添加 Core 直接审批按钮。

## 14. Error Handling

统一展示 error code、message、request_id、可折叠 details。处理 Backend JSON 错误、代理非 JSON 错误、网络/超时、404 可选产物和版本冲突。只对“产物尚未存在”的 404 返回空，不吞掉其他错误。Blocked 显示 block_reason / guard；Failed 展示 Task 的错误，并可查看 Run。

持久化 Workflow / Run DTO 没有原 HTTP request_id 时明确写“未提供”，不伪造；API 命令错误保留真实 request_id。错误后停止轮询，由用户手动刷新。

## 15. Debug Panel

默认折叠，首次展开才查询 Workflow History / Runs / Context / Prompt。可由公开配置关闭。展示版本指针、Agent 状态与错误、生成证据及原始结构化数据。模拟记录跳过不适用的正式 Planning 查询，仍可只读查看 Workflow 和 Debug。

## 16. Context Inspector

严格按用户选择的具体 AgentRun 读取当次 Context，显示 Profile/Version/Hash、Build Status、当前 Freshness、预算/估算 token、Included source/version/priority/authority/status/reason、Excluded source/reason，以及折叠内容、缺失项和冲突。历史快照的当前 Freshness 可能 STALE，页面说明其与当时 Build Status 的区别。

## 17. PromptLineage Inspector

显示 system policy、role、task template、skills、quality profile 的 Module ID、版本、content/execution hash，以及 ModelProfile 和 compiled prompt hash。仅查看 Backend 给出的 lineage，不在浏览器组装 Prompt，不展示密钥。

## 18. Agent Inspector

Task 展示 agent/type/status/attempts/error；Run 展示 attempt/status/provider/model/duration/error/disposition。点击 Run 可切换当次 Context/Prompt。Generation lineage 按 API 原样展示 WritingGeneration 与 metadata；正文仍由 ChapterVersion 提供。旧记录缺失 Context/Prompt 时明确展示未生成。

## 19. Polling / Refresh Strategy

活跃 C01～C07 每 1.5 秒；C06 HumanGate、暂停、C08、本阶段外状态和终止状态停止。使用请求完成后排下一次 `setTimeout`，避免重叠。错误停止。手动刷新重新建立快照。

选择变化使用 epoch + AbortController；忽略不能取消的迟到响应。快照读取前后核对 state_version，状态推进时重新查询，不发布混合版本。写入期间取消旧读取。组件卸载会取消请求和定时器；disposal fence 防止迟到的创建响应继续提交或重启轮询。Debug 独立清理请求，切换 Run 时先清空旧 Context/Prompt。

## 20. Backend Changes

两个最小只读入口：

1. 章节 Workflow discovery：API → WorkflowRuntime → WorkflowRepository；先校验章节所属项目，再分页查询。
2. Run Context inspection：API → ContextService.inspect(run_id=...) → 原 Repository 与 freshness 校验；准确查当次 snapshot。

修改五个 Backend 源文件，新增一个测试文件、三个测试。没有数据库表、迁移、Service 写业务、Authority、HumanGate 或 Worker 调度规则的变动。Repository 没有 commit。Migration head 保持 `0009_writing_agent`。

## 21. Frontend Tests

**35 tests PASS / 4 files**：

- HTTP 统一错误、非 JSON、404/422、分页、准确审批 payload、原始反馈、不重试。
- 已知/未知状态和轮询策略。
- Brief/Plan/Review 渲染、Gate 交互、正文段落/HTML 转义、折叠 metadata、错误提示、Blocked、Debug 懒加载/准确 Run/版本指针。
- 自动轮询无重叠、人工等待停轮询、版本冲突后不重试、切换项目/章节丢弃迟到响应、卸载后不提交/不轮询、模拟流程可读、跨流程旧稿隔离。

静态 fixture 来自临时 Mock E2E 数据库，只有测试故事和随机 ID，没有用户数据或 credential。

## 22. Browser E2E

**8 tests PASS，32.0s**，Chromium / Playwright，真实 FastAPI + PostgreSQL + 独立 AgentWorker，Mock Provider。

| 案例 | 结果 |
| --- | --- |
| A：创建/自然语言/Brief/Review/Approve/Writing/Draft/lineage/重载找回 | PASS |
| B：Reject 原文反馈 → Plan v2，v1 仍可读，审批后写作 | PASS |
| C：Request Alternative → Plan v2 | PASS |
| Modify → Plan v2 | PASS |
| 第二客户端变更门，旧页面提交只发一次并收到 VERSION_CONFLICT | PASS |
| Mock Agent failure，页面显示 FAILED 和对应 Run | PASS |
| 真实 Plan current v2 / approved v1 分离 | PASS |
| Vite 拒绝读取 Backend 配置目录 | PASS |

测试通过临时 `_test` schema 隔离，结束清理；无产品测试控制路由。早期一次断言误用了设计名称而非实际 `CP-005 v3`，已修正；一次开发中 Vite HMR 刷新影响正在运行的用例，停止源码编辑后完整重跑通过。最终配置不自动 retry 测试。

## 23. Backend Regression

全量 `uv run pytest`：**784 passed、3 skipped、2 warnings，495.05s（8 分 15 秒）**。3 个 skipped 均为显式 opt-in 的真实 Provider 测试。新增接口专项测试 **3 PASS**，包括 project/chapter scope、分页、只读性、重试两次 Context 区分、无 snapshot 的 404。既有 Core / Workflow / Agent / Prompt / Context / Planning / Writing、事务、并发与 migration 测试均通过，没有削弱安全规则。

## 24. Build / Typecheck / Lint Result

- `npm install`：PASS，生成并保留 package-lock；TypeScript 固定 `~5.9.3` 与当前工具链兼容。
- `npm run typecheck`：PASS。
- `npm run lint`：PASS。
- `npm run build`：PASS；JS 101.13 kB，gzip 37.70 kB；CSS 2.75 kB。
- `npm test`：35 PASS。
- Backend `ruff check`：PASS；`ruff format --check`：225 files PASS。
- E2E Python host 单独 Ruff check/format：PASS。
- `npm audit --omit=dev`：0 vulnerabilities；安装时全依赖 audit 也为 0。
- `git diff --check`：PASS。

工具：Node 22.22.0 / npm 10.9.4；Vue 3.5.42、Vite 8.3.0、TypeScript 5.9.3、Vitest 5.0.1、Playwright 1.63.0。依赖精确版本以 lockfile 为准。

## 25. Docker Result

`docker compose up --build -d --wait backend` 成功。backend / postgres / postgres-test 均 healthy。`/api/v1/health`、`/api/v1/health/db` 均 HTTP 200，带 X-Request-ID；容器 OpenAPI 包含两个新增只读接口。前端使用单独 Vite，无 Compose 改动、无 nginx。

`alembic current` 为 `0009_writing_agent (head)`；本 Ticket 没有迁移，浏览器测试从空 schema 应用完整 head。既有 migration round-trip 由 Backend 全量套件验证，不对开发数据做降级。

## 26. Manual Test Instructions

详细命令见 README 的 DEV-UI-001 小节。已启动本机 http://127.0.0.1:5173 控制台、Docker Backend 和独立 Mock Worker。

人工可直接：创建 Project → 创建 Chapter → 输入需求 → Start → 阅读 Brief/Plan/Review → Approve → 阅读 Draft → 展开 metadata / Debug。测试 Reject/Alternative/Modify 时填写原文反馈。测试版本冲突可在两个浏览器页面打开同一门，一个先操作，另一个再提交。失败可在 Backend TOML 将 Mock scenario 改为 ALWAYS_FAIL 并重启 Worker，测试结束恢复 SUCCESS。

本机 local/runtime TOML 均为 mock-default，未配置真实 credential。本次没有运行付费调用；AI 理解、plan adherence、knowledge leakage 和文笔等真实行为质量仍需人工 opt-in 的真实 Provider 测试。

## 27. Acceptance Criteria PASS / FAIL

| 验收项 | 结果 |
| --- | --- |
| 无需内部 ID/JSON 的完整浏览器 Writing 链路 | PASS |
| 原始自然语言与真实 HumanGate 版本绑定 | PASS |
| Plan 历史保留、Current/Approved 分离、旧稿隔离 | PASS |
| Blocked/Failed/未知状态与可定位错误 | PASS |
| Debug/Context/Prompt/Agent/Generation 可读 | PASS |
| Poll cleanup、race、stale approval 防护 | PASS |
| 前端 tests/typecheck/lint/build | PASS |
| Docker/health | PASS |
| Backend 全量回归 | PASS（784 passed，3 个 paid opt-in skipped） |
| 独立 Review、无剩余 Critical/Required | PASS |
| 不开始 NOVEL-009 | PASS |

独立只读 Reviewer 发现并复核修复三项 Required：模拟流程误调正式查询、旧正文误作当前产物、卸载后迟到请求继续提交/重启轮询。独立执行 35 个测试、typecheck、lint 均通过，最终结论 Approve；未重复运行 Backend/E2E。

## 28. Architecture Deviations

无已确认架构的偏离。因实际数据缺少读取入口，按 Ticket 允许范围新增两个只读接口。没有重构 NOVEL-001～008 稳定基础设施。前端公开 `.env.example` 为本 Ticket 明确要求，Backend TOML-only 配置规则保持不变。

## 29. Known Issues

- Mock 只能验证工程链路，不能证明文学质量或任意需求理解准确。
- Backend 某些持久化失败记录没有原 HTTP request_id，UI 如实提示并提供 Run 关联排查。
- 本工具为本机内部单用户控制台，没有新增鉴权或公网部署能力。
- npm 安装可能提示 ESLint 9、测试工具传递依赖的弃用提示；本次安装/audit/检查均成功。不会使用 `--force` 或跳过 peer 检查来解决兼容性。
- Backend 的两条既有弃用警告来自 Starlette TestClient/httpx 和 AnyIO BlockingPortal 别名，未为此改动稳定依赖。

## 30. Deferred Items

真实 Provider 的人工 opt-in 测试、文学质量评估、专用 Requirement 澄清重提 UI、Draft regeneration UI、正式产品交互、SSE/WebSocket、登录/RBAC，以及 NOVEL-009 及其后续业务全部保留后续处理。Blocked 的查看、恢复/取消使用现有接口，不在本 Ticket 新增业务状态。

此前未追踪的 `docs/reports/NOVEL-008-acceptance.md` 与 `evals/writing/v0.1/` 原样保留，不属于本 Ticket 新增实现。当前未提交、未推送；等待用户 Review。
