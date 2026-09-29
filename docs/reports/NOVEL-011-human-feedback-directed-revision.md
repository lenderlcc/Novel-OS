# NOVEL-011 — Human Feedback & Directed Revision

Date: 2026-09-29. Branch: `wfg/novel-011-human-feedback`.

## 1. Background

原始需求定义章节目标；读过正文后的反馈定义针对某一版正文的修改意图。011 将两者分开，避免反馈覆盖 CreativeBrief。开发基于已获取的最新 `origin/main`（8199173），并继承 010A/010B 与修订段落证据定位修复 cab34ac；没有重写稳定基础设施。

## 2. Scope

增加 HumanFeedback、HumanFeedbackInterpretation、A02 的反馈解释任务，以及现有 Revision 的人类方向输入。没有新增 A08、第二套 Revision Engine、Writer 调整、Quality Review 规则调整或 Memory Commit。

## 3. Product Flow

当前 Draft →「我想修改」→ 自然语言反馈 → A02 理解 → A06 修改方案 → A06 候选正文 → A05 Fidelity → 新 Draft → A05 两阶段 Review → 等待用户。安全局部修改不要求用户审批 JSON；重大方向、项目偏好和真实矛盾才中断。

## 4. HumanFeedback Domain

`human_feedback` 记录 project/chapter/workflow、精确 source_chapter_version_id/version、原始反馈、提交时状态版本、可选 Review、冻结的 Authority snapshot、Context profile、USER 来源及时间。`human_feedback_interpretations` 独立记录结构化结果及 Task/Run/PromptLineage/ContextPackage。两个表均 append-only；解释结果对 feedback/task/run 唯一。Repository 只 flush；事务由现有 application runtime 控制。

迁移为 `0014_human_feedback`。数据库触发器检查版本、任务、Authority 和 Revision 来源绑定。已有 HumanFeedback 时拒绝 downgrade，以免静默删除不可变历史；空测试 schema 支持完整升降级回环。

## 5. Feedback Interpretation

Pydantic `FeedbackInterpretationOutput` 是 Structured Output 合约来源。保存 intent、requested_changes、preserve_requests、do_not_change、语义 target_regions、quality_concerns、scope、safe_inferences、ambiguities/conflicts、action、证据、引用与 confidence。普通 API 不暴露可伪造的 authority/status/actor 字段。

Action 只包括 REVISION、REPLAN_REQUIRED、PROFILE_CHANGE_REQUIRED、USER_DECISION_REQUIRED、NO_CHANGE。Scope 只包括 LOCAL、SECTION、CHAPTER_WIDE。

## 6. A02 Integration

复用 A02，新增 `INTERPRET_CHAPTER_FEEDBACK` / `interpret-chapter-feedback.v1`，使用已有 C13 状态。允许能力仅为报告结果。使用 CP-008.v1、版本化 Role/Task/Skill/Quality Profile；`proposed_changes` 和 `memory_proposals` 在 Schema 中均限制为空。历史 Prompt 未覆盖。

## 7. Authority

显式用户修改范围优先于 AI Review 的建议；Lock、Canon、批准的故事边界仍优先。Schema 检查声明的影响与 action 一致性，Service 检查真实来源和冻结版本，A06 保持现有 Authority/Fidelity 检查。反馈没有直接修改 Brief、Plan、Profile、Canon 或 Memory 的执行能力。

## 8. Ambiguity Handling

普通表达问题由 A02 结合正文和诊断自主定位；只有不同理解会改变故事方向或显式指令矛盾时才返回一个简短的决定问题。USER_DECISION_REQUIRED 只保存解释并等待用户，不分派 A06。补充要求以新反馈保存，不修改原记录。

## 9. Safe Inference

推断必须记录于 safe_inferences；原文最小证据必须是 raw_feedback 的真实子串。没有自然语言关键词 if/else 路由。离线测试中使用可控 Provider 输出来验证路由和持久化，不把 Mock 成功宣称为真实语义能力通过。

