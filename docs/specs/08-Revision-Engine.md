# Targeted Revision Engine — NOVEL-010 / 010A

本规范落实 2026-09-24 的 NOVEL-010 补充需求，取代旧 ticket 中多种 Revision Mode、自动循环及数值质量指标的设想。Formal Revision 属于现有 `chapter-planning.v3`；旧 v1/v2 工作流保持原行为。

## 用户控制与状态

用户在当前有效 Review 为 FAIL / PASS_WITH_WARNINGS 时明确点击“根据审阅修改”。PASS 不提供主修改按钮。请求必须带 event_id、expected_state_version、source_review_id、expected_draft_version。普通 Review 完成不会自动启动 A06。

```text
C10/C11 WAITING_HUMAN
  -- USER REQUEST_REVISION --> C10 WAITING_AGENT (A06 PLAN_CHAPTER_REVISION)
  -- AGENT REVISION_PLAN_READY --> C10 WAITING_AGENT (A06 REVISE_CHAPTER)
  -- AGENT REVISION_CANDIDATE_READY --> C10 WAITING_AGENT (A05 VALIDATE_REVISION_FIDELITY)
  -- fidelity PASS / AGENT REVISION_READY --> immutable successor → C08 → C09
  -- fidelity FAIL --> C90 BLOCKED，原稿保持 current，STOP
  -- INTERNAL_REVIEW_PASSED/FAILED --> C11/C10 WAITING_HUMAN, STOP
```

每个用户 request 至多一个 plan、一个 candidate、一个 result，至多一个 successor Draft。Review v2 FAIL 也停止；需要用户基于新 Review 再次明确请求才可改下一版。revision_count 在用户请求时增加，不把技术重试或审阅 FAIL 计为新修改。特殊事件由 deterministic WorkflowRuntime 验证和处理，Agent 不能指定状态、事件或 next_state。

## 两阶段契约

A06 同时拥有 PLAN_CHAPTER_REVISION 和 REVISE_CHAPTER，不增加 Agent。

`RevisionPlanOutput`：source Draft/Review/chapter、target_issue_ids、preserve_items、revision_targets、do_not_change、revision_strategy、scope、blocked_reasons、source_refs、confidence。scope 默认为 TARGETED，仅另支持 FULL_PASS。每个问题必须分配到 safe target 或 blocked reason，不能遗漏、重复或偷偷替换问题。

`RevisionResultOutput`：source Draft/Review、revision_plan_id、content（安全阻塞时可为 null）、addressed/unresolved_issue_ids、preserved_items、declared_changes、blocked_reasons、source_refs、confidence。addressed 仅是 A06 自述，后续 A05 独立判断是否改善。

唯一输出 Schema 是 Pydantic，Prompt 只引用 contract。A06 完整输出保存到 immutable RevisionCandidate；通过 Fidelity Gate 后才创建 ChapterVersion。RevisionResult 保存 candidate ID、hash、Fidelity 判定及 A06 issue 声明，不重复存正文。

## Authority 与最小修改

Review 是 A7 的质量诊断，不是新的 Story Authority。服务从原 Review 及其 ContextPackage 生成 immutable contract：

- target_issues 使用 `uuid5(review.id, "issue:{原数组索引}")`，同 Code 多个问题仍有不同 ID；优先级先按 P0/P1/P2，再按 revision_priorities 排序。
- KEEP 包含 strengths 的原描述、证据和保留方向，以及 Brief/approved Plan 的确切内容。
- DO_NOT_CHANGE 显式提供 Brief MUST/FORBIDDEN/preserve/creative_freedom、approved Plan、approved/locked Requirement/Decision、locked dependency、已批准相关前章事实及 approved WritingProfile（含 POV）。不将当前待修正文全文列为不能改的内容。
- 输出 preserve_items/do_not_change 是这些不可变条目的引用 ID；Validator 要求完整原集合，模型不能删掉、改写或加入 Review 建议冒充硬约束。

