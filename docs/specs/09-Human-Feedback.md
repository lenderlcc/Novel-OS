# Human Feedback & Directed Revision — NOVEL-011

本文件对应 2026-09-29 的 NOVEL-011 开发请求。旧 Ticket 中的 Chapter Acceptance、Memory Commit、统计与自动偏好学习不在本阶段。

## Feedback Domain

`HumanFeedback` 是 USER 对 exact 当前正文的显式修改意图，不是 CreativeBrief、QualityReview 或 HumanEvaluation。保存 raw_feedback、project/chapter/workflow、source_chapter_version_id、source_draft_version、source_state_version、可选 source_review_id / reply_to_feedback_id、return_state、冻结的 Context Profile 与 authority_snapshot。`source=USER`、`status=RECORDED`，不原地编辑。

`HumanFeedbackInterpretation` 由现有 A02 的 `INTERPRET_CHAPTER_FEEDBACK` 生成；每条 Feedback 至多一个已接受 Interpretation，保存 task/run/prompt/context lineage。两张表均 append-only，Repository 只 flush。流程状态在 Workflow 与 AgentTask 中；RECORDED 不代表正在执行。

## Interpretation 与安全推断

Pydantic `FeedbackAgentResult` 是 Structured Output、parse 和 runtime validation 的共同来源。输出 intent_summary、requested_changes、preserve_requests、do_not_change、target_regions、quality_concerns、scope、safe_inferences、ambiguities、conflicts、change_impact、action、user_message、decision_question、feedback_evidence、supporting_review_issue_ids、source_refs、confidence。

普通模糊质量意见应自主形成安全 prose 修改；只有真实分歧、矛盾或 Authority 冲突才提问。scope 为 LOCAL / SECTION / CHAPTER_WIDE，region 是语义区域，不向用户展示数字 patch。Service 不按词语猜意图；模型给出语义结论，确定性校验检查结构、具体 ID、原话 evidence、来源与 action/impact/conflicts 一致性。

| Action | 路径 |
| --- | --- |
| REVISION | prose-only、安全且有目标；直接进入既有 A06 |
| REPLAN_REQUIRED | 改变已批准方向/方案；返回空闲状态，用户明确提交新章节需求后复用已有 Planning |
| PROFILE_CHANGE_REQUIRED | 持续项目偏好；返回空闲状态，打开已有 Profile 编辑/版本/审批界面 |
| USER_DECISION_REQUIRED | Lock/Canon/用户指令矛盾或重大分歧；说明原因，等待用户新反馈/显式权限操作 |
| NO_CHANGE | 保存反馈和解读，不创建 A06 |

两层 Proposal 数组都必须为空，Schema 直接 `maxItems=0`。不把无效结构当作用户权限问题。技术/格式失败走既有 error taxonomy 和有界重试；低置信/失败 envelope 不固化唯一 Interpretation，可在原冻结来源仍有效时显式 RESUME。

## Authority 与合并

用户显式 preserve / scope 高于 AI Review 建议，但不自动更改 User Lock、Canon、Approved Plan 或 Profile。Review 是 DIAGNOSIS_ONLY。HUMAN_FEEDBACK / BOTH 不把 Review strengths 自动升级成强制 KEEP；保留用户要求、已批准约束和原文 Fidelity，AI_REVIEW 原路径不变。人工 Revision 的 targets **仅**来自 requested_changes，使用独立 `HUMAN_FEEDBACK` target code，不强迫用户反馈伪装成 QualityIssue；其 Review evidence_refs 为 []。具体原文 preservation 与 Fidelity 仍必须提供精确段落引文。

revision_source 为 AI_REVIEW / HUMAN_FEEDBACK / BOTH。HUMAN_FEEDBACK 默认；A02 引用了当前 Review 的具体诊断 ID 时才为 BOTH。A06 的目标、KEEP、DO_NOT_CHANGE 均冻结在 RevisionRequest。不会把其他 Review 问题顺便加入修改目标，不累计历史反馈进 constraints，不自动学习项目偏好。

## Revision Integration

`POST /api/v1/workflows/{id}/feedback` 携带 event_id、expected_state_version、source_chapter_version_id、raw_feedback（1–12000 字符）和可选 reply_to_feedback_id / reason。当前正式 chapter-planning v3 的空闲 C10/C11 接受；转 C13 调度 A02。历史 workflow definition YAML 不变，使用与 Revision 相同的 application event 扩展边界。

“补充修改要求”引用同 Workflow、同 exact Draft 的最新 USER_DECISION_REQUIRED Feedback。A02 按时间顺序读取这条关联链的原始用户反馈、问题和本次回答；原始保留要求继续有效，除非用户明确改变。问题仅帮助解释回答，不作为用户 quote evidence。链路同时冻结到 A06 / Fidelity contract；无关历史反馈不进入上下文，独立新反馈不关联旧链。

REVISION 解读后：C13 → C10 的 PLAN_CHAPTER_REVISION → REVISE_CHAPTER candidate → VALIDATE_REVISION_FIDELITY → 创建同章新 Draft → 既有 C08/C09 两轮 A05 Review → WAITING_HUMAN / STOP。非 REVISION 返回记录的原 C10/C11，不新建 Revision。