## 10. Revision Integration

复用现有 RevisionRequest/Plan/Candidate/Result 和 Fidelity 后才晋升正文的路径。新输出版本为 plan v4、execution v3、fidelity v3；对应最终 Prompt 版本为 5、6、4。新 CP-007.v7 支持有/无诊断 Review 的人类反馈。此前安全的 v3/v2/v2 合约继续通过其固定历史 Prompt/Skill 执行。

Revision 来源支持 AI_REVIEW / HUMAN_FEEDBACK / BOTH。每份反馈最多产生一个 RevisionRequest；它使用独立的确定性 UUID，避免与 HumanFeedback 在 EXTENSION 引用空间冲突。没有 AI Review 的最新手工 Draft 也可走同一流程。

## 11. AI Review Merge Policy

A02 只能选择现有、精确版本 Review 中的辅助 issue IDs；选择后标记 BOTH。修改目标由用户解释生成，Review 作为 DIAGNOSIS_ONLY 支持；不会把全部 AI 问题合并成必改清单，更不会升级为故事 Authority。

## 12. Preserve Semantics

preserve_requests 转为必须覆盖的 KEEP；do_not_change 转为 DO_NOT_CHANGE。保留 Scene/Relationship/Effective Detail，语义 target_regions 约束 revision_zones。LOCAL/SECTION 禁止变成整章结构重写。Fidelity 额外检查用户保留项、禁止项和区域边界，失败保留旧正文，不晋升新 Draft。

## 13. Replan Boundary

改变章目标、结局方向或 Approved Plan 时返回 REPLAN_REQUIRED。UI 引导用户在原需求上明确新方向，再调用现有需求修正/Planning 流程；不会由 A06 修改批准 Plan。

## 14. WritingProfile Boundary

持续偏好请求返回 PROFILE_CHANGE_REQUIRED，打开已有写作偏好界面供用户显式编辑/批准。本次反馈不会被自动学习为永久偏好。历史 Profile 与 approved/current 分离继续有效。

## 15. Freshness

提交校验 exact source Draft = current；排队、模型调用前、结果接收时再次核对 Draft、批准 Plan、批准 Profile、Brief 与 Lock 等 Authority snapshot。修改不相关的 Profile draft 不污染 approved context。stale 反馈不得套用到新版本。

## 16. Versioning

ChapterVersion 不可变。候选修订经 Fidelity 通过后才生成同 Chapter vN+1；approved_version 不随新 Draft 自动改变。新 Review 必须绑定生成的新正文 ID。event_id、workflow expected_state_version、唯一 feedback→interpretation/revision 约束共同防重。

## 17. Frontend

增加空白反馈输入、发送并修改、中文阶段、明确的失败/方向/偏好/决定分支、当前版本入口和历史只读记录。沿用取消、恢复、版本选择与人工评价；人工评价和反馈没有混表。网络响应丢失重试沿用 event_id，切换章节不会把旧异步错误或结果写入新页面。浏览器实测刷新恢复显示 Draft v3、Review v4 对应 Draft v3、原始反馈来源以及「我想修改」入口；展开时输入框为空，空输入的发送按钮禁用。

## 18. Debug

展示 Raw Feedback、Source Draft、结构化 Interpretation、Revision Source、Revision Plan/Candidate/Result/Fidelity、Task/Run/PromptLineage/ContextPackage。低置信度或失败 envelope 在持久化 accepted Interpretation 前被阻断，保留 Raw Feedback/AgentRun，并允许现有显式恢复，不留下唯一记录阻塞重试。

## 19. Tests（首次实现，Review 修复前）

011 专项 41 项通过，包含完整六任务链路、无 Review 的手工最新 Draft、A–H 语义结果路由、Lock、非法输出、低置信度恢复、重复投递、并发提交、取消、rollback、immutable、queued/in-flight freshness 与 Fidelity 失败不晋升。前端 134 项通过。已完成独立后端和前端 Review，发现的 UUID JSON 序列化、EXTENSION ID 碰撞、低置信度恢复和 C13 失败后阅读区消失问题均已修复并回归；没有遗留 Blocking/Required。

