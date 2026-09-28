# Targeted Revision Engine — NOVEL-010

本规范落实 2026-09-24 的 NOVEL-010 补充需求，取代旧 ticket 中多种 Revision Mode、自动循环及数值质量指标的设想。Formal Revision 属于现有 `chapter-planning.v3`；旧 v1/v2 工作流保持原行为。

## 用户控制与状态

用户在当前有效 Review 为 FAIL / PASS_WITH_WARNINGS 时明确点击“根据审阅修改”。PASS 不提供主修改按钮。请求必须带 event_id、expected_state_version、source_review_id、expected_draft_version。普通 Review 完成不会自动启动 A06。

```text
C10/C11 WAITING_HUMAN
  -- USER REQUEST_REVISION --> C10 WAITING_AGENT (A06 PLAN_CHAPTER_REVISION)
  -- AGENT REVISION_PLAN_READY --> C10 WAITING_AGENT (A06 REVISE_CHAPTER)
  -- AGENT REVISION_READY --> C08 --> C09 (A05 Compliance + Narrative)
  -- INTERNAL_REVIEW_PASSED/FAILED --> C11/C10 WAITING_HUMAN, STOP
```

每个用户 request 至多一个 plan、一个 result、一个 successor Draft。Review v2 FAIL 也停止；需要用户基于新 Review 再次明确请求才可改下一版。revision_count 在用户请求时增加，不把技术重试或审阅 FAIL 计为新修改。特殊事件由 deterministic WorkflowRuntime 验证和处理，Agent 不能指定状态、事件或 next_state。

## 两阶段契约

A06 同时拥有 PLAN_CHAPTER_REVISION 和 REVISE_CHAPTER，不增加 Agent。

`RevisionPlanOutput`：source Draft/Review/chapter、target_issue_ids、preserve_items、revision_targets、do_not_change、revision_strategy、scope、blocked_reasons、source_refs、confidence。scope 默认为 TARGETED，仅另支持 FULL_PASS。每个问题必须分配到 safe target 或 blocked reason，不能遗漏、重复或偷偷替换问题。

`RevisionResultOutput`：source Draft/Review、revision_plan_id、content（安全阻塞时可为 null）、addressed/unresolved_issue_ids、preserved_items、declared_changes、blocked_reasons、source_refs、confidence。addressed 仅是 A06 自述，后续 A05 独立判断是否改善。

唯一输出 Schema 是 Pydantic，Prompt 只引用 contract。持久化 Result metadata 不重复存正文，以 ChapterVersion ID 和 SHA-256 关联 immutable prose。

## Authority 与最小修改

Review 是 A7 的质量诊断，不是新的 Story Authority。服务从原 Review 及其 ContextPackage 生成 immutable contract：

- target_issues 使用 `uuid5(review.id, "issue:{原数组索引}")`，同 Code 多个问题仍有不同 ID；优先级先按 P0/P1/P2，再按 revision_priorities 排序。
- KEEP 包含 strengths 的原描述、证据和保留方向，以及 Brief/approved Plan 的确切内容。
- DO_NOT_CHANGE 显式提供 Brief MUST/FORBIDDEN/preserve/creative_freedom、approved Plan、approved/locked Requirement/Decision、locked dependency、已批准相关前章事实及 approved WritingProfile（含 POV）。不将当前待修正文全文列为不能改的内容。
- 输出 preserve_items/do_not_change 是这些不可变条目的引用 ID；Validator 要求完整原集合，模型不能删掉、改写或加入 Review 建议冒充硬约束。

A06 只能提出正文修改。proposed_changes 与 memory_proposals 必须为空，不能直接写 Plan/Brief/Profile/Lock/Canon。最小修改可以覆盖一段连续交流或多个低价值段落，不限制为逐句机械补丁。局部可替换细节允许在 Creative Freedom 内展开；改变重大事实、required_outcome 或批准结尾不允许，缺乏依据时记录 blocked_reasons。

这些是结构、权限和输入约束。程序不会用脆弱关键词判断文学语义；是否实际上保留 strengths、提升人物声音、没有引入重大新设定，需要 A05 重审和人工对照。

