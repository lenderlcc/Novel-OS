# NOVEL-010B — Revision Workspace Integration

日期：2026-09-28。基线：`3804b0f`（NOVEL-010A），分支：`wfg/novel-010b-revision-workspace`。

## 1. Background

010/010A 已提供定向修改、不可变 successor、Fidelity Gate 和自动重审。用户需要在原 Chapter 内完成 Draft → Review → 显式修改 → 新 Draft → 新 Review，并保留原稿阅读入口。

## 2. Problem Statement

已有主按钮受有效 Review、approved Profile、Workflow v3 限制；历史 v2 无正式 Review 不能直接修改。版本入口藏在折叠区，阅读选择和后台当前版本混用；刷新可覆盖显式选择，活动 Revision 依赖数组第一项，失败/历史查看的阶段标题不准确。真实验收还发现 CP-007 v4 容量不足，见第 20 节。

## 3. Scope

完善现有 Workspace 和必要 Context 容量配置。真实重审发现引用格式阻塞后，新增 A05 evidence skill v3，明确跨段论证须拆成单段引用。后续 Review 修复了人工评价版本固定、Fidelity 预算恢复入口和模型窗口预检，详见第 24 节。无新端点、数据库表、migration、Agent、状态或 Revision 策略；未修改 Quality detection/taxonomy、A06 Prompt。未实现 011/012、Diff、编辑器、Restore 或 Issue 勾选。

## 4. Existing NOVEL-010 Audit

| 能力 | 既有实现 |
| --- | --- |
| Command/API | `api/revision_routes.py`，REQUEST_REVISION |
| Request/source binding | `services/revision_binding.py` |
| RevisionPlan/A06 | 既有两阶段 task 和版本化 Schema |
| source version/review | Request 冻结两个 immutable ID 和 QualityBinding |
| successor | `services/versioning.py`，同章 parent/supersedes |
| Fidelity | `services/revision_results.py`，PASS 后才创建版本 |
| Re-Review/STOP | `services/agent_results.py`、`workflow/runtime.py` |
| Version/Review 列表 | 现有分页 GET，足够按 exact ID 读取 |

结论：复用主链路，不建立第二套 Backend。独立审计确认 v1/v2 保持旧行为；不能擅自修改 Workflow definition version 接入新能力。

## 5. Backend Entry

使用现有 POST `/api/v1/workflows/{id}/revision`。输入 `event_id / expected_state_version / expected_draft_version / source_review_id / reason`。Workflow 确定 project/chapter，Review 精确确定 Draft。Service 执行权限、锁、freshness、幂等与事务校验。

## 6. ChapterVersion Handling

Fidelity PASS 后在原 chapter_id 下创建新 ID、version+1、parent/supersedes；源 content/hash 不变，approved pointer 不变。Fidelity FAIL 不创建可接受新 Draft，保持原 current。新增集成断言核对整个项目的 Chapter ID 集合前后相等。

## 7. Revision Request API

没有改变 DTO/权限。按钮冻结已显示的 source Review/Draft/state tokens；不确定投递重用 event_id；重复点击被 busy 阻止，409 不自动重发。不允许前端提交正文、Agent、Authority 或指针。

## 8. Workspace UI Integration

保持左侧 Chapter 导航和居中正文阅读器。复用“需求 → 方案 → 正文 → 审阅 → 修改”。`revisionWorkspace.ts` 集中派生修改状态，活动证据通过 request.id 精确匹配；Raw JSON/内部标识留在 Debug。

## 9. Review CTA

当前正文、当前 Workflow、有效 non-PASS Review、approved Profile、WAITING_HUMAN 才显示主修改按钮。PASS/历史稿隐藏。Profile 缺失/Review 过期提供明确恢复入口。执行中显示禁用的“修改进行中…”。旧流程给出不能修改的实际原因，不提示新建 Chapter 代替修改。

## 10. Revision Processing UX

显示分析范围、修改正文、检查修改范围、重新审阅。FAILED/CANCELLED/PAUSED 不再伪装成运行中。C09 全局阶段不随 viewingVersion 改变，正文区审阅状态仍精确绑定所选稿。后台队列文案不再暴露 Worker。

真实验收发现旧失败任务被误用作新业务阻塞说明，已限定为同 workflow_id、终止前一 state_version 的 FAILED/BLOCKED task；没有当前技术错误时使用 Workflow 的实际 block_reason。合法“依据不足”不会再显示之前的 SCHEMA_PARSE_ERROR。

## 11. Draft Version Selector

正文顶部原生 select：`Draft v2 · 当前`、`Draft v1 · 原稿`、其他历史版本。只读历史，原稿永久保留。没有 Branch/Restore/Merge/Diff。