最终后端全量 pytest：**1342 passed、4 skipped、0 failed**。完整 collection 共 1346 项，使用隔离数据库 schema 分组执行，成功分组覆盖全部 collection，集合互不重叠。4 项 skipped 均为未加 `--live-model` 的付费 Provider 测试；本次真实反馈验收单独显式执行并记录于第 20–21 节。已完成的质量检查：

| Check | Result |
| --- | --- |
| Backend full pytest | 1342 passed / 4 opt-in skipped / 0 failed |
| Frontend npm test | 134 passed / 10 files |
| Frontend lint / typecheck / build | PASS |
| Backend ruff check | PASS |
| Backend ruff format --check | PASS（366 files） |
| git diff --check | PASS |
| Migration upgrade → downgrade -1 → upgrade | PASS（隔离 test schema，0014 → 0013 → 0014） |
| alembic check | PASS，No new upgrade operations detected |
| Dev database upgrade / check | PASS，当前 head 0014_human_feedback |
| Docker backend + worker build | PASS |
| Docker API startup / health / health/db | PASS（容器内 HTTP 检查；临时容器已清理） |
| Native API / frontend | PASS，8000 health/db 正常，5173 可访问 |
| Updated worker | 已重新创建运行；验收结束时没有待执行任务 |

旧测试中的迁移 head、历史表快照、CP-007/Prompt 版本及测试替身字段按新增合约更新；不会修改历史产品数据来迁就断言。最初长运行载入了更新前的测试断言，其失败项随后复测通过。最早的只读旧合约仍拒绝运行；紧邻上一阶段的安全旧合约增加 3 项回归，继续固定历史 Prompt。所有测试代码仅在本机保留，本次未提交/推送。

## 20. Real Provider Acceptance

使用用户已配置的 Lingzhi / gpt-5.6-sol，配置每个任务最多尝试一次，分阶段检查后才执行下一步；发现具体 Prompt 歧义并修复后，显式恢复了失败的执行阶段。没有新建 Chapter、没有重新 Writer 生成，也没有隐式循环重试。

原文反馈：

> 整体已经比上一版自然很多，
> 但养护棚那段对白还是有点一问一答。
> 另外‘这是一个能交代得过去的决定’
> 这种直接替读者总结的句子我不喜欢。
> 其他地方不要大改，
> 石湾小学、撤离车和最终继续上山都保留。

A02 已通过：action REVISION、scope SECTION、两个语义区域、四个显式保留项、两个禁止项、confidence 0.97、无澄清问题；引用两个现有 Review issue 作为诊断支持。A06 Plan 已通过，用户保留和范围进入正式 Revision Contract。首次 execution Prompt v5 将 feedback-boundary 标识混入 preserved_items，后端按精确集合校验正确拒绝，原 Draft v2 保留。发布新的 revise-chapter Prompt v6 明确 KEEP 与 DO_NOT_CHANGE 标识的不同用途；没有修改历史 v5、丢弃非法字段或放宽校验，并增加额外标识拒绝回归。

最终执行：Prompt v6 的 A06 通过；Fidelity PASS，31 项检查、0 violation；同章 Draft v3 生成；新 Review v4 为 PASS_WITH_WARNINGS（Compliance PASS、Narrative PASS_WITH_WARNINGS、Audience Fit PASS），0 hard gate、1 个 P2 OVER_EXPLAINED_REASONING，requires_revision=false。Workflow 停于 C11_INTERNAL_PASS / WAITING_HUMAN（state_version=36），待执行任务为 0。

本次共 7 次真实 Provider 调用：6 个成功阶段 + 修复前 1 次 execution 合约失败；每个任务均只有 1 次 attempt，没有自动重试循环。调用均为 lingzhi / gpt-5.6-sol。