A06 只能提出正文修改。proposed_changes 与 memory_proposals 必须为空，不能直接写 Plan/Brief/Profile/Lock/Canon。最小修改可以覆盖一段连续交流或多个低价值段落，不限制为逐句机械补丁。局部可替换细节允许在 Creative Freedom 内展开；改变重大事实、required_outcome 或批准结尾不允许，缺乏依据时记录 blocked_reasons。

这些是结构、权限和输入约束。程序不会用脆弱关键词判断文学语义；是否实际上保留 strengths、提升人物声音、没有引入重大新设定，需要 A05 重审和人工对照。

## Context 与 exact binding

CP-006 已属于 Quality Review，因此扩展已有 Revision profile 为 **CP-007 v4**。不改名或覆盖旧 CP-007 v1。

用户触发时，RevisionRequest 冻结 source ChapterVersion / ChapterQualityReview / QualityBinding / 原 Review ContextPackage、CP-007 完整 profile snapshot/hash 和 authority contract。QualityBinding 已固定 Brief、approved Plan、approved Profile 和 relevant source fingerprints。Revision 要求原 Review 已绑定 approved WritingProfile；历史无 Profile 的 Review 返回 CONTEXT_MISSING，不创建任务。用户需先批准 Profile，再明确重新审阅，不能给旧 Review 偷换新 Profile。创建新未批准的 Plan/Profile 不使已批准绑定失效。

A06 两阶段和 A05 Fidelity 各自经 Context Engine 构建与本次 AgentRun 绑定的 ContextPackage / PromptLineage；执行阶段必须有第一阶段的 exact RevisionPlan。任务创建、领取、Provider 前及返回写入前均校验原绑定。Draft、Review、批准 Plan/Profile、相关 Decision/Lock 等变化使结果 CONTEXT_STALE/BLOCKED，绝不读取 latest 替换原输入。普通 unrelated 数据不会全量进入上下文。

Context 只选择目标章节、确切依赖及最近最多三章 approved 内容。006 尚未接入的 Character/Canon Memory 不在本阶段创造替代数据库；延续 Global Canon ≠ Character Knowledge 的 policy 边界，未知不能臆造。

## Persistence 与事务

010 新增 `revision_requests`、`revision_plans`、`revision_results`；010A 的 migration 0013 新增 `revision_candidates`，DB trigger 禁止 UPDATE/DELETE，唯一约束防止重复 artifact。RevisionRequest + 工作流事件/状态 + A06 task 在一个 Service transaction 内创建。

每个结果处理在既有 Project → Workflow → Task 锁顺序下验证 lease/state/source，再在一个事务中写 artifact、Draft successor、Audit、task terminal state、合法 Workflow event 和下一 task。Repository 只 flush，不 commit。数据库进一步校验 task/run/Prompt/Context owner、active request、source scope，以及 successor 的 current pointer、version+1、supersedes/parent、AGENT/A7/DRAFT/unlocked/unapproved、非空正文和 hash。失败全部 rollback。

技术 Provider 错误使用既有重试及 lease fencing。同一 event 重发返回 duplicate，并发不同 event 用 expected_state_version 只允许一个成功。业务无法安全修复保留 artifact 后进入 C90 BLOCKED，不作为 Provider failure 重试。这样的 artifact 不能 RESUME 重用；UI 显示原因和显式“重新审阅正文 vN”。技术重试耗尽仍可通过原恢复流程继续。新审阅不会自动再调用 A06。

## API 与界面

- `POST /api/v1/workflows/{workflow_id}/revision`：明确请求一次完整修改及重审。
- `GET /api/v1/workflows/{workflow_id}/revisions?limit=100&offset=0`：最新在前，包含 request/source_binding/plan/candidate/result。批量 join 获取，避免逐条查询。
- `POST /api/v1/workflows/{workflow_id}/quality-review`：沿用现有端点，从业务阻塞的 Revision 明确重新审阅当前 Draft。

