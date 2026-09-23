# Case 01 · Plan Review 修复与复测

日期：2026-09-16。范围：Requirement → Planning → Plan Review。Writing 暂停，未审批 Plan、未创建 Draft、未开发 NOVEL-009。

## 根因与证据

历史 Workflow：`b740882e-c39e-45a8-959b-7201e2197088`，五轮 Planning 生成 Plan v3～v7。
原始输入 SHA-256：`82490c0b11dc0722cede763d4558334b04a2f2879b12d5f845603ef84b1fb907`。

| 历史 Plan | Provider 原始 Review | 原持久化结果 | 原追加硬问题 | 新规则离线回放 |
| --- | --- | --- | --- | --- |
| v3 | PASS | FAIL | 5 × MISSING_MUST | PASS_WITH_WARNINGS / 0 hard issues |
| v4 | PASS_WITH_WARNINGS | FAIL | 5 × MISSING_MUST | PASS_WITH_WARNINGS / 0 hard issues |
| v5 | PASS | FAIL | 5 × MISSING_MUST | PASS_WITH_WARNINGS / 0 hard issues |
| v6 | PASS_WITH_WARNINGS | FAIL | 5 × MISSING_MUST | PASS_WITH_WARNINGS / 0 hard issues |
| v7 | PASS_WITH_WARNINGS | PASS_WITH_WARNINGS | 0 | PASS_WITH_WARNINGS / 0 hard issues |

四份历史失败报告全部同时包含 `covered=true` 与 `missing_requirements=[]`。
该矛盾由后端制造：`PlanningResultService.persist` 用整项字符串相等判断必需约束是否存在，
`[MUST id] 原文` / `[FORBIDDEN id] 原文` 被判成缺失；随后 `model_copy` 追加 FAIL/hard gates，
没有同步 coverage/missing IDs。Schema 只有去重校验，因而接受了非法结果。

`effective_verdict` 中 PLAN_GLOBAL 同样使用整项相等，形成第二条误判路径。
这不是四次模型真的拒绝该计划。模型原始结果与持久化结果的差异可由私有 capture 和数据库逐项复核。

返工输入原来提供整份上一轮 Review；Prompt 只说修复缺陷，没有明确区分可选建议与需求。
Plan.constraints 又允许任意字符串。因此下一轮开始把“上一轮审查修复要求”等文字作为硬约束保存，
细节持续增长。Context 的 Authority 虽然仍为 A7，但文本语义与最终存储没有足够的边界。
业务回环也没有上限，技术重试次数限制不能限制连续 Plan/Review FAIL。

## 修复设计

- `PlanReviewOutput` 使用新的 `chapter-plan-review-result.v2`：MISSING_MUST 和
  FORBIDDEN_VIOLATION 都有结构化 `constraint_id`；各自 ID 数组必须与 issue 集合相等，
  对应 coverage 必须存在且为 false；有硬证据只能 FAIL，只有建议不能 FAIL。
  Service 再校验 ID 属于真正的硬类别，FORBIDDEN_VIOLATION 只接受 Brief.forbidden。
- `PlanReviewRecord` 仅用于只读 API，保留历史非法 v1 证据可见性。执行入口始终使用严格
  `PlanReviewOutput`。没有重写历史报告，也没有把旧 FAIL 自动改成审批通过。
- `plan_review_policy.py` 集中确定性检查。服务端发现实际缺失时同时更新 issue、missing IDs、
  coverage=false，再重新验证整个结果；不再留下交叉字段矛盾。
- 约束规范化只接受原文或其准确的 `[类别 ID] 原文` 显示形式，不做模糊匹配、子串放行或案例特判。
  新 Plan.constraints 只能来自 Brief.must/forbidden/change_requests，preserved_elements 只能来自 preserve。
  附加 Review 文本、建议或自创规则会被拒绝；不静默升级成 User/System 权限。
- CP-004 v4 / CP-004R v2 显式提供有来源的 `authoritative_constraints`。
  Planning 的上一轮报告投影只含 `review_revision_targets`（硬问题）与 `recommendations`（可选建议），
  保留 A7_AI_INFERENCE；只选上一轮，不累计历史报告。旧 Context profile 原地不变。