| Stage | Task | Run | PromptLineage | ContextPackage | Task Prompt |
| --- | --- | --- | --- | --- | --- |
| INTERPRET_CHAPTER_FEEDBACK | a508c5b9-40fa-41fa-8e82-69e83f1074d4 | 4209a7de-a89d-4044-9d8a-26a758823617 | 7a613aaa-ddf0-4bab-8c95-174bb2067c0d | 77d117e0-4f7e-43d3-8e18-8929a324279c | interpret-chapter-feedback v1 |
| PLAN_CHAPTER_REVISION | 2f15d791-10cf-4761-9194-222f43be00f0 | b75e48cb-1843-4c1d-aee3-22ef0401b5e2 | a2626f75-71fe-4f9a-b147-5fe3ea7b4c9f | 12185718-1538-419e-812f-66596d5cadf0 | plan-chapter-revision v5 |
| REVISE_CHAPTER | 39c59f55-e340-45c4-9f24-a28bf1c6b521 | 2b80ade8-93f2-40b8-a0da-3b798d2b61b0 | 91b35b66-e959-4135-aa15-c9b4ce0bcedb | 8f63d53f-c8c7-42e7-b7fc-253f645d2ae4 | revise-chapter v6 |
| VALIDATE_REVISION_FIDELITY | 02983126-ecf4-4827-88b6-6a8068bc9906 | 4d6d0680-7584-42d7-8961-bb46dd61101d | f0fa9123-0275-4dd8-883c-55ff152d8942 | 649cfe20-3e99-4ecf-8d92-77fe5c60ab06 | validate-revision-fidelity v4 |
| REVIEW_CHAPTER_COMPLIANCE | d9094240-6b5d-4462-9bda-18ba3c2cba3f | ba6540f9-2d05-4ef5-931d-18a39aa74cf5 | 91d5d49f-f239-4878-9c64-da210496afb3 | 90624355-dd22-4e87-a271-4ad4c6198656 | review-chapter-compliance v1 |
| REVIEW_CHAPTER_NARRATIVE | 05472447-08fc-49e5-8ff2-e1865746c504 | ebd625f7-aab6-4f87-84dc-477163cdc512 | 11cef886-7a73-4293-8aaf-c7ba5107bdcd | 574aa529-4876-40f1-afdc-e7ae1c7ad955 | review-chapter-narrative v2 |

所有成功阶段 ModelProfile 为 `lingzhi-structured`，冻结 hash `9ae0b152887db3ea647ff150774605278c53953702322e1cde08dc0cbc5bec47`。Context profile 为 A02 CP-008.v1、A06/Fidelity CP-007.v7、A05 既有 Review profile；完整原始输出仅存本机私有 runtime，不纳入 Git；根目录 `.runtime/` 也加入忽略规则。

## 21. Case 05 Draft02 → Draft03

实际沿用先前 010 验证成功的第 8 章 `hh`，不根据“Case 05”名称猜测其他数据：

| Binding | ID |
| --- | --- |
| Project | 23c028ee-cd94-4965-af85-731e560c9633 |
| Chapter | 0db2fea7-db58-4cc6-9947-4fcee48bdb21 |
| Workflow | c96f61c2-da12-4b05-9051-073a63d7f079 |
| Source Draft v2 | fd3046a6-40be-4560-a87e-e59d8b341ff8 |
| Source Review v3 | 3aabf408-2a44-4d40-adab-23b0d54b722d |
| HumanFeedback | 3b8edc05-e738-42e1-b6b0-2b38e320b109 |
| Interpretation | e4406c1e-cbf2-40b6-8010-2ccda11e15de |
| RevisionRequest | c7099e60-814c-5be3-838a-9a4408510cf5 |
| Candidate | 8fa23981-ee1a-4562-aa2a-f6f10dd6eec5 |
| RevisionResult | 2c2ca0b5-bb6c-4ed2-901c-5d0eeded7ed2 |
| New Draft v3 | 544d07d5-d376-4be8-b8b0-c8dbf4641eb3 |
| New Review v4 | ff4a07b5-a776-4c4b-9453-1a782bca6e80 |