正文顶部的轻量选择器切换 v1/v2，Review 按 exact chapter_version_id 选择，并标注 Review / Draft 版本；同正文多次审阅取 Review.version 最大值，修改操作另外验证 workflow 绑定。人工评价导出仍包含 project/chapter/workflow/draft_version，弹窗按 Draft ID 重建，禁止继承旧评价；现有评价仅下载本地 JSON，不提供服务端保存/历史评价查询。正常界面只显示修改进度、简要重点、原因和审阅结果；Context/Prompt/Run 原始 lineage 留在 Debug。

## 验收边界

Mock 验证结构、权限、版本、重试与停止，不证明文字改善。真实 Provider 仅由用户显式触发 Case 04/05。人工记录 Improved = YES/PARTIAL/NO，Strength Lost = YES/NO，New Major Problem = YES/NO，保留两份 Draft/Review 和完整 lineage，不做数字打分或语义 Delta Engine。

不实现 NOVEL-011 自然语言修改意见、不实现 NOVEL-012 Memory Commit、不自动更新 Profile/Prompt/Preference、不做无限循环或富文本 Diff。


## NOVEL-010A：Source Fidelity 与 Locality

正式三原则为 SOURCE FIDELITY、MINIMUM NECESSARY CHANGE、STORY DEVICE PRESERVATION。Source Draft 是完整的 EDIT_BASE，服务在 revision-contract 明确角色与 exact source ID；不新增通用 Context role 字段，不做 Context Engine 重构。target-version 与候选正文均为 P0，缺少完整文本或预算不足时拒绝，不能以 summary 替换。Review recommendations 仍是 A7 诊断。

`chapter-revision-plan.v2` 扩展：

- `preserve_scene_elements`：场景、物件、互动前提和事件机制；`preserve_relationship_elements`：关系功能；`preserve_effective_details`：已有效的动作/意象。每项有唯一 element_id、描述和原稿 exact paragraph evidence。
- `strength_preservation`：每项 Review strength 的原 ID 必须完整映射为 DIRECT/FUNCTIONAL + preservation_direction。`strength_regression_risks` 记录可能影响的 strength、risk、mitigation。
- `revision_zones`：每个 actionable issue 必须有 semantic_range，可带成对 1-based paragraph_start/end；blocked issue 无需制造修改区域。
- `allowed_structural_change` 默认 LOCAL（另有 NONE / CHAPTER_WIDE）；`change_budget` 默认 MINIMAL（另有 MODERATE / BROAD）。全文输出不是 BROAD。CHAPTER_WIDE 必须引用实际 Review issue，逐字绑定其 description，并说明 reason 和 why_local_insufficient；BROAD / FULL_PASS 仅在有此授权时允许。A05 进一步判断该理由是否真实成立，Planner 不能自行将局部问题升级为全章根因。

KEEP 数组不是保护的全部：未被问题覆盖的内容默认保留。必要局部对白可以整段调整；为衔接修改少量前后文、代词、节奏、对应动作也允许。禁止为了更容易满足 Review 而更换地点、核心物件、互动前提、人物关系角色或事件机制；Authority 可修改不等于 Fidelity 需要修改。

ABSTRACT_STAKES 依次使用原稿已存在信息、授权 Context canon、Approved Plan/Brief、安全 Local Elaboration。仍无依据则保留 unresolved，并解释 `Insufficient authorized context for stronger concretization.`。addressed 是声明，不是已解决的证明。新稿有安全改动时可保留部分甚至全部 unresolved；不为清零问题制造故事事实。

## NOVEL-010A：Fidelity Gate 与失败证据

在 existing C10 加一个 A05 REVIEW 能力任务 `VALIDATE_REVISION_FIDELITY`，不增加 Agent/Workflow 状态，也不改变 009 的 detection 或 taxonomy。A06 REVISE_CHAPTER 仅存候选稿和 lineage，不更新 Chapter current/approved。A05 接收 exact source + frozen Review + RevisionPlan + candidate，分别检查 SCENE_PREMISE、RELATIONSHIP_FUNCTION、UNAFFECTED_MATERIAL、STRUCTURAL_SCOPE，以及全部 strength 和具体 preserve elements。隐式保护允许发现 Planner 未列出的关键场景/关系。