## Context 与 exact binding

CP-006 已属于 Quality Review，因此扩展已有 Revision profile 为 **CP-007 v3**。不改名或覆盖旧 CP-007 v1。

用户触发时，RevisionRequest 冻结 source ChapterVersion / ChapterQualityReview / QualityBinding / 原 Review ContextPackage、CP-007 完整 profile snapshot/hash 和 authority contract。QualityBinding 已固定 Brief、approved Plan、approved Profile 和 relevant source fingerprints。Revision 要求原 Review 已绑定 approved WritingProfile；历史无 Profile 的 Review 返回 CONTEXT_MISSING，不创建任务。用户需先批准 Profile，再明确重新审阅，不能给旧 Review 偷换新 Profile。创建新未批准的 Plan/Profile 不使已批准绑定失效。

两阶段各自经 Context Engine 构建与本次 AgentRun 绑定的 ContextPackage / PromptLineage；执行阶段必须有第一阶段的 exact RevisionPlan。任务创建、领取、Provider 前及返回写入前均校验原绑定。Draft、Review、批准 Plan/Profile、相关 Decision/Lock 等变化使结果 CONTEXT_STALE/BLOCKED，绝不读取 latest 替换原输入。普通 unrelated 数据不会全量进入上下文。

Context 只选择目标章节、确切依赖及最近最多三章 approved 内容。006 尚未接入的 Character/Canon Memory 不在本阶段创造替代数据库；延续 Global Canon ≠ Character Knowledge 的 policy 边界，未知不能臆造。

## Persistence 与事务

新增 `revision_requests`、`revision_plans`、`revision_results`，DB trigger 禁止 UPDATE/DELETE，唯一约束防止重复 artifact。RevisionRequest + 工作流事件/状态 + A06 task 在一个 Service transaction 内创建。

每个结果处理在既有 Project → Workflow → Task 锁顺序下验证 lease/state/source，再在一个事务中写 artifact、Draft successor、Audit、task terminal state、合法 Workflow event 和下一 task。Repository 只 flush，不 commit。数据库进一步校验 task/run/Prompt/Context owner、active request、source scope，以及 successor 的 current pointer、version+1、supersedes/parent、AGENT/A7/DRAFT/unlocked/unapproved、非空正文和 hash。失败全部 rollback。

技术 Provider 错误使用既有重试及 lease fencing。同一 event 重发返回 duplicate，并发不同 event 用 expected_state_version 只允许一个成功。业务无法安全修复保留 artifact 后进入 C90 BLOCKED，不作为 Provider failure 重试。这样的 artifact 不能 RESUME 重用；UI 显示原因和显式“重新审阅正文 vN”。技术重试耗尽仍可通过原恢复流程继续。新审阅不会自动再调用 A06。

## API 与界面

- `POST /api/v1/workflows/{workflow_id}/revision`：明确请求一次完整修改及重审。
- `GET /api/v1/workflows/{workflow_id}/revisions?limit=100&offset=0`：最新在前，包含 request/source_binding/plan/result。批量 join 获取，避免逐条查询。
- `POST /api/v1/workflows/{workflow_id}/quality-review`：沿用现有端点，从业务阻塞的 Revision 明确重新审阅当前 Draft。

正文版本入口切换 v1/v2，Review 按 exact chapter_version_id 和 workflow 选择，并标注 Review / Draft 版本。人工评价 storage key 仍包含 Draft 版本，切换时重建组件，禁止继承旧评价。正常界面只显示修改进度、简要重点、原因和审阅结果；Context/Prompt/Run 原始 lineage 留在 Debug。

## 验收边界

Mock 验证结构、权限、版本、重试与停止，不证明文字改善。真实 Provider 仅由用户显式触发 Case 04/05。人工记录 Improved = YES/PARTIAL/NO，Strength Lost = YES/NO，New Major Problem = YES/NO，保留两份 Draft/Review 和完整 lineage，不做数字打分或语义 Delta Engine。

不实现 NOVEL-011 自然语言修改意见、不实现 NOVEL-012 Memory Commit、不自动更新 Profile/Prompt/Preference、不做无限循环或富文本 Diff。