注意：Review 的流水版本和 Draft 版本独立；原 Draft v2 已有 Review v3，因此本次新 Draft 的 Review 序号应继续递增，不能强行改名 Review v3。最终以 chapter_version_id 绑定为准。

数据库/API 交叉核验：current_version=3，approved_version=null（没有自动批准）；Review v4.chapter_version_id=`544d07d5-d376-4be8-b8b0-c8dbf4641eb3`。原 Draft v2 全字段未变，hash `696b2b815d20f925f1d44d16f7cc9099ebecf525f05eacfc6dee1dbe5131f756`；v3 hash `da6afc60818e5514e40be1128bd573df3b5eab142ed3afd9c53d5d4dd20f3295`。Approved WritingProfile 与提交前完全一致。

正文 diff 只有两个区域：养护棚内合并问题并穿插动作；删除用户点名的直接总结句。其他段落逐字不变，石湾小学、撤离车、Stakes、最终继续上山与主要场景结构保留。仍需人工判断改后对白是否足够自然；没有为了清除 Review 的其他建议继续扩大修改。

## 22. Known Limitations

- A02 的自然语言语义仍取决于模型；结构/引用/版本检查不能数学证明语义解释完全正确，需结合真实验收。
- Fidelity 是晋升前的强制模型门禁，不代表人工文学质量评分。
- 非 Revision 分支只引导现有流程；没有自动解锁、自动改 Profile 或自动改批准方向。
- 已落地不可变反馈后，数据库迁移有意禁止破坏性降级。
- 保留现有单用户本机权限模型，没有扩展多人身份体系。

## 23. Deferred to NOVEL-012

Memory Commit、偏好学习、Prompt Auto Tuning、Golden/Reject Sample 自动写入、Fine-tuning、Analytics、多人评论、富文本批注、复杂段落选择器、语音/图片反馈全部未实现。

## 24. Acceptance Result（首次实现，Review 修复前）

Engineering Acceptance：**PASS**。完整自动化回归、真实链路、迁移、Lint、Build、Health 与独立 Review 均通过。

AI Behavior Acceptance：本次原文反馈真实通过（REVISION / SECTION，保留要求生效，未自动追问或扩张到其他 Review 建议）；A–H 的全部语义类型目前只有离线可控输出回归，不宣称全部做过付费模型验收。

Human Prose Evaluation：待用户阅读 Draft v3。改动范围与保留约束可验证，但“对白更自然”的程度仍由用户决定；AI Review 保留一条无需自动修改的 P2 重复归纳建议。

| Acceptance area | Result |
| --- | --- |
| A02 复用、独立 Feedback/Interpretation、无新增 Agent | PASS |
| Exact Draft、不可变记录、幂等、防并发重复 | PASS |
| Authority / Plan / Profile / Lock / Canon 边界 | PASS |
| 模糊意见的安全解释、显式保留与范围 | 原真实 Case PASS；其余路由有离线回归 |
| 现有 A06、强制 Fidelity、新版 A05 Review 后停止 | PASS |
| UI 当前版本入口、历史只读、Debug 与刷新恢复 | PASS |
| Independent Review | PASS，无遗留 Blocking/Required |
| Human Prose Evaluation | PENDING，需用户阅读 v3 |

NOVEL-011：CONDITIONAL PASS（仅人工正文验收待确认）。没有开始 NOVEL-012。

## 25. Review 修复（2026-09-29）

按 Review 确认的三个根因做局部修改，复用现有 Workflow transaction / transition、A02、A06、Fidelity、ContextPackage、前端表单和 mutation；没有引入 Feedback Manager、通用仲裁框架、新 Agent 或新 Revision Engine。

