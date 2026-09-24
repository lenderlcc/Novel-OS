# NOVEL-009 — Chapter Quality Review Engine

日期：2026-09-24。开发基线：`main` / `origin/main` 的 `032da3c`；开发分支：`wfg/novel-009-quality-engine`。

用户要求先合并此前工作：已将 NOVEL-001～008、内部工作台、UX-001、STYLE-001/002 的此前产品改动合并并推送到 main。009 在该基线上开发。保留此前本地测试改动；遵守“测试代码不要提交”，本次没有提交测试或自动合并 009。

## 1. Background

Requirement/Plan 合规不代表正文好读。009 增加可追溯的正文诊断，分别报告硬约束、叙事质量和受众匹配；不修改正文、不改变批准版本、不触发自动重写。实现以本次用户补充指令为准，覆盖旧票据中的多轮设计差异。

## 2. Findings From Manual Cases 01–05

以下是用户提供的人工观察，**不是本次模型运行的结果**：

| Case | 设计依据 | 评估边界 |
| --- | --- | --- |
| 01 | 文风、节奏、描写与批准的受众偏好不匹配 | 只依据对应版本的 Profile，不把“网文”变成固定模板 |
| 02 | 推理正确但代入弱、立即解释证据、叙事重点分配失衡 | 必须引用实际文字并说明阅读影响 |
| 03 | 叙述视角不符、动作过程过细、安全而普通的选择 | 对白中的第一人称不等于第一人称叙述；重复安全选择需要多章证据 |
| 04 | 人物像观点载体、冲突过于对称、对白功能化 | 双方立场合理、几句问答本身不能触发问题 |
| 05 | 用户最终方向得到保留，但对话像论证程序、代价抽象、解释过多 | 同时保留 Human Sovereignty 优点和叙事问题，不要求改写最终方向 |

## 3. Scope

新增质量领域枚举/事实、两个 A05 任务、结构化结果与证据校验、版本绑定、持久化、工作流接入、正文审阅 UI、人工评价对照、历史评估入口和文档。无新依赖。

未新增 Agent/调度器/Workflow Engine；未实现 Revision、自动润色、Memory Commit、训练、向量检索、评分仪表盘或 NOVEL-010。Writer 的提示词、生成策略未修改。

## 4. Quality Architecture

API → Service → Repository → PostgreSQL。`domain/quality.py` 不依赖 FastAPI/ORM；`quality/schemas.py` 与 `quality/policy.py` 管理结构契约和证据关系。`QualityBindingService` 冻结审阅依据；`QualityResultService` 校验并持久化；Repository 只 add/flush/query，不 commit。

继续使用既有 AgentRuntime、Provider、PromptLineage、ContextPackage、TaskScheduler、lease/heartbeat/retry 与事务锁顺序。模型判断语义，确定性系统验证结构、来源、版本与权限。

## 5. Hard Compliance

已确认的 LOCKED_CONFLICT / MAJOR_DIRECTION_VIOLATION 必须 P0 且要求修改；MISSING_MUST / FORBIDDEN_VIOLATION / CANON_CONFLICT / CHARACTER_KNOWLEDGE_LEAK 必须 P0/P1 且要求修改，不能降为 P2/P3 建议后放行。

MUST/FORBIDDEN 引用对应 CreativeBrief 的精确条目，或已选入上下文的正式 Requirement 的 content 字段；后者必须类型匹配，并满足 APPROVED/A2 或 LOCKED/A1 的状态与权威组合。SHOULD/PREFERENCE 不因批准而成为硬约束。Locked 要求真正的 A1 锁；Canon 要求提供的已批准/锁定事实；角色知识泄漏要求明确的角色知识证据。无证据时不允许构造冲突。A5 视角偏好不能成为 P0。

## 6. Narrative Quality

支持代入、视角锚点、细节取舍、解释过度、对白功能化/结构化、人物声音、观点载体、冲突对称、抽象代价、过度收束和需求痕迹等语义诊断。没有关键词、句长比例、代词计数等文学判定规则。

严重叙事问题可为要求修改的 P1；普通问题是警告/建议。允许有优点、有局部不足的章节通过；不按问题数量计算分数。

## 7. Audience / Writing Profile Fit