## 12. Current vs Viewing Version

`currentBackendVersion` 来自 Chapter；`viewingVersion` 独立保存在页面。初次打开跟随 current；显式选择后固定阅读位置。即使慢轮询开始时 v1 仍是 current，晚到的 v2 也不会覆盖已选 v1。显式开始新修改可跟随后继稿；请求期间再次选择历史则继续保留选择。浏览器重新加载默认 current。

## 13. Review Version Binding

按 exact chapter_version_id 筛选；同稿多个 Review 用服务端 Review.version 取最新记录，测试打乱数组顺序验证。修改前另验证 workflow_id，不能把其他章/流程 Review 用作当前操作。Human Evaluation 在打开时冻结所选 Draft ID/version、Project/Chapter/Workflow/Case；后台产生 successor 不重挂载弹窗、不清空输入，标题明确被评价的版本。关闭后重新打开评价才选择新的阅读版本；现有评价仅下载本地 JSON，不提供服务端历史查询或自动回填。

## 14. Fidelity Failure UX

固定文案：“这次修改范围过大，未替换当前正文。”提供详情、未采用稿和 Debug 检查入口，不自动 retry。业务缺少依据与技术错误分开；技术恢复仅沿用已有 Workflow 允许的按钮。预算拦截明确说明当前阶段尚未调用模型，不能据此推断之前阶段没有消费。

## 15. Polling and Concurrency

活动修改/重审 1.5 秒轮询，完成/受阻/失败停止。切章 Abort/epoch 丢弃晚到响应；版本切换不会写任何 API，也不被旧轮询覆盖。活动 request 按 ID 匹配。刷新不调用 Revision；Review FAIL 不自动生成 v3。

## 16. Tests Added

- 前端：慢轮询中固定版本、新请求自动跟随 successor、Review 乱序/跨 Workflow、C09 阅读 v1、重审刷新恢复、停止轮询、旧 v2 原因、终止状态、人工评价不跨版本继承。
- 后端：完整修改 slice 增强同章/新 ID/精确 source Review、Chapter 集合不变、versions 列表和 current 检查；复用既有 stale/并发/权限/Fidelity/rollback 测试。
- Context：三个阶段的真实 Prompt/Schema overhead 加合成多源中文 P0 输入；v4 hash 固定、v5 选择策略不变、所有 P0 不丢失、超大输入继续拒绝。
- 浏览器：隔离 `_test` schema、真实 API/迁移/Worker、Mock Provider；成功同章 v2 + 重审 FAIL STOP，Fidelity 拒绝保留原稿。生产案例不使用测试 marker。

测试文件按此前要求保留本地，不加入提交。

## 17. Browser Acceptance

自动浏览器 Revision 两条场景已通过。真实浏览器打开既有第 7 章“继续3”，核对原稿和正式 Review，通过实际“根据审阅修改”按钮发起请求；没有创建 Chapter。真实执行最终结果见下节。

## 18. Case 05 Acceptance Result

选用已存在且有正式 Review 的固定结局 Case05，Brief 原文为“主角最终仍然选择继续原来的计划……”。不是 `evals/manual/case-05.json` 的旧身份隐瞒样例，也不是“暴雨中继台”。

| 对象 | ID |
| --- | --- |
| Project | `23c028ee-cd94-4965-af85-731e560c9633` |
| Chapter | `8a345f75-f673-4efb-8a93-342da83d2180`（第 7 章“继续3”） |
| Workflow | `15aaf3b7-6c6f-4832-b490-fcb03f3dfffa` |
| Source Draft v1 | `ac433c00-5906-470a-9fcf-e300621c533b` |
| Source Review v1 | `4f2993ae-7933-4b8c-b941-48ebace12129`，FAIL，CURRENT |
| Approved Profile | `db33c48c-2fc3-4860-8614-647ec539b470`，v2 |

初始原稿 SHA256：`474319ab874dd55af8b6516aa24ee34bdc55217d199cb44f3307ecb6c5d08e7f`。项目 8 个 Chapter。

首次 Request `5ee62a28-7e70-4b4f-8be8-65fe1ceef2a9` 绑定 CP-007 v4，在 Provider 前因预算不足 BLOCKED，0 次模型调用、无 Plan/candidate/new Draft。旧记录与 hash 保持不变。容量修正后通过现有“重新审阅正文 v1”入口恢复，两次 Narrative 均被非法跨段引用阻塞。离线确认证据协议缺少明确的分段说明后，按第20节做最小版本化修正，再对相同原稿重审成功，并从浏览器发起新 Revision。