`RevisionFidelityValidator` 检查 source/plan/candidate IDs、hash、完整输入、所有必须检查项、原文与候选证据位置，以及 verdict/checks/violations 的跨字段一致性。它不计算字符重合率、编辑距离或改动百分比；文学含义由独立 A05 判断，仍需人工验收。Fidelity 代码独立于 QualityCode：REVISION_SCOPE_VIOLATION、REVISION_STRENGTH_REGRESSION、UNAUTHORIZED_SCENE_REPLACEMENT。

只有有效、高置信 PASS 才在同一 Service 事务创建 successor Draft、写 RevisionResult、更新 current 和调度既有质量审阅。approved pointer 不变。FAIL 则记录 candidate + rejected result + A05 lineage，保持源 Draft/current，不执行后续质量审阅或自动 A06 retry。显式 RESUME 也不能复用已拒绝产物；用户可补充依据后重新审阅，再明确发起新 Revision。技术执行错误沿用既有有界技术重试/lease fencing；不可与语义 FAIL 混淆。

普通界面显示“这次修改范围过大，未替换当前正文。”，可展开未采用稿；成功后的体验仍为新 Draft 和正式 Review。Debug 显示 Source Fidelity、KEEP/CHANGE/DO NOT CHANGE、zones、budget、preserved strengths、risks 和 violations。分页历史批量 join candidate，不引入 N+1。

plan-chapter-revision / revise-chapter 使用新增 v2，targeted-revision skill 使用 v2；Fidelity 独立版本化 Prompt。历史 Prompt 文件不变，v1 结果仍可读。执行中旧 RevisionRequest 无 fidelity contract 时 fail closed，需新的明确请求，不能沿旧路径跳过门禁。

## NOVEL-010B：Revision Workspace

已完成审阅的当前 Draft 为 FAIL/PASS_WITH_WARNINGS 时显示“根据审阅修改”，PASS 不突出此操作。缺少 approved Profile 或 Review 已过期时先提供明确的偏好/重新审阅操作；旧 v2 无正式 Review 不伪装成可修改状态。

正文顶部选择器只改变 viewingVersion，Chapter.current_version 是独立的后台事实。默认跟随新 Draft，显式选择后固定阅读位置，即使在慢轮询开始时所选版本仍是 current；切章或关闭页面使旧响应失效。Revision 成功后保留所有旧稿和对应 Review，进行中的重审不阻塞新稿阅读；人工评价仍按版本隔离。

活动 Revision 通过 workflow.revision_request_id 匹配历史记录，不假设 revisions[0] 必然活动。C09 的全局进度来自 Workflow，历史 v1 的 Review 区仍显示 Review v1。技术失败仅提供状态机允许的恢复，Fidelity/业务阻塞不会自动重试。Fidelity FAIL 显示“这次修改范围过大，未替换当前正文。”和详情，Debug 提供完整源绑定、KEEP/CHANGE/DO NOT CHANGE、preservation arrays、zones/budget、addressed/unresolved、Fidelity/Result。

### 真实输入容量修正

010A 的完整 EDIT_BASE、Review、authority contract、Fidelity Schema 超过原 CP-007 v4 的 100000 保守 UTF-8 预算，真实 Case05 在 Provider 前失败。010B 新增 CP-007 v5（240000），只调整版本、描述和预算，selectors/Authority/版本/知识策略不变。三阶段预算测试保留全部 P0，超大输入继续 fail closed。旧文件和冻结请求不改；恢复走既有显式重审后新 RevisionRequest，不能称为篡改旧请求后重试。不存在模型消费或 Provider 容量承诺，实际结果仍须验证。

### 重审证据协议澄清

新增 A05 `quality-evidence` skill v3，明确单个 evidence 必须完整引用其 paragraph_index 对应段落中的连续原文。分析跨段对话模式时使用多个独立条目；不得拼接两段、改写或用省略号拼合。保留 v2 和历史 pin；现有确定性校验、Schema、严重程度、Verdict 与 A06 策略均不变。该修正对齐模型输入说明与已有校验，不接受不合法引用或自动改写模型结果。