只取 approved ProjectWritingProfile 的 record ID、version、hash，保留 A5_USER_PREFERENCE。当前未批准的 Profile 不进入模型上下文。未设置的偏好不是禁令。

冻结“无批准 Profile”这一状态；排队或两轮之间首次批准 Profile 也会令审阅过期。受众诊断仍由模型根据具体偏好和正文判断。

## 8. Quality Taxonomy v1

24 个稳定 code，归入 COMPLIANCE / NARRATIVE / CREATIVE / AUDIENCE。详见 `docs/specs/Quality-Taxonomy-v1.md`，包含定义、典型 severity、证据要求与 Non-trigger。

SAFE_GENERIC_CREATIVE_CHOICE 必须有至少两章先前证据；它与 LOW_CREATIVE_NOVELTY 只能 P2/P3，不能因偏好新奇而否定批准主线。Taxonomy 是词汇表，不是要求逐项报错的清单。

## 9. Issue Schema

每条问题包括 code、severity、category、title、description、evidence、source_refs、impact、revision_direction、confidence、requires_revision。Evidence 为 1-based paragraph_index、最多 280 字符的原文片段和 reason。

禁止未知字段、非法 code/severity、缺失证据、错误 category、无依据的升权及非法严重级别。所有级别都要求证据；不接受正文重写字段、numeric score 或模型伪造批准。

## 10. Review Result Schema

最终 ChapterReviewResult 包含 exact chapter_id/chapter_version_id、overall/compliance/narrative/audience verdict、hard_gate_issues、quality_issues、strengths、revision_priorities、source_refs、confidence、reviewer_version、created_at 及两轮 Context/Prompt ID。

Pass 与 aggregate 均执行 cross-field invariant：问题种类属于对应轮次；verdict 与有效 issues 一致；revision priority 引用真实 issue；同一 code 合并证据。API DTO 不直接使用 ORM。

## 11. A05 Review Integration

复用 A05_REVIEW，只增加 REVIEW_CHAPTER_COMPLIANCE 和 REVIEW_CHAPTER_NARRATIVE 两个 task type。允许 REVIEW 能力，不允许提出 Draft/Plan/Canon/Profile mutation、Memory Proposal 或审批。

默认 Mock 可离线完整运行。新增显式执行范围 `chapter-quality`；现有 `chapter-writing` 范围不自动增加付费审阅权限。

## 12. Compliance Pass

第一轮读取 exact Draft、CreativeBrief、approved Plan、有效约束、已提供的权威事实与 approved A5 Profile。结果成功保存后，同一 C09 state_version 调度第二轮，不切换状态，不产生第三次聚合模型调用。

硬问题与技术异常区分：有效的 FAIL 是成功的业务审阅结果；Provider/结构异常才进入既有错误与重试路径。

## 13. Narrative/Audience Pass

第二轮独立读取同一冻结依据，审阅叙事、创意建议和受众效果。第一轮的批评不加入第二轮权威约束；避免 Reviewer 文本被累积成硬要求。

两轮并非投票或辩论。第二轮不能输出合规类问题绕过第一轮的来源校验。

## 14. Deterministic Aggregation

P0 或 requires_revision=true 的 P1 → FAIL；其他有效问题 → PASS_WITH_WARNINGS；无问题 → PASS。各维度独立保留。confidence 取两轮较低值，不是正文评分。

合并 source_refs、优点和修改优先级；完全相同的优点去重；优点与优先级各最多保留 10 条。没有分数、权重、阈值拟合或第三次模型调用。

## 15. Evidence Model

段落按空行确定；引用必须逐字存在于指定段落，不能复制整章。缺失项问题也需要相关段落及“为什么这段不能满足要求”的解释，不伪造缺失文字。

引用只允许当前 ContextPackage 已选择的 source_type/source_id/source_version；每条问题的引用必须在 pass 顶层引用中出现。字段级校验用于 MUST/FORBIDDEN/Profile。该校验能保证来源身份，不能替代人工判断理由是否合理。

## 16. Strength Preservation

Strength 也需要原文证据，并包含 preservation_direction。UI 显示“值得保留”；模型被明确要求保留有效选择、已实现方向和场景优点，不把全面重写当成默认建议。

Mock 优点明确标注契约样例，不冒充真实文学判断。

## 17. Revision Priority