| 执行 | 结果 |
| --- | --- |
| 原 Revision Plan，run `5b330309-7881-4433-b25e-85fe01ace319` | Context budget 阻塞，未调用 Provider |
| 显式重审 Compliance，run `dbf92775-1229-4866-b9b5-3b4e7c3fcbbe` | SUCCEEDED |
| 显式重审 Narrative，run `17c6a3b5-2e07-43b5-bbd4-1ab024f3ebce` | SCHEMA_PARSE_ERROR；三条 quote 跨27–28、38–39、67–69段，但只声明首段 index |
| 显式恢复 Compliance，run `c69deed4-eb72-4ba9-a68b-ff165e524489` | SUCCEEDED |
| 显式恢复 Narrative，run `33a2ce67-b30b-4162-aece-a2950d3711f6` | SCHEMA_PARSE_ERROR；OVER_STRUCTURED_DIALOGUE 第一条 evidence 声明第27段，引用实际跨27–28段；JSON、Pydantic 与其余业务检查通过 |
| evidence v3 Compliance，run `eb5c08e9-8471-4828-a56e-c3292b15c057` | SUCCEEDED，正式 lineage 记录 skill v3/hash |
| evidence v3 Narrative，run `d05212cf-00a7-467b-9705-733a084105c9` | SUCCEEDED，正式 lineage 记录 skill v3/hash；生成 Review v2，仍精确对应 Draft v1 |
| CP-007 v5 Revision Plan，run `136f9ac2-63be-4715-a3fa-ef7104c83408` | 执行及结构校验成功，返回合法业务 BLOCKED：缺少安全具体化 stakes 的授权依据 |

本轮实际新增 **7 次 Provider 调用**（三轮各 Compliance + Narrative，以及一次 Revision Plan），各任务只尝试一次；恢复均显式触发，无自动修复循环。现已停止继续付费调用。没有放宽单段证据校验、篡改 Review 或冻结 Request，也没有为通过验收另建 Chapter。

新 Request=`e1e67bb9-724d-4e08-a524-b38169e0f731`，source Review=`f774f445-44d8-49b3-b3a3-15f41ef1e5d3`，source Draft 保持原 v1。Plan=`ec861728-c112-475f-9eda-f687af492941`，ContextPackage=`3f5eb504-9c38-4f0c-abdc-892e1854c08f`（DB 确认 CP-007 v5），PromptLineage=`66634371-1e12-4fcf-9ac2-ba797e11e3a2`，ModelProfile=`lingzhi-structured`。未执行 REVISE_CHAPTER/Fidelity/新稿重审，因此不存在这些后续产物的 lineage。

合法阻塞原因：EDIT_BASE、批准 Plan、Brief 都未给出“原计划”的具体目标、现实投入与失败损失；解决 ABSTRACT_STAKES 需要新增未经授权的故事事实。Plan 已给出其他对白/解释修改目标，但依现有引擎语义，有 blocked_reasons 即停止，不自行改为部分执行。Ticket 第22节明确允许保持现有 BLOCKED 语义。本次不编造事实、不改变 Revision 策略，也不通过关闭问题或重新 Writing 冒充验收。

最终只读 SQL 与 API 一致：current=v1、approved=null、仍只有原 Draft，SHA256 与操作前相同，项目仍8章；正式 Review 2份均绑定同一 Draft，RevisionRequest 2份、Plan 1份、candidate/result 均0。Workflow=`C90_BLOCKED`，state_version=21，resume_state=C10。界面可继续阅读 v1、查看当前 Review 和明确业务阻塞原因，刷新未创建新请求。

**真实 Case05：业务 BLOCKED / 尚未完成 v1→v2 验收。** 技术性的 Context budget、Review quote 协议和历史错误串入问题已修复；目前不再是 Provider/Parser 故障。因为没有真实 v2，Dialogue/Explanation/Stakes 改善、原场景/真实动摇/最终方向/Strength preservation 的修订效果检查全部 NOT EVALUATED。不能用 Mock 成功替代真实通过。

证据保存在本机 `backend/.runtime/acceptance-010b/`，包含操作前章节、版本、Review、Brief、Workflow、失败 Context、三阶段预算预检、`case05-final.json` 和 `case05-db-final.json`。模型正文及本地运行数据不加入 Git。

## 19. Case 04 Regression Result

按 Ticket 仅在 Case05 通过后执行真实补充验收。已有 Case04 是同项目第 6 章“继续2”，chapter `5c8f382e-81eb-4dfa-bd9d-005a7e8c8be1`，有正式 PASS_WITH_WARNINGS Review。Case05 受阻，因此 Case04 真实修改 SKIPPED，未消费额外模型调用。

