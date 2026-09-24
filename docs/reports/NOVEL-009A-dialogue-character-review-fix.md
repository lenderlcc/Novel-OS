# NOVEL-009A — Dialogue / Character Review Acceptance Fix

## 1. Background

NOVEL-009 的真实 Draft 人工验收发现：Review 能指出抽象代价、重复解释及阅读推断空间不足，但对“逻辑正确、人物交流却像执行程序”的根因区分不够具体。009A 是 A05 Narrative Review 的局部验收修正，不进入 NOVEL-010。

## 2. Case 05 Acceptance Finding

最新 Case 05 位于 Project `14c99102-f5b0-4a0f-82b6-be829fae15b5`（测试2），Chapter `23208bf8-ecc7-4054-8ae9-46cf4bc15181`，ChapterVersion `e3e88aaf-ae0b-48fe-a230-9893b79761cb` / v1。Before Review 为 `55bad299-a861-4a62-89db-f7003d310ea3`。

实际 Before：Compliance PASS，Narrative PASS_WITH_WARNINGS，Audience PASS；已有问题为 ABSTRACT_STAKES、OVER_EXPLAINED_REASONING，并保留最终方向、替代选择吸引力、动摇与选择链等 strengths。人工关注的对白程序感、人物承载立场和声音差异薄弱，尚未被充分诊断。本轮不把旧 Draft 与新 Draft 的文本区别误判为版本绑定缺陷。

**Profile 前提与实际数据不同：** 最新 Case 05 的 Project 在数据库中没有任何 Writing Profile，既有 Review binding 的 `profile_record_id/profile_version` 均为空，原始 Writing Context 也不含 Profile。`naturalness=HIGH` 等已批准 v1 偏好属于另一个 Project `23c028ee-cd94-4965-af85-731e560c9633`（测试），不能跨项目套用。后者的当前 v2 仍是未批准 Draft。因而当前 Case 05 的 Audience PASS 不能单凭这些外部偏好判为错误；有 Profile 时的关联判断用独立测试覆盖。

## 3. Scope

- 加强 OVER_STRUCTURED_DIALOGUE、CHARACTERS_AS_ARGUMENTS、WEAK_CHARACTER_VOICE 的语义判断及非触发边界。
- 明确 Character Specificity 为现有 explanation/evidence/impact 的辅助视角，不新增 taxonomy code。
- 添加结构化 Audience mismatch evidence，保持各维度独立、既有 severity/verdict 规则不变。
- 新增 Narrative Prompt/输出契约版本，兼容历史报告及排队中的 v1 任务。
- 保留现有界面，仅增加可展开的批准偏好依据。

未修改 Writer/Planning/Requirement Prompt、Draft、Plan、Context 选择策略、Workflow 定义或数据库结构。没有 Regex/词频/问号数/句长/对话轮数检测器，没有 numeric score、自动修改、A06 调用或 Revision。

## 4. Root Cause

1. 旧 Narrative task Prompt 主要枚举问题名称，缺少“信息功能 vs 互动协议”“观点差异 vs 人物差异”的诊断准则和反例。
2. 旧 Audience schema 只有 verdict 与 AUDIENCE issue/source_refs，不能结构化记录“哪个批准字段、要求什么、观察到什么、为什么冲突”。
3. 验收输入存在 Profile 混淆：最新 Case 05 在无 Profile 的新 Project 中，不能据旧项目偏好推断 Audience 漏检。

这些是 Prompt/证据契约及验收前提问题，本轮未发现必须重构的持久化或 ChapterVersion 绑定问题。

## 5. Dialogue Review Changes

Prompt 新增连续回应模式、过度完整的观点—反驳—澄清—回答链条、个人反应被压缩等语义信号。区别 FUNCTIONAL_DIALOGUE 的信息/行动传递功能与 OVER_STRUCTURED_DIALOGUE 的互动结构。正式讨论、清楚推理、适合场景的流程交流不是自动触发条件；沉默、误解、打断等只是可能信号，不是必选装饰。

多个重叠信号可以合并为一个有证据的根因，在 impact 说明声音或关系质感损失。优先少量重要诊断，常见为 2–4 个；不把数量设为硬约束，也不要求补 LOW_IMMERSION 或任何指定 code。

## 6. Character Review Changes

CHARACTERS_AS_ARGUMENTS 要有“角色主要代表抽象立场，而人格/关系/具体动机难以影响互动”的证据，分歧本身不算问题。WEAK_CHARACTER_VOICE 比较句式、节奏、回避、情绪、判断及反应习惯，不等同于口语化或话多话少。

Character Specificity 关注现有文本中的关系事实与反应：这场互动为何属于这几个人。不给缺少人物记忆的章节强加 OOC、背景故事或新 canon。正式、克制、文学化表达同样可以有不同声音。