RevisionPriority 只引用已经报告的 issue_code，提供 direction 与 preserve。不得新增用户约束、改写片段或直接修改任何业务对象。优先级是建议，等待人工或后续 NOVEL-010 消费。

## 18. Workflow Integration

新增不可变 `chapter-planning.v3`，保留 Requirement → Planning → Plan Review → 人工审批 → Writing。Writing 已验证后 C08 → C09；同一轮最多两次业务审阅调用。最终 PASS/WARN → C11_INTERNAL_PASS，FAIL → C10_REVISION，两者 WAITING_HUMAN。

不调度 A06。显式用户 REQUEST_REVIEW 可从 C10/C11 或暂停/受阻的审阅再审一次，要求 expected_state_version、expected_draft_version 和 event_id；可绑定用户明确指定的 current Draft。Review RESUME 同样接收可选 Draft token，未携带时只允许原绑定版本仍为 current。重复提交幂等；结果追加历史，新 binding 重新运行两轮，不复用旧 pass。

旧 v1/v2 定义和运行中实例不修改。既有数据库禁止原地变更 Workflow definition version；因此历史章节通过独立 read-only eval 评估，不强行迁移到 v3。

## 19. Context Integration

新增 CP-006 v3，仅绑定两个新审阅任务；旧 CP-006 v1/v2 保留。P0 选 exact Draft、workflow approved Plan、Brief、已批准/锁定 Requirement/Decision、声明的锁定依赖和 approved Profile。

可选 P1 取至多三章先前 approved 正文，按章节序号限定范围，绝不取 current Draft 或未来章。超预算按既有 Context Engine 策略处理，不能静默截去必需 P0。缺失 Canon/Character Memory 不补造领域或数据库。

## 20. Prompt Versions

| 类型 | Module | Version |
| --- | --- | --- |
| AGENT_ROLE | chapter-quality-reviewer | 1 |
| TASK_TEMPLATE | review-chapter-compliance | 1 |
| TASK_TEMPLATE | review-chapter-narrative | 1 |
| SKILL | quality-evidence | 2（v1 原样保留） |
| QUALITY_PROFILE | chapter-review-quality | 1 |

模块有内容 hash，使用已有 compiler/registry/PromptLineage。Prompt 说明无证据不报错、区分权威与偏好、观点合理不等于对话自然、对白中的“我”不等于视角违反。无 Case 01～05 特定物品/情节关键词；人工标签不进 Prompt。

## 21. Persistence / Versioning

迁移 `0011_quality_review` 增加 quality_review_bindings、quality_review_passes、chapter_quality_reviews 三张表。问题/优点随不可变 JSON 结果保存，没有额外可变评分表。

Binding 记录 exact Draft/Plan/Brief/Profile 和来源指纹；pass 记录 task/run/context/prompt；aggregate 记录两个 pass ID 和章节内 review version。数据库 FK、唯一性与关系触发器验证跨对象绑定，UPDATE/DELETE 触发器保护全部新证据。

事务由既有 application service 控制，沿用 Project → Workflow → Task 锁顺序。Pass、Audit、task 状态、下一任务或状态转换一起提交；失败整体回滚。重复并发投递只产生一份 pass/下一任务/结果。

未修改历史 migration 文件；0011 局部替换旧 Writing relation guard 以允许 v3，downgrade 恢复原 guard。

## 22. Freshness

调度时冻结同一个 binding；调用前、结果写入前、两轮之间均重新核对来源。Draft、approved Plan、Brief、approved Profile 或引用依据变化 → CONTEXT_STALE，不把旧结果挂到 latest。

历史 GET 动态验证完整来源指纹并标为 STALE，原结果不修改。创建新 Draft 后旧 review 仍可查询、不能误标为当前评价。

Review 指纹忽略 Chapter 的通用版本号/更新时间等记账字段，因此新增未批准 Plan 不影响对原批准 Plan 的审阅。正文、批准 Plan、Chapter 实际输入、状态与权限仍受校验。正文更新后可由用户携带最新版本 token 恢复；批准 Plan/Brief 变化仍先进入原 intake/replanning 恢复路径。

## 23. UI

新增四步进度：需求 → 方案 → 正文 → 审阅。正文可在审阅过程中阅读；结果使用“通过 / 有改进空间 / 建议修改”，分开展示约束、叙事、受众。