- 最新 Prompt：`plan-chapter v4`、`review-chapter-plan v3`。
  不强制添加物件机制、固定动作、精确台词来证明覆盖；保留 over-specification 警告，
  对已可执行且满足硬边界的简单计划允许首次 PASS/PASS_WITH_WARNINGS。
- 每个 Brief / 人工规划指令最多两份自动 Plan。第二份 Review 仍 FAIL 时保存真实失败证据，
  进入 C90_BLOCKED / PLANNING_ITERATION_LIMIT，不强制 PASS，不调度第三次 Planning。
  RESUME 无法绕过。人工修正需求生成新 Brief，或通过已通过 Plan 的 Human Gate 请求修改，
  才开始新的预算。技术重试不会增加可用的业务预算。
- `planning-only` TOML scope 只允许 Requirement、Planning、Plan Review；本机与 Docker 渲染配置
  均已切换到此 scope，单任务尝试上限仍为 1。

## 真实调用期间发现的额外阻塞

全部保留原始 Task / Run / Workflow，没有修改不可变数据库记录或直接恢复终态。

1. Workflow `fba2f808-47c6-4d68-9417-d4f23115fb65`：Requirement 成功；Planning
   `MODEL_UNAVAILABLE`，没有模型输出，不能计作 Review FAIL。
2. Workflow `d916bffd-abce-43ac-81fd-853f826b6ddb`：Requirement 成功；Plan 内容及约束有效，
   但模型把 Brief 内嵌的历史 Requirement Task.source_ref 引用了出来，本轮并未选中这个源。
   原有来源守卫正确拒绝。新增 Prompt 明确顶层 Context item 与嵌套 provenance 的区别；
   新增负例证明仍然拒绝这种引用，没有放松校验。已使用的 Prompt v3/v2 保留，通过 v4/v3 发布修正。