## 20. Backend Changes

生产后端配置变更一：新增 `context/profiles/CP-007.v5.json`，100000 → 240000 本地保守 UTF-8 容量。真实 P0=106407，prompt/schema=27542，output reservation=8192，合计142141，旧上限必然失败。保留原稿、Review、authority全文与全部 P0；未修改 estimator、Schema、权威或状态机。

离线预检使用真实失败 Context 的完整 P0，并为后续 Plan/candidate 分别增加25000/50000字节占位余量，Plan/Revision/Fidelity 总量为141983/155748/182533，均小于240000；这是容量预检，不能证明未知模型输出一定适配。新 v5 hash=`3096040b1492dd0b29bdb67576182868231503888451159f05ce1c94e191b195`。实际 Docker Worker 已核对版本/hash。240000 不等于实际计费 token 或 Provider 窗口。

无 migration；现有 head 保持 `0013_revision_fidelity`。Docker build/start/health/health/db 已通过（独立验证容器随后清理，保留实际服务与数据库）。

生产后端配置变更二：新增 `prompts/library/skill/quality-evidence/v3/`。两次真实 Narrative 输出均跨段引用，进一步检查发现旧 Prompt 鼓励分析完整对话，但未明确要求分条引用；新增说明要求每个 evidence 完整属于其 paragraph_index、跨段模式使用多个条目、不得拼接/省略/改写。v2 内容/hash 保留，v3 hash=`68b1c95735fec530cc9465e2bb3b8cdec9f84ac159bdf732c767073775a4429b`。仅 A05 Compliance/Narrative 使用；未修改 Validator、Schema、评分、Taxonomy 或 A06 策略。新增两项协议/负向测试与相关回归共165项通过；独立 Review 无 Blocking/Required。部署后继续对同一原稿验证，最终结果以下述实际记录为准。

## 21. Known Limitations

- 旧 v1/v2 无正式 Review 的稿件不能直接进入 v3 Revision；本次不迁移历史 Workflow。
- 人工评价维持既有本地 JSON 导出，不增加评价持久化/导入。
- Mock 证明工程行为，不证明语言质量；真实修改需保留门禁并单独验收。
- 模型输出/Provider 失败不能通过前端承诺消除；页面只提供既有状态机允许的显式恢复。
- 本轮真实 Case05 已修复重审引用阻塞，CP-007 v5 已产生正式 RevisionPlan；当前停在“缺少授权依据”的合法业务阻塞，尚无真实 v2，不能宣称完整产品验收成功。
- 接受其余安全修改并暂留 ABSTRACT_STAKES，需要现有引擎支持部分执行；本次严格保持已有 BLOCKED 策略。若继续使用该样例，应由用户在已有需求/方案流程提供并批准具体目标、投入和损失，再复验，不能由开发者补写成所谓原有事实。
- 测试有两项上游依赖弃用警告（Starlette TestClient/httpx 和 AnyIO BlockingPortal），不影响本轮结果。

## 22. Deferred to NOVEL-011

自然语言人工修改意见、局部锁定反馈、反馈解释与结构化、编辑器/版本恢复不在010B。未开始 NOVEL-011/012。

## 23. Acceptance Result

| 验证 | 结果 |
| --- | --- |
| Backend full pytest | **1246 passed / 4 skipped**，1250项，21分25秒；跳过项均为显式 opt-in 的真实模型测试 |
| 配置/引用协议增量回归 | **165 passed**；包含全量测试收集之后新增的3项容量测试、2项单段引用测试 |
| ruff check | PASS |
| ruff format --check | PASS，327 files already formatted |
| Frontend npm test | **113 passed / 7 files** |
| Frontend lint / typecheck / build | 全部 PASS |
| Mock Browser E2E | **2 passed**；同章 v2→重审 FAIL→STOP/历史切换/刷新，Fidelity FAIL 保留 v1 |
| Docker build / startup | Backend、Worker 镜像构建成功，实际 Worker 已更新；独立 Backend 容器启动成功后清理 |
| health / health/db | 均 HTTP 200 / ok，实际前后端继续运行 |
| Migration | 无变更，无新增 roundtrip；head=`0013_revision_fidelity`，全量测试内现有迁移检查通过 |
| git diff --check | PASS |

独立 Review 已覆盖既有 Backend 入口、版本/Review绑定、轮询/刷新/重复操作、历史选择、Fidelity隔离、新增配置和证据协议。发现并修复 C09 标题受历史选择影响、预算文案的消费范围歧义，以及真实验收发现的历史错误串入。最终无待修 Blocking / Required 代码项。