普通视图显示简洁问题、可展开的短引用/影响/修改方向和优点。Code、severity、confidence、段落索引、版本绑定、raw JSON、Context/Prompt 放在 Debug。无评分、自动修复或重写按钮。

旧章节没有 review 也能阅读、评价。已完成真实浏览器 Mock 流程并检查截图；修复四步进度仍按三列布局导致换行的问题。

API 新增：POST `/api/v1/workflows/chapter-quality`，GET `/api/v1/projects/{project_id}/chapters/{chapter_id}/quality-reviews`，POST `/api/v1/workflows/{workflow_id}/quality-review`。OpenAPI TypeScript 类型由当前 schema 重新生成。

## 24. Manual Human Evaluation Integration

保留原有人工评价导出流程。Debug 可以在本页读取 `ux-001.v1` JSON，对照 AI codes 与 human tags/notes；核对 Project、Chapter、Workflow、Draft version 后才显示。

文件有类型/大小边界；切换 review 清空对照。新增测试验证匹配版本的主题对照、拒绝其他 Draft 的评价、拒绝超大文件，以及 HTML 笔记作为纯文本显示。导入不写数据库、不覆盖人工评价、不更改 AI 结果。主题可比较，不以标签完全一致作为合格标准。

## 25. Case 01–05 Eval Harness

`evals/quality/run.py` 提供历史输入导出和离线/显式 real 评估。导出使用 READ ONLY 数据库事务，读取对应 WritingGeneration 原始 ContextPackage/Brief/Profile，不能用今天的 current/approved Profile 替换历史依据。

默认 Mock，不消耗 API。`--real` 是单次人工 opt-in，要求真实 ModelProfile；最多两次调用、失败停止、无自动重试。输出不可覆盖已有目录。expected themes 在两个模型调用之后才读取，仅用于对照文件。

五个案例目录有 source-case 与 expected-themes；未捏造历史快照或已执行结果。文件 lineage 的 UUID 是离线评估标识，明确区别于 runtime 数据库记录。使用方式见 `evals/quality/README.md`。

## 26. Test Results

初次实现验证（本轮 Review 修复前）：前端 65 项单元/组件测试、lint、build、typecheck 通过；Playwright 完整 Mock 流程 1 项通过。质量聚焦集合 105 项通过，其中 79 项 schema/policy 契约用例。ruff check、ruff format --check、git diff --check 通过。**backend full pytest：1044 passed、4 skipped、2 warnings，711.41 秒，进程退出码 0。** 四项 skipped 为显式付费 opt-in 测试；两个 warnings 为既有依赖弃用提示。新增测试覆盖 taxonomy/schema、hard/soft invariants、引用身份与段落、权威证据、角色知识隔离、approved/current Profile、stale、rollback、DB immutability、Repository 不 commit、重复并发投递、两轮上限、FAIL 不启动 Revision、独立人工对照和浏览器完整流程。本轮修复后的验证另见下文。

首次全量运行 934 passed / 7 failed / 4 skipped。7 个失败来自旧 migration head/Context 最新版本断言，以及旧 migration schema 上试图查询新增质量表的测试；已修改历史测试的版本范围，保留旧数据快照一致性检查。修正后的针对性集合 105 passed。后续全量运行发现新增的“两轮之间 Profile 变化”测试使用列表末项定位第二轮，受同状态版本任务 UUID 排序影响；已按 REVIEW_CHAPTER_NARRATIVE 身份定位，单项复测通过并重新启动完整回归。

验证命令（均在对应工程目录执行）：

```sh
# backend
.venv/bin/pytest -q --tb=short
.venv/bin/ruff check .
.venv/bin/ruff format --check .
# frontend
npm test
npm run lint
npm run build
npm run typecheck
npm run test:e2e -- e2e/quality.spec.ts
# repository
git diff --check
docker build -t novel-os-quality-acceptance backend
```

Migration 同时通过 Alembic command API 集成测试和实际 Alembic CLI，在独立 test schema 中执行 `upgrade head`、`downgrade -1`、`upgrade head`、`check`，四步均通过。CLI 使用临时目录内的私有 TOML 配置，结束后删除配置和 schema，不读取环境变量。真实 Provider 的 opt-in 开关未开启。