## 7. Audience Fit Changes

`audience_evidence[]` 记录 `profile_field`、`profile_ref`、`expected`、`observed`、`reason`。每项必须对应 AUDIENCE_STYLE_MISMATCH 和顶层 source_refs 中的同一个批准 Profile 字段；字段只能来自 WritingPreferences，expected 必须与选定 APPROVED/A5 Profile 的实际字符串或完整列表一致。错版本、Draft、未选中的来源、metadata 冒充偏好、空/未指定值、伪造 expected 均拒绝。

Narrative P2 不自动生成 Audience warning。Reviewer 必须先确认与相关批准偏好的直接冲突，再生成一个合并的 Audience mismatch issue 和证据。Audience 非 PASS 必须有证据；声称 mismatch 的证据不能与 Audience PASS 并存。诊断是否成立仍属于 LLM 语义判断；代码只校验声明的一致性和来源。

## 8. Prompt Version

| 模块 | 修改前 | 修改后 |
| --- | --- | --- |
| review-chapter-narrative（现有 chapter-quality 的 Narrative 部分） | v1 | **v2** |
| review-chapter-compliance | v1 | v1，未修改 |
| quality-evidence | v2 | v2，未修改，v1 也保留 |
| chapter-quality-reviewer / chapter-review-quality | v1 | v1，未修改 |
| Writer / Planning / Requirement 模块 | 既有版本 | 未修改 |

新增 v2 manifest/hash，不覆盖 v1。正式 Prompt 只包含一般诊断原则，没有 Case 04/05 名称、原句或物件。Strength Preservation 明确要求在文本有证据时保留作者最终方向、替代选择的真实吸引力和人物自主选择。

## 9. Schema Changes

- `chapter-narrative-review.v2` / `NarrativeReviewV2` 增加 Audience evidence；原 v1 model/schema 保留，schema hash 回归固定。
- 新 aggregate 使用 `A05-quality.v2`，在原不可变 JSON body 中保存 evidence；旧 `A05-quality.v1` 继续按原契约读取。API body 接受两版，前端类型已从离线 OpenAPI 重新生成。
- 共用 Task/Prompt runtime 增加可选的输出契约选择。新 Narrative 任务使用 v2；已排队 v1 任务使用 v1 schema 和 v1 task Prompt，结果服务也按任务的固定契约解析。其他任务默认行为不变。
- 不修改 severity/category taxonomy，也不改变 `verdict_for`。没有 migration。

## 10. Tests

新增 43 个纯契约/验收输入用例、2 个数据库集成用例、2 个前端用例。重点覆盖：

1. 三类 Dialogue/Character code 的 P1/P2 impact-based contract，不固定 FAIL。
2. 包含问答/反驳/流程指令的文本不会触发确定性 issue；无问题可以 PASS。
3. 多个重叠信号可以保持为一个根因，不强制补 label。
4. Narrative warning 与 Audience PASS 可以并存；相关 Profile 冲突以证据支持 Audience warning。
5. Audience cross-field 矛盾、假 expected、错版本、Draft、metadata、缺来源均拒绝。
6. 已批准 Profile v1 被精确使用，未批准 v2 从 Context 排除；证据持久化并由 API 返回。
7. strengths 保留，Draft/approved_version 不改变，不调度 A06。
8. 排队中 v1 task 在 v2 rollout 后正常执行，历史报告不补造新字段。
9. Case 04/最新 Case 05 输入固定实际 ChapterVersion 与 hash；人类预期不注入 Context。
10. Case 05 Before 的真实 Compliance PASS、未报告 MAJOR_DIRECTION_VIOLATION 和已有 strengths 均保留。该检查不冒充新模型的 false-positive 验收。
11. UI 用中文展示偏好/观察/理由，内部 code 不进入普通展示，旧报告继续显示。
12. 不支持旧版契约的任务拒绝 null、空串及未知 Schema；支持旧版的 Narrative v1/v2 任务正常准备。

最终验证结果见第 15 节。

## 11. Case 04 Before / After

固定输入：Project `23c028ee-cd94-4965-af85-731e560c9633`，Chapter `119ae046-5b27-4b71-9ad2-eaae9518af99`，Draft v1。精确 ChapterVersion、原 Writing lineage、批准 Profile 和 hash 见本地 `evals/quality/009a/case-04/manifest.json`。

- Before：保留人工关于人物作为立场载体、对称冲突、对白功能化等结论；数据库没有该 Draft 的历史 AI 正文审阅，不能虚构 Before 模型输出。
- After Mock：相同真实输入的 Compliance、Narrative 两个 pass 均运行成功，只证明链路/Schema；不证明语义识别改善。
- After Real：等待用户显式触发。人工判断应关注是否理解人物像两种立场，而非 exact label match。

## 12. Case 05 Before / After