3. 同一 Workflow 经带审计的人工 RESUME 后，Plan 正常持久化；Review 请求返回
   `MODEL_INVALID_REQUEST`，无输出。本地检查发现新的 nullable `constraint_id` 带 default，
   原 `native_schema` 没有把它加入 required，违反严格 Structured Outputs 的字段要求。
   Adapter 现在递归移除 default 元信息，并要求输出全部对象属性，保留 nullable 类型和本地
   Pydantic 校验。原本地 Schema/hash 不变，改动限于 Provider 方言转换。
   该缺陷由请求结构与协议规则确定；没有保存网关的原始错误正文，不把推断写成网关原文。
   依据：[Structured Outputs 官方文档](https://developers.openai.com/api/docs/guides/structured-outputs#all-fields-must-be-required)。
4. Workflow `81f040f7-b933-4340-bc60-c33dcd84105d`：协议修复后 Requirement 成功，Planning
   返回 `MODEL_RATE_LIMIT`。停止调用并完成其他回归，间隔数分钟后做最后一轮有上限的复测。

## 真实同文复测结果

**PASS：相同原文，真实模型 1 次 Planning 后达到 PASS_WITH_WARNINGS；此前为 5 次。**

- 时间：2026-09-16 10:36:54～10:38:08（Asia/Shanghai）。
- Model：`lingzhi / gpt-5.6-sol`，Profile：`lingzhi-structured`。
- 原项目/章节的名称、描述、标签、metadata、序号和标题复制到隔离复测项目；原始输入逐字一致，
  上述 SHA-256 已重新核对。旧 Workflow 与五份 Review 全部保留，没有覆盖旧结果。
- Project：`0767f00f-1d3a-4e82-a779-17e78d4f2888`；Chapter：`ee59f19c-7815-4e91-99ca-619a10ebd311`。
- 最终 Workflow：`cc7a88d3-087d-4da6-a540-9a0463eddf46`。
- 三个任务各调用一次、各自成功，无技术重试；`planning_iteration_count=1`。
- 本 Workflow 只生成一份 Plan，版本号为 v2，因为隔离章节此前调试保留了 Plan v1。
  版本号与本次业务迭代数分开统计。
- Brief：3 MUST、2 FORBIDDEN、1 SHOULD、1 PREFERENCE；Plan.constraints 恰好是五条硬需求的原文。
  没有 Review 文本、自创要求或可选偏好混入 constraints。
- Review：7 条 coverage 全部 true，`hard_gate_issues=[]`、`missing_requirements=[]`、
  `forbidden_violations=[]`、`over_specification_issues=[]`。
- Provider 原始 verdict 为 PASS；保留的一个 LOW logic risk 和两条 recommendation 使确定性策略
  输出 PASS_WITH_WARNINGS。除 verdict 外，原始 Review 与持久化 body 完全一致；没有追加硬问题。
  建议明确不需增加固定台词、动作或场景装置，也没有触发新一轮 Planning。
- 状态：`C06_PLAN_APPROVAL / WAITING_HUMAN`，`approved_plan_version=null`；
  `current_version=null`、`approved_version=null`；Writing task 数量为 0。

| 阶段 | AgentTask | AgentRun | PromptLineage | ContextPackage |
| --- | --- | --- | --- | --- |
| Requirement | 26b9e56a-b200-4adb-a1bb-64b7e796133d | 450d6158-3904-4716-bd4c-c415ea9ab05f | d9130069-f4e7-4fd9-b068-85559d0ca206 | 3a527e52-fa92-4e9e-8ecd-be8b509bb389 |
| Planning | 1535336c-f7ef-418d-b2aa-7d0b7fe76827 | 01a33b1d-fb55-4045-88b8-4c723a25b2dc | ae4f66e2-2962-4ac0-8c78-5415b636a444 | cb821f67-ed9f-4b95-be83-54b104f3eeb3 |
| Review | c9f23673-f8a1-4886-ae85-acadd6e09ef1 | efa69af4-22a4-4380-95da-ae8d3ca0dd10 | 31b4081c-9639-4a56-9853-499859b5b35a | 3fbf4bf7-5230-413c-b138-ea4be1207713 |

最终复测使用 parse-chapter-requirement v2 / plan-chapter v4 / review-chapter-plan v3，
Review 输出 Schema v2。Task、Run、Lineage、模型快照的绑定已核对。
Plan ID：`f784571b-928c-4fd3-afcd-af4cce90a441`；Review ID：`5661353f-a939-4e79-89a5-97ef5abf2955`。

**调用总量与迭代数不是同一指标：**本次诊断及四次 Workflow 复测合计 11 次真实 Provider 尝试：
Requirement 4、Planning 5、Review 2，其中包括前述网关错误和来源拒绝。
最终成功 Workflow 是 3 次调用、1 次 Planning。没有通过隐瞒失败调用来计算“5 → 1”。
API 计费以网关记录为准，不假定失败请求不收费。

本机私有证据：`backend/.runtime/plan-review-acceptance/baseline.json`、
`final-attempt.json` 及对应 `backend/.runtime/agent-output/` capture；不包含 credential，未加入 Git。

## 自动验证

| 验证 | 结果 |
| --- | --- |
| `uv run --locked pytest -q` | **866 passed, 4 skipped**, 634.50 秒；4 个跳过项均为显式 opt-in 的付费调用 |
| `uv run --locked ruff check` | PASS |
| `uv run --locked ruff format --check` | PASS，243 files already formatted |
| `npm test` | **41 passed**，4 test files |
| `npm run lint` | PASS |
| `npm run build` | PASS，包含 vue-tsc 类型检查 |
| `git diff --check` | PASS |
| `/api/v1/health`、`/api/v1/health/db` | HTTP 200，status=ok，database=ok |
| 原始 Workflow planning history API | HTTP 200，五份历史 Review 完整可读 |
| 浏览器回归 | 原始 Plan v3 的 FAIL/5×MISSING_MUST 正常显示；新结果可读；Writing 暂停文案正确 |
| 历史原始 Review 离线回放 | 五份均无硬问题；四次错误 FAIL 不再重现 |
| 最终真实同文端到端 | PASS_WITH_WARNINGS；1 次 Planning；0 Writing task |

全量日志：`/tmp/novel-review-verified-suite.log`，真实调用日志：
`/tmp/novel-review-final-attempt.log`。两条 pytest warning 来自现有 Starlette TestClient
对 httpx 与 anyio BlockingPortal 旧接口的弃用提示，不影响测试结果。
付费自动测试没有批量启用；真实调用由上面的限次脚本执行，避免 Writing smoke 误触发。

前端、Host API 与 `planning-only` Worker 保持启动，便于人工查看结果。
恢复 Worker 前再次确认全库 unfinished_tasks=[]，不会补跑历史任务；不会领取 WRITE_CHAPTER。

新增与更新的回归覆盖：

- 缺失 issue / missing ID / coverage 矛盾、无 ID、错误 ID、PASS 与硬失败矛盾。
- FORBIDDEN 引用非禁止类别、无引用禁止项、建议伪装成禁止项。
- 真实带标签约束可通过；SCENE/PLAN_GLOBAL 均覆盖；CHANGE_REQUEST 分类保持单数枚举。
- 服务端追加真实缺失时所有字段一致；真正缺失不会放行。
- Review 建议/自创硬约束不能持久化；上一轮反馈不会累积进下一轮 constraints。
- 一轮通过；两轮修复后带警告通过；第二轮仍失败阻断第三轮；RESUME 无法扩大预算。
- 人工修改/新 Brief 可以开启新预算，旧 Plan/Review 保留。
- 历史 v1 非法报告可读，但不能作为新结果接受。
- 嵌套历史 provenance 不能作为当前选中 Context 引用。
- 四个正式任务的 Provider schema 全部对象字段 required，nullable 保留，本地 Schema 不被修改。
- 旧 Prompt hash 保持；新 Prompt/schema/profile 正确选择；planning-only 不包含 Writing。

## 文件与架构

主要改动：`agents/planning_schemas.py`、`agents/registry.py`、`api/planning_schemas.py`、
`services/planning_results.py`、新增 `services/plan_review_policy.py` / `planning_budget.py`、
`services/planning_context.py`、`repositories/planning.py`、`workflow/guards.py` / `runtime.py`、
`prompts/tasks.py`、新增 Context/Prompt 版本、`providers/openai.py`、`core/config.py`、
配置示例/README、相关测试和前端自动生成 API 类型。
前端仅同步执行范围文案：planning-only 明确显示 Writing 暂停，停用任务提示其实际类型。

API → Service → Repository → Database 边界不变。未增加表、migration、依赖或业务 Agent。
Repository 只查询/flush，不 commit；预算与 artifact/event 更新在原 Service transaction 内执行。
新旧 Context package 的 profile/version/hash 仍固定；approved/current 选择规则不变。
独立复核按 code-review-and-quality 执行，发现的来源/类别/历史读取风险均处理。

## 限制与部署条件

- Schema v2 发布前必须停止 Worker、排空或审计处理旧 v1 unfinished tasks。
  不能修改其不可变 expected_output_schema；本机发布前已查询确认 unfinished_tasks=[]。
- 本次只验证一条真实 Case 01，不能由此声称所有题材都必定在两轮内获得高质量计划。
  两轮是自动执行上限，真实硬问题仍会停止等待人工，而非被忽略。
- 模型仍可能产生合法结构下的语义误判。规则保证可检验的一致性、Authority 和预算边界，
  不替代人工判断。此次不评价最终文笔。
- 网关曾返回 MODEL_UNAVAILABLE / MODEL_RATE_LIMIT；保持不自动重试。
  调试调用次数与业务迭代数分别报告；最终限次复测已成功。
- 无生产 migration 操作；全量测试包含隔离测试数据库中的 migration 回归。未重建 Docker 镜像。
- 未提交或推送本次改动，等待 Review。

## 验收结论

- **Engineering Acceptance：PASS。** 结构矛盾被拒绝、硬约束来源校验、反馈分层、两轮预算、
  历史只读兼容与负向回归均通过；未增加 Case 01 特判。
- **Case 01 AI Behavior Acceptance：PASS_WITH_WARNINGS。** 同一原文的最终真实运行从历史
  五次 Planning 降为一次，保留轻风险/可选建议并停止返工。只代表本次样本结果。
- **Human Prose Evaluation：未执行。** 未开始 Writing，未人工批准 Plan，等待用户检查方案与 Review。