| 问题与根因 | 修复 |
| --- | --- |
| Draft / Approved Profile 变化使 C13 Feedback stale；恢复必须拒绝旧来源，但旧 feedback 指针又阻止新提交 | 增加显式 DISCARD_FEEDBACK，返回原 C10/C11 的 WAITING_HUMAN 并读取当前 Draft。保留不可变历史、审计与幂等；迟到结果仍 STALE_IGNORED。用户重新提交才冻结新来源，不自动重试或重绑定旧任务。 |
| “补充修改要求”把短回答作为独立反馈，丢失原问题和保留要求 | 添加 nullable reply_to_feedback_id，限定同 Workflow、同 Draft 的最新 USER_DECISION_REQUIRED。仅投影这条关联链的用户原话和问题，并冻结到 A06 / Fidelity Context；quote evidence 只能来自用户原话。独立新反馈不携带无关历史。 |
| Human Revision 复用了含 Review strengths 的强制 KEEP，导致用户想删除的表达反而不可修改 | 人工路径复用 contract_for(None, …)，只把真实批准约束和用户保留项作为强制承诺。HUMAN_FEEDBACK / BOTH 的 Review strengths 保留为诊断建议；原 AI_REVIEW 路径及 source Fidelity 不变。 |

持久化使用增量迁移 **0015_feedback_clarification**，未重写已部署 0014。数据库自关联与触发器限制父子来源、最新问题和严格递增的 state version，历史按同一版本顺序展示。旧 Feedback 的关联字段为 null，历史 Context / Prompt 继续有效。存在澄清链时拒绝破坏性降级。

新 Prompt：interpret-chapter-feedback v2、plan-chapter-revision v6、revise-chapter v7、validate-revision-fidelity v5；历史版本未覆盖。Pydantic 输出结构未另起一套，未放宽 Authority。

验证记录：

- 新增后端修复回归 **13 passed**：queued / in-flight Draft 与 Profile stale、放弃后的重新提交、重复放弃、迟到交付、连续两轮澄清、错误/过时父反馈、HUMAN / BOTH strength 冲突、新 Draft 与新 Review 绑定、0015 往返迁移和历史保护。
- 原 011 后端测试 **41 passed**。前端全量 **137 passed / 10 files**，包括澄清引用、独立反馈、过期提示、放弃后回到当前正文。
- 扩展后端回归覆盖 **384 项**（其余 975 项未重跑）：包含全部 Quality / Revision 集成、Revision 单元、历史迁移、Context 与 Prompt 注册/编译。首轮 **383 passed / 1 failed**；唯一失败是段落引用测试仍断言旧的最新 Prompt 版本号，按新版本更新断言后该文件 **8 passed**（含失败项），无遗留失败。Prompt 注册/编译另外复测 **40 passed**。本次没有重复宣称执行全部 1359 项后端 collection；第 19 节全量结果属于修复前。
- Frontend lint / typecheck / build、Backend ruff check / format check、git diff --check 通过。
- 隔离测试库执行 upgrade → downgrade -1 → upgrade / alembic check 通过；本机开发库仅 upgrade 到 0015，alembic check 无模型漂移。
- Backend 与 Docker Worker 已更新，前端 / health / health/db 均 HTTP 200；更新后 active task count=0。
- 原真实案例依旧是 Draft v3、C11_INTERNAL_PASS / WAITING_HUMAN、state_version=36；历史反馈 GET 在新增 nullable 字段后仍可读取。
- 独立 Review 确认 discard 与迟到结果沿用原锁序/lease fencing，父链无环且不引入无关历史，没有新增高置信正确性问题或明显过度设计。

本次修复没有调用真实 Model Provider。第 20–21 节是此前 Prompt 版本的真实验收证据，不能当作这次新 Prompt 的真实语义验收；新的澄清与人工优先场景已完成可控输出回归，真实模型表现仍待用户下一次明确测试。未提交或推送代码，测试文件仍仅在本机；没有开始 NOVEL-012。