- Before：固定本节开头的真实报告及相同 ChapterVersion；ABSTRACT_STAKES + OVER_EXPLAINED_REASONING，保留 strengths、方向与自主选择。
- After Mock：相同真实输入的 Compliance、Narrative 两个 pass 均运行成功；不宣称对白检测或 Audience 效果已改善。
- After Real：等待用户显式触发。应判断是否识别高效逻辑协议带来的程序感，避免为了 taxonomy 覆盖增加症状。
- 无 Profile 的本次输入不应被强制判 Audience warning。如用户之后批准 Profile，这是不同的、有新来源绑定的输入，需要单独标明，不能与当前 same-input Before/After 混为一谈。

## 13. False Positive Review

Prompt 明确排除：正常意见分歧、聚焦冲突、正式/克制语体、缺少打断/沉默、说话多少、合理的局部收束。未引入任何文本规则自动生成三类 issue。已有用户方向不因 Review 偏好而改变；替代选择吸引力和真实动摇不等于方向违反。

工程负向用例只能证明代码不会自动产生误报；真实 Reviewer 对 Case 05 是否保持零 MAJOR_DIRECTION_VIOLATION 误报，仍需真实输出的人工作证。

## 14. Known Limitations

1. 未获本轮两例真实复评的显式触发前，不自动调用付费 Provider；真实效果与人工文学验收仍待完成。
2. 最新 Case 05 缺少批准 Profile；其他项目的偏好不能用作证据。
3. Case 04 缺少历史 AI 正文审阅；Before 只能引用既有人类结论。
4. Schema 可验证证据引用/值/判定一致性，不能证明 LLM 的文学判断正确。
5. 测试、eval 输入和输出按用户既有要求保留本地，不自动提交。运行中的 Backend/Worker 未在本开发任务中替换，不自动改变用户当前执行链路。

## 15. Acceptance Result

**NOVEL-009A = CONDITIONAL PASS。** 工程修正已完成，真实语义与人工验收尚未完成，不能由 Mock 代替。

| 验证项 | 结果 |
| --- | --- |
| 共享 Agent / Planning / Writing / Prompt / Quality 契约回归 | 327 passed，1 skipped（真实 Provider 未 opt-in） |
| Authority / 执行 / Prompt lineage / Quality / Writing Context 数据库集成回归 | 121 passed |
| 前端测试 | 73 passed，6 files |
| ruff check | PASS |
| ruff format --check | PASS，291 files |
| npm run lint | PASS |
| npm run build（含 vue-tsc） | PASS |
| git diff --check | PASS |
| Case 04 / 05 同输入 Mock 双 pass | PASS，仅工程契约 |
| Live DB Draft hash 再核对 | 两例均与固定输入一致，无正文修改 |
| Migration | N/A，无 ORM/数据库结构变更 |
| 独立代码复核 | PASS，发现的空 Schema 放行问题已修复并补 6 项回归 |

后端契约与集成测试共 448 项通过，前端 73 项通过。后端仅有已有 Starlette/httpx/anyio 弃用提示，不影响结果。集成测试初跑曾因测试按任务列表末项猜测 Narrative 而失败；已改为按 task_type/id 精确选择，最终整组 121 项通过，未为测试改产品查询顺序。

复现命令（backend 目录，配置文件指定隔离测试数据库）：

```sh
.venv/bin/pytest -q tests/test_agent_contracts.py tests/test_planning_contracts.py tests/test_writing_contracts.py tests/prompts tests/test_quality_contracts.py tests/test_quality_dialogue_acceptance.py --tb=short --show-capture=no
.venv/bin/pytest -q tests/core/workflow/test_agent_authority.py tests/core/workflow/test_agent_execution.py tests/core/workflow/test_prompt_lineages.py tests/core/quality tests/core/writing/test_context_and_prompt.py --tb=short --show-capture=no
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

前端执行 `npm test`、`npm run lint`、`npm run build`；仓库根目录执行 `git diff --check`。本轮没有运行全历史测试全集；覆盖范围为本次改动及共享运行链路的相关回归。

- **Engineering Acceptance：PASS**。新版本契约、精确批准 Profile 证据、历史兼容与 UI 展示通过验证。
- **AI Behavior Acceptance：PENDING**。等待用户显式触发 Case 04 / 最新 Case 05 各一次真实双 pass 复评；最多四次调用、不自动重试、不重生成正文。
- **Human Prose Evaluation：PENDING**。比较真实报告是否理解根因、保留 strengths、无方向误报，且没有以重复症状增加问题数量。Case 05 没有 Profile，不能据别的项目偏好强制 Audience warning。

现有 Backend/Worker 尚未部署或重启以加载本补丁。测试及 eval 数据保留本地，不随产品代码提交。完成后停在 NOVEL-009A，不启动 NOVEL-010。