解释阶段可通过 `POST /api/v1/workflows/{id}/feedback/discard` 显式放弃本次反馈（event_id、expected_state_version、feedback_id）。复用既有 Workflow transition、审计、任务取消和迟到结果保护，返回 C10/C11 的 WAITING_HUMAN，指向当前 Draft。不可变 Feedback/Run 历史保留。过期输入不自动绑定新来源，用户重新提交时才冻结当前来源；已经进入 A06 的修改继续使用既有取消机制。

RevisionRequest 的 Review/QualityBinding 在人工来源下可空；必须有唯一 source_feedback_id、已接受 REVISION Interpretation 和其 exact ContextPackage。AI_REVIEW 仍必须拥有原 Review/Binding。BOTH 必须引用同一 Feedback 的 Review。数据库检查 source、scope、task、run、prompt、context、candidate/Fidelity/successor lineage，不能用 nullable 绕过。

RevisionPlan v4、RevisionResult v3、Fidelity v3 承载 revision_source/source_feedback_id。当前 Prompt 为 Feedback v2 / Plan v6 / Execute v7 / Fidelity v5；targeted-revision skill v3、revision-fidelity skill v2。历史 Prompt 不覆盖，以前安全的 Plan v3 / Execute v2 / Fidelity v2 继续使用原 Prompt/Skill；更早不具备安全契约的版本维持只读限制。

## Preserve 与 Fidelity

`feedback-preserve:n` 进入 KEEP，`feedback-boundary:n` 进入 DO_NOT_CHANGE。每个 user target 的 zone.semantic_range 必须属于 A02 冻结的该 target_regions。LOCAL/SECTION 不允许 FULL_PASS、CHAPTER_WIDE、BROAD。明确 prose-wide 意图也不授权替换故事。

除原有 SCENE_PREMISE、RELATIONSHIP_FUNCTION、UNAFFECTED_MATERIAL、STRUCTURAL_SCOPE 与合同中的 preservation elements，Fidelity 必须检查 HUMAN_SCOPE 及所有 feedback-preserve / feedback-boundary。人工路径不能重新将与用户意见冲突的 Review strengths 加回强制保留项；无关原文仍受 Fidelity 保护。每项有独立 source/candidate paragraph evidence。失败保留候选证据和原 current，不能生成替代稿或自动再修。语义是否确实保留由 A05 判断，工程校验不能证明文学效果，仍需人工阅读。

## Context 与 Freshness

CP-008 v1：P0 原始反馈、完整 source Draft、CreativeBrief、Approved Plan、显式依赖/有效约束、Approved WritingProfile；P1 可选当前 Review、最近批准正文。只有结构化 ID/关系/版本查询，无 Vector/Embedding。CP-007 v7 复用 Revision context，新增人工反馈/解读项，source-quality-review 可选，完整 frozen contract 仍 P0。

绑定当前 UUID、正文 hash、Brief、Approved Plan、Approved Profile 和相关授权来源快照。提交、调度、模型前、结果入库、恢复均检查。创建未批准的 Plan/Profile Draft 不替换 approved 来源。当前人工新 Draft 即使没有 Review，也可显式绑定并更新 workflow 的 draft pointer；页面仍显示旧 UUID 时必须 409。已批准版本只能创建新版本，不能原地修改；current 与 approved pointer 继续分离。

## UI 与 Debug

当前正文提供“我想修改”及自然语言输入，“发送并修改”直接执行一次安全修改。展示理解反馈、确定范围、修改正文、重新审阅。普通 UI 不暴露 Agent、Schema、scope enum。非安全路径说明原因，Profile 打开已有面板，Replan 由用户编辑完整章节需求并明确提交；不自动改写原 CreativeBrief。

历史正文只读，展示当时反馈与产生该版本的原话。版本选择与后台 current 分离；失败/取消后仍可读原稿。Debug 展示原始反馈、source版本、全部 Interpretation、revision_source 及关联 Revision/Context/Prompt/Task/Run。

## Migration

0014_human_feedback 新增两张表、workflow.human_feedback_id、revision_requests.source_feedback_id，并调整人工来源的 nullable Review/Binding。upgrade/downgrade/upgrade 在独立测试库执行。已有人工反馈时 downgrade 主动拒绝丢失不可变历史；生产环境只 upgrade，回退应用前必须先审查已有数据与任务。

0015_feedback_clarification 仅新增 nullable reply_to_feedback_id 自关联和同来源/最新问题约束，不改写 0014 或已有反馈。已有澄清链时拒绝破坏性降级；未使用澄清链时可完整降级/升级并保留原反馈。

## Non-goals

不增加 A08，不新增 Revision Engine，不更改 Writer 或 Quality Review 判断，不实现 Character/Event/Canon Memory、Memory Commit、自动学习、跨章分支、Feedback 管理器或 NOVEL-012。人工反馈语义推断存在模型误判风险，工程与模型/人工验收必须分别报告。