## 27. Real Provider Results

**NOT RUN；真实 API 调用 0 次。** 本次没有新的付费质量审阅授权，因此没有对 Case 01～05 自动调用真实 Provider。四个既有 live tests 按其显式 opt-in 要求跳过。

Mock 验证仅说明契约、权限、事务和链路正确；不能证明 Reviewer 能稳定识别真实文学问题。该项等待人工授权后的案例评估。

## 28. Docker / Migration Verification

隔离 test schema 中执行 upgrade head → downgrade -1 → upgrade head → alembic check，全部通过；head 为 0011_quality_review，downgrade 为 0010_project_writing_profile；无 metadata drift。

Docker 镜像 `novel-os-quality-acceptance` 构建并启动。容器内 GET `/api/v1/health` 返回 `{"status":"ok"}`；`/api/v1/health/db` 返回 `{"status":"ok","database":"ok"}`。

验证使用独立 Mock 容器和测试数据库 schema，完成后清理。首次宿主机临时路径挂载未被 Colima 识别，后改为 docker cp 配置并在同 Docker network 连测试 PostgreSQL。容器内探活通过；不将宿主机端口转发作为本次产品代码结论。未改现有 paid Worker 或开发数据库。downgrade 会删除本迁移新增的 review 证据表，因此本次只在隔离 schema 中验证，没有对用户数据做回滚。

## 29. Independent Review Findings

依据 code-review-and-quality skill，使用不同模型进行只读独立审查并复核。

- Required：模型可把已确认硬冲突降为 P2/P3/不要求修改，导致 WARN→C11。已对 Locked/Major Direction 强制 P0，对 MUST/FORBIDDEN/Canon/Character Knowledge 强制 P0/P1 且要求修改；同步 Prompt 和负向测试。
- 复核确认：人工 expected themes 不进入 Prompt/Context，历史 eval 不写 runtime review 表；freshness、历史保留、显式重审和并发重复投递路径有测试。
- 最终复核：两个 Required 均已闭环，独立 reviewer 运行 79 项契约测试通过，没有未解决 Required。
- 文学语义仍由模型判断；补丁仅约束模型声称存在的已证实冲突，不新增自动文本判定。

## 30. Known Limitations

1. 尚无真实 Provider 的质量效果数据；不能给 AI Behavior 或 Human Prose Evaluation 宣布 PASS。
2. 009 未引入 Character/Event/Canon Memory。缺少角色知识证据时无法做有根据的知识泄漏断言；这是明确的能力边界。
3. 历史 Writing context 通常只有一个前章；离线 eval 不为“多章重复”补造证据。新运行最多看三个已批准前章，预算不足可省略 P1。
4. 旧 v1/v2 工作流保持原样；不支持把运行中旧实例改成 v3。历史 Draft 使用 read-only eval。
5. 人工评价对照在本地页面，尚无独立人工评价持久化服务/统计系统。
6. 本机真实 Worker 配置没有自动改为 `chapter-quality`，没有静默增加 API 消费。新代码部署后，真实审阅需用户明确开启该配置范围并启动更新后的 Worker；若范围仍为 `chapter-writing`，C09 会显示执行范围未开放。
7. 既有 Starlette/httpx 与 AnyIO deprecation warnings 仍存在，非本次引入。

## 31. Deferred to NOVEL-010

Revision proposal、人工选择修订方向、生成新 Draft、优点保留的修订执行及新版本再审均留待后续。未修改 Writing Prompt，未实现 Auto Fix/Humanizer/learning/训练/模型投票。

## 32. Acceptance Result

**Engineering Acceptance = PASS。NOVEL-009 综合结果 = CONDITIONAL PASS**：工程实现和全量回归通过，真实模型质量效果及人工文学验收尚未运行。

工程验收矩阵：

