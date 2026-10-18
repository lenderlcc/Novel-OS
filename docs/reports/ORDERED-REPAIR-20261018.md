# Novel OS 顺序收敛修复 — 2026-10-18

按用户授权，顺序执行第五章失败定位、Memory 修复与对照、验收输入对齐、第五章恢复、首稿观察。
沿用项目 `688d6d8a-e6ae-4197-a320-c3cc1b81bf32` 的已批准 Profile v3，未修改第二章。
测试确认由助手代办，走既有接口、版本检查、Gate 与审计，不代表人工文学评价通过。
本轮未提交推送，未新增业务模块、表、迁移、依赖或并行执行框架。

## 1. 第五章规划失败：根因与修复

原 Task `33e47d9a-9457-4619-81ff-a6319233b7bf` 的私有捕获响应可以通过
`chapter-planning-result.v4` Schema。原 CP-004 v8 把全部 6 个 `memory-subjects` 身份
作为 P2 预算项裁掉；输出中的正确 Gu Che ID 与先前 Plan 一致，随后
`PlanningResultService.validate` 无法在当前输入找到该身份，抛出 ValueError，被结果处理器
归类为 SCHEMA_PARSE_ERROR。离线重放原响应及原业务校验得到同一错误。

修复：新增 CP-004 v11（对应普通 v8）/v12（对应探索 v10），将已有主体身份改为 P0；
身份数据不存在时仍允许为空，不自动编造。必要输入装不下时沿用现有预算阻断，不能裁掉
输出契约所需身份后仍调用模型。服务对历史快照中匹配 POV 的 TOKEN_BUDGET 排除原因
返回既有 CONTEXT_BUDGET_EXCEEDED；真正未提供的身份及其他排除原因仍拒绝。
没有提高预算、灌入额外知识或放松 Authority。

同一真实输入离线重建：旧 READY / 身份 0；新 READY / 身份 6，Gu Che 在内，模型调用 0。
第五章恢复任务 `e0657c64-e851-4dcf-af6e-fed2657497fd` 实际使用 CP-004 v11，6 个身份均为 P0。
原错误记录、原失败响应和 Plan v1 完整保留。前份报告误称无原响应的部分已更正。

## 2. Memory：已修复与尚未证实部分

确认的代码缺陷：角色 BELIEVES/SUSPECTS/DOUBTS 的“主张尚未证实”，也被
`blocking_uncertainty` 当成主体/提取歧义。现在这些候选可保留为有明确归属的认知状态；
身份歧义、低置信度、KNOWS 不确定、Canon/Authority 冲突仍阻断，非 KNOWS 不能链接
known_fact_id。旧提案再次确认会重新归一化并比较快照，不能静默放行。

第二章真实候选 `linlan_alarm_suspicion` 离线回放：AMBIGUOUS → NONE；主体仍是 Lin Lan，
epistemic_status 仍为 SUSPECTS，没有新增事实或正式记忆记录。

确认的模型遗漏：第三章原提取没有角色知识候选；第四章第一次有条目持有人，重提取时又遗漏。
对应原始响应可查，相关上下文没有预算排除。新增版本化 A07 Prompt v6，沿用原六类记忆：
明确分开世界事实与亲历者知识、更新相同主体/属性的判断变化、关闭真正完成的约定、保留
有持续影响的持有关系。没有自动推断所有在场角色都知道，也没有新增自动补写路径。

诊断提取对照使用当时完整输入、同一模型 gpt-5.6-sol 和原已接受正文；仅替换新的 Prompt/
Schema 描述及独立诊断 ID。复用 AgentRuntime 和正常输出解析，记录私有证据，不调用
结果持久化 handler，不创建 Proposal/Commit。归一化采用当章之前的历史版本，是只读
诊断，不等同于正式提交的 freshness、事务、版本及确认校验。

- 第三章：原 6 条 → 新 8 条；补出 Lin Lan/Gu Che 知道 Gu Che 非警报责任方。
  仍遗漏 Gu Che 亲历铜盒损坏；不能宣称 Memory 完整性修复通过。
- 第四章：一次调用返回 MODEL_OUTPUT_INVALID，无可校验完整结果，未自动重试。
  私有 harness 当时未配置 JSON 日志格式，只有错误码，具体 Provider 拒绝标签未保留；
  无法据此断言是截断、空输出还是响应结构问题。已复用既有日志初始化修正 harness，
  没有为补证据再次付费调用。