| 验收层面 | 结论 |
| --- | --- |
| Engineering Acceptance | **PASS**：现有引擎完成 Workspace 接入；Mock 真实 API/DB/Worker 闭环通过 |
| 原稿、Chapter、authority 保护 | **PASS**：真实失败路径保持正文/hash/指针/章节数量，未绕过 Workflow |
| 真实 Case05 完整 Revision | **BLOCKED**：已到合法 RevisionPlan，但缺少授权背景事实，未产生 v2 |
| Case04 真实补充回归 | **SKIPPED**：遵守 Case05 通过后才执行的前置条件 |
| Human Prose Evaluation | **NOT EVALUATED**：本轮无真实修订稿可比较 |
| NOVEL-010B 总体 | **BLOCKED，尚不能宣称完整产品验收 PASS** |

进入下一阶段前，应先解决 Case05 的授权依据缺口并在同一 Chapter 重跑 v1→Revision→v2→Review，验证真实历史切换与刷新恢复；随后按要求执行 Case04。不要放宽 Fidelity、伪造 evidence、覆盖源稿或新建 Chapter 替代此项验收。

本次未提交/推送，测试代码及模型运行证据保留本地；未开始 NOVEL-011/012，停下等待用户 Review。

## 24. Review Fix Verification（2026-09-28）

针对后续代码 Review 的三项 P2 完成局部修复：

1. **人工评价版本固定**：根因是弹窗绑定可随轮询变化的 `draft`，`draft.id` 变更使 Vue 重挂载并丢失输入。改为打开时捕获评价目标；阅读器仍可跟随新正文，评价对象和备注/评分保持原版本。关闭后为新版本重新打开时输入独立。
2. **Fidelity 预算阻断恢复**：原判定只检查 A06 或已有 Result，漏掉 A05 门禁前无 Result 的 Context 阻断。现在按 workflow ID、resume state、终止前 state version 和 Revision task type 定位当前失败任务，覆盖 Plan / Execute / Fidelity。业务或 Context BLOCKED 提供显式重新审阅；技术 FAILED 保留既有重试路径；历史任务和其他 Workflow 不影响当前入口。旧 Request、candidate、source 不被重写。
3. **模型窗口限制**：`providers/profiles.toml` 增加独立 `context_windows` 运维配置，按实际 provider/model 取窗口；不改变历史 generation profile hash。Worker 和 smoke 的 Context 预算取 Context Profile 与模型窗口的较小值，扣除 Prompt/Schema 和 output reservation，保留完整 P0，超出则以 `CONTEXT_BUDGET_EXCEEDED` 阻断。ContextPackage 记录有效预算。DefaultAdapter 在发送前再次检查完整 Prompt，覆盖旧 package 和直接调用；缺少真实模型窗口时拒绝发送。

窗口参考：[GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) 128000、[GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) 1050000；Gateway 可在配置文件中收紧。估算仍使用 UTF-8 bytes 上界，可能比精确 token 计数更早阻断，未引入 tokenizer 或新增依赖。CP-007 v4/v5、冻结 Request 和历史 ModelProfile hash 均保持原值；已有预算失败不能通过改写历史配置绕过。

新增 4 项前端回归、11 项模型窗口/配置/边界测试及 1 项数据库恢复测试。数据库测试实际执行 A05 预算阻断 → 显式重新审阅 → 新 Review → 新 RevisionRequest，确认 Provider 零调用阻断、旧 candidate/source 保留、不产生额外 Draft。

| 本轮复验 | 结果 |
| --- | --- |
| `pytest tests --ignore=tests/core -q` | **570 passed / 1 skipped**；真实 Provider opt-in 测试未执行 |
| Revision/Fidelity + Context 相关数据库集成 | **36 passed**；`test_revision_fidelity.py`、`test_revision.py`、`test_context_engine.py` |
| Frontend `npm test` | **117 passed / 8 files** |
| Mock Browser Revision E2E | **2 passed**；隔离测试库、真实 API/Worker、Mock Provider |
| Frontend lint / TypeScript / production build | **PASS** |
| `ruff check .` / `ruff format --check .` | **PASS**，328 files formatted |
| `git diff --check` | **PASS** |
| 后端增量独立复核 | 无新的 Blocking / Required |

本轮没有重跑所有数据库集成测试；第 23 节全量 pytest 为前一轮记录，不能当作本次运行结果。现有依赖的两项弃用警告仍在。未修改 migration、未重启正式 Worker、未调用真实 Provider、未提交或推送，测试代码仍保留本地。真实 Case05 依旧是第 18 节的授权事实不足 BLOCKED，本次工程修复不改变该验收结论。