| 维度 | 结论 | 证据 |
| --- | --- | --- |
| Hard / Soft、Schema、Authority、Evidence | PASS | 79 项独立复核契约测试 |
| 两轮工作流、只读审阅、版本/事务/并发 | PASS | 26 项集成用例及浏览器流程 |
| UI 与独立人工评价 | PASS | 65 项前端测试、完整 Mock 浏览器流程 |
| Lint / Build / Typecheck | PASS | ruff、eslint、vue-tsc、vite、diff check |
| Docker / Migration | PASS | 新镜像探活、隔离 schema 升降级、metadata check |
| NOVEL-001～009 全量工程回归 | PASS | 1044 passed / 4 opt-in skipped，退出码 0 |
| AI Behavior Acceptance | NOT RUN | 未授权付费质量审阅 |
| Human Prose Evaluation | PENDING | 需要人工对照真实 Case 输出 |

没有未解决的 Blocking / Required 工程问题。进入真实质量效果验收前，需要用户显式授权选定历史 Draft 的两轮 Provider 调用，并逐项比对 AI 证据、人工主题与误报。此条件不通过 Mock 测试代替。本次完成后停在 009，等待 Review；不启动 NOVEL-010。

## 33. Review 修复：正式约束、版本隔离与显式恢复

本轮先复现三个根因，再作局部修复，没有改变数据库结构或旧 Workflow 定义：

| 问题 | 根因 | 修复与验证重点 |
| --- | --- | --- |
| 正式 Requirement 报告被当作解析错误 | MUST/FORBIDDEN 校验只接受 Brief 条目 | 允许精确的正式 Requirement content 引用；类型、状态/Authority 配对、版本全部校验。合法 FAIL 正常落库，不进入技术重试；soft、过期及错配引用拒绝 |
| 未批准 Plan 使 Review 过期 | Chapter 通用 version/updated_at 被纳入审阅指纹 | 排除纯记账字段，保留实际输入与权限；在排队、两轮之间、报告完成后创建未批准 Plan 均不误报 stale，真正批准 Plan/正文/标题变化仍失效 |
| 正文更新后无法恢复/复审 | 旧 draft_current guard 先拒绝新正文，RESUME 又沿用旧 draft_version | 用户携带当前 Draft token，在同一事务创建新 C09 binding 与新两轮；旧 pass/report 不改。覆盖 stale token、并发、幂等、回滚、锁、旧 C08 block 恢复及 v2 Writing handoff 隔离 |

前端重试按钮显示“重新审阅正文 vN”，提交已加载快照中的版本；冲突时等待用户刷新，不自动重试付费调用。Review 阶段可显示显式绑定的人工 Draft，不要求它具有 WritingGeneration，也不伪造 Writing lineage；旧 Writing 阶段保留原校验。新增 `quality-evidence.v2`，v1 内容和 hash 保留。OpenAPI TypeScript 类型已重新生成。

新增 34 个后端回归案例、6 个前端案例；均保留在本地，未提交或推送。独立复核检查了权限、锁、旧 Writing 兼容、事务回滚与不可变证据，并补充状态/Authority 错配的负向测试。

本轮最终验证（与第 26、32 节的初始实现全量结果分开记录）：

| 检查 | 结果 |
| --- | --- |
| 最终修复专项：quality contracts、recovery、formal Requirement source | **113 passed** |
| 旧 Workflow 路径、guards、安全、并发、历史恢复兼容性 | **61 passed** |
| 扩展 Quality / Writing / Prompt 回归 | **298 passed / 1 opt-in skipped**；与专项有重叠，不累加为独立用例数 |
| Quality migration roundtrip / metadata | 上述扩展回归包含 upgrade → downgrade -1 → upgrade → check，通过 |
| 前端 | **71 passed**；eslint、vue-tsc、vite build 通过 |
| 后端静态检查 | `ruff check`、`ruff format --check` 通过，288 files already formatted |
| Diff | `git diff --check` 通过 |

扩展回归首次混合指定目录/文件时，旧 Workflow 的 61 项在 setup 阶段报父目录 `core_settings` fixture 未加载，未进入业务代码。调整参数顺序的 `--setup-plan` 验证通过；将这 61 项单独补跑，全部通过。最后在最终代码上重跑 113 项修复专项，全部通过。未把首次失败运行描述为整套通过，也未将本轮局部回归描述为重新执行 1044 项全量测试。

本轮无真实 Provider 调用，没有重启或更改 paid Worker，没有调整数据库结构，没有新增依赖；Docker 探活沿用初始实现记录，本轮未重跑。现存 Starlette/httpx、AnyIO deprecation warnings 保留。三个 Review 问题均已修复，等待用户 Review。