第三、四章已完成提交，现有正常流程不允许重新打开已完成章节覆盖 Memory。历史漏项保留，
本轮不直接补库、不把诊断结果冒充正式 Canon。当前仍缺乏逐项完整性保证。

## 3. 验收输入对齐

旧 expected-memory 的第五章 B.X=ABSENT 要求继续保持秘密；原 raw_requirement 只要求
POV 过滤，没有禁止 Lin Lan 在情节中主动告知。检索隔离不能替代“不发生披露”的故事要求。
现在 `chapter-05.json` 明确本章不披露/推断暗号，README 说明二者区别；旧输入和失败快照
不追溯改写。当前项目通过既有 REJECT 意见携带相同限制与铜盒连续性要求，恢复同一失败阶段。
恢复结果属于有明确驳回指导的 assisted recovery，不能计作未经干预的首轮成功。

## 4. 第五章受控恢复

第五章现为 `C16_COMPLETED / COMPLETED`，state_version 19。经正常 RESUME、Plan Gate
审批、Draft 接受及 Memory Confirm 完成；没有直接写数据库或绕过版本/权限保护。

- Plan v2：`7425a058-84f9-4805-a931-fab0501884b1`，Plan Review PASS_WITH_WARNINGS。
- Draft v1：`0d256ddb-9fc6-4eb0-8fe1-4a2b40639344`，原始首稿未修订。
- Review v1：`22985ecf-f8ef-4492-9fb8-4d2411b35e53`，绑定上述 Draft；
  Compliance PASS，Narrative FAIL，Audience Fit FAIL，Overall FAIL；无 hard gate issue。
- Proposal：`17d201ef-763d-4e16-a0cd-92f3c0bdf48c`。
- Memory Batch：`f310aa65-9544-44cd-a193-382fe3beabe5`，canon_revision 5。
  确认了公开登记核查线程 v2、Missing Courier 线程 v3、Gu Che/Lin Lan 合作状态 v2，
  以及 Lin Lan 保管铜盒的新状态。均有正文确切证据、匹配旧版本及兼容的 Authority 检查。

本轮恢复的 6 个工作流任务均 attempt=1、SUCCEEDED；没有新增工程失败或残留排队。
加上两次 Memory 诊断，本轮共 8 次真实调用，7 成功 / 1 失败。失败是第四章诊断，未重试。
此前第五章原失败仍保留，不能用恢复成功覆盖它。

首稿接受理由明确限定为连续性/Memory 工程验收；产品正常接口允许在无 Authority 阻断时
接受仍有风格质量问题的 Draft。审阅 FAIL 保留，未被改为 PASS。未启动自动修订或第六章。

最终核对：原 18 条 Memory 完整对象不变，新增 4 条，三次更新保留旧版本链；前四章对象及
第三/四章已接受版本不变；Profile 完整对象不变。Writer 使用批准 Plan v2 / Profile v3；
WritingResult → Task → Run → PromptLineage → ContextPackage → Draft 链路和正文 hash 一致，
双审阅绑定同一 Draft。Writer 没有接收前章全文、Lin Lan 的私有知识/纸条状态记录或暗号原文。

### 首稿质量观察：没有宣称系统写作效果已改善

这份第五章未经逐句打磨，可与第三、四章首稿一起确认问题跨章节存在。输入与 Plan 不同，
第五章还含驳回指导，因此是跨章观察，不是严格单变量 A/B，也不是人工文学验收通过。

- **重复信息：FAIL。** 第五章第 14、18、28、50、71、73 段重复“没有取得记录不代表
  投递结论”。第 18 段“眼前这次受阻同样不是答案”已完整说明，第 28 段又完整辩解，
  第 73 段再次列出未知项。
- **解释性旁白：FAIL。** 第 51 段动作后加“分工却因此有了形状”；第 55 段替读者解释
  “更接近真正的推进”，第 72 段再总结“两条线…都已经开始向前”。
- **人物具体性：PARTIAL。** 有拒绝捷径和讽刺，但第 43–53 段再次以协议补全代替人物交锋。
  项目仍没有已批准人物行为画像；不能据现有输入评价画像遵循率或自行补造画像。
- **事件变化：PARTIAL。** 核查受阻和申请递交真实发生，但案件信息增量少，承载过多规则解释。
- **Canon/知识边界：本次观察通过。** 铜盒保持损坏，未找到 Missing Courier，未披露暗号；
  这不等于对全文所有语义做了自动证明，也不弥补历史 Memory 漏项。

同类症状在第四章首稿第 61–70 段可见：划分“已见/待核/未知”后，再重复“先核验”和
“仍没有找到那个人”。第三章首稿第 59、63–64 段也在事件后总结信任及未知。
本次 Narrative Review 准确识别了第五章程序化对白 P1、过度解释 P2、受众风格不符 P1，
附有对应段落。当前已不能把问题简单归因为“审核只看合规”；上游 Plan 仍允许用
边界确认与流程分工承担主要场景，Writer 则将这些边界进一步写成正文。

### 收敛结论与剩余事项

工程恢复验证通过，**整体五章验收仍未通过**，原因是 Memory 完整性及首稿自然度不足。
下一轮只应聚焦两个目标，不继续打磨单章：

1. 用当前冻结输入核验人物亲历知识、判断更新、完成约定和持有关系的提取覆盖；区分
   新提取质量与既有历史缺失，不能把新 Prompt 等同于已修复已提交数据。第四章输出
   失败原因仍缺证据；若再次执行，使用已启用的既有安全日志，不盲增预算或自动重试。
2. 针对 Plan 的事件/选择/后果容量做有限对照，观察初稿能否减少重复论证；复用现有
   Plan Review / Narrative Review，保留批准 Profile，不再追加平行评审体系或禁令清单。

这两项未完成，不用“全流程完成”冒充全部产品质量通过。

## 5. 验证结果

- Planning / Prompt capture / clarification / exploration 等相关回归：62 passed。
- Memory 合同、不确定性、状态变化及 Context：172 passed。
- 新增历史快照错误归类四分支后，身份预算测试：7 passed（其中原 3 项已在前组）。
- PostgreSQL Memory 提交、历史、事务、隔离集成：首次 39 passed / 1 failed；唯一失败是
  测试仍断言 Prompt v3，实际为 v6。更新该旧断言后对应完整用例重跑 1 passed。
- 更新输入后的 Recorded 五章连续性及 finalized Draft 隔离主用例：1 passed（非真实写作质量测试）。
- ruff check、ruff format --check：本轮 13 个 Python 文件通过；git diff --check 通过。
- 独立审阅确认身份预算、人物认知/Authority 边界和私有对照无业务写入路径。
  独立运行 Memory 纯离线测试 122 passed。未声称本轮执行全仓库测试。
- API / DB health 正常；Worker 重启后仍只领取该项目任务，运行参数没有自动扩大到其他项目。

## 6. 本轮变更文件

- `backend/novel_os/context/profiles/CP-004.v11.json`、`CP-004.v12.json`
- `backend/novel_os/services/context.py`、`planning_results.py`
- `backend/novel_os/memory/policy.py`、`schemas.py`
- `backend/novel_os/prompts/library/task_template/extract-chapter-memory/v6/`
- `backend/tests/test_planning_identity_budget.py`、`test_memory_story_uncertainty.py`
- 当前版本断言更新：`test_planning_clarification_contract.py`、`test_memory_contracts.py`、
  `test_memory_transition_contracts.py`、`context/test_context.py`、
  `core/workflow/test_planning_context_and_concurrency.py`、`test_exploration_context.py`、
  `core/quality/test_memory_transitions.py`
- `evals/e2e/multi-chapter/chapter-05.json`、该目录 README
- 本报告、FIVE-CHAPTER 报告更正、PROJECT-STATUS。

本轮之前的未提交文件保留，不混称为本轮新增修复。私有运行证据：
`backend/.runtime/ordered-repair-20261018/`，旧基线仍在 `five-chapter-continuation-20261018/`。


## 后续提交前复核（2026-10-18）

用户要求提交推送已有改动并继续上述收敛计划。发布包含产品代码、版本化 Context /
Prompt、验收输入说明和报告，不包含测试代码、本机配置、原始运行日志或密钥。
此前段落“未提交推送”描述的是恢复验收结束时的快照，发布版本以 main Git 记录为准。

提交前针对相关预算、Worker CLI、规划合同和 Memory 边界再次验证：134 项通过。
首次运行 133 PASS / 1 FAIL 原因为测试仍期待 CP-004 v10；补充旧 v10 仍可解析的断言，
将最新版本断言改为 v12 后全组通过，没有为测试更改生产行为。前端相关 49 项通过，
构建、lint、后端变更文件 ruff check / format --check 和 git diff --check 通过。
这不是全仓库全量验收；测试代码不入库的 fresh-clone 复现限制继续保留。
