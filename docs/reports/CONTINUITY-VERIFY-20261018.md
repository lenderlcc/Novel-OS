# 连续性复验：见证知识与 v4 探索入口

## 本轮结论

2026-10-18 按“提交推送、继续执行”推进。开始前核对本地 main 和远端 main 均为
`047e46ff1381fc78cd624249be7b5c0871379c62`，已有产品修复已推送，无需重复提交。
测试代码仍按用户此前要求留在本地。

**工程回归通过；Memory 提取完整性仍未通过；v4 探索诊断被来源引用校验阻断。**
本轮不修改产品代码或 Prompt，没有新正文、Plan、Memory commit，也没有新建 E2E 项目。
两个真实调用均收到完整响应，不能把本轮阻塞归为网络掉线或输出截断。

## 1. 第三章 Memory 补验

沿用原第三章已接受 Draft v1、原 A07 冻结 Context，使用当前 Memory v7 /
`lingzhi-memory` / `gpt-5.6-sol` / 16384 输出上限，单次执行现有 AgentRuntime。
使用新的诊断 task UUID，不覆盖旧 capture，不调用业务结果持久化。

结果：Provider 与 Runtime 成功，输入 23162、输出 7315 tokens，54.173 秒，
`finish_reason=stop`；7 条候选通过精确证据、边界引用与只读历史归一化。
候选为：铜盒永久损坏、警报启动时间、Gu Che 非责任方、Lin Lan 知道排除责任、
Gu Che 知道排除责任、警报真正责任仍未决、Lin Lan 留在 Clock Tower。

**Gu Che 亲见铜盒损坏的知识仍然缺失。** 原文第 37 段写他协助抬起齿条，
第 40 段明确“Gu Che看着那团变形的铜”。这支持他看见损坏，不等于他知道
Lin Lan 的私密纸条或全部内部结构检查结论。

- 原始输出与 normalized 均为相同 7 条，遗漏发生在模型输出，非归一化删除。
- 本次未触及输出上限；不能继续用截断解释这条漏项，也不能据此断言增大容量毫无作用。
- v7 已在第 19–21 行要求分别提取有证据的见证者知识；不能仅再加一句相同要求就宣称修复。
- 13 条证据引文均精确匹配对应段落；未见将私密暗号传给 Gu Che、提前找到信使或确定警报责任方。
- 输出有效与提取完整是不同结论。停止对同一缺口继续抽样，不复制 Canon 补造知识。

来源：`backend/novel_os/prompts/library/task_template/extract-chapter-memory/v7/content.md:19`；
本机 `backend/.runtime/continuity-verify-20261018/chapter-3-compare-{input,result,normalized}.json`。
`original_candidate_count=6` 对比的是原正式提取，不是前轮 v6 的 8 条诊断结果。

## 2. v4 的真实输入与覆盖边界

现有五章 Workflow 都是 v3 / COMPLETED。v4 正式入口已存在：
`POST /api/v1/workflows/chapter-exploration`，复用同一 Worker、Context、Runtime 和结果服务。
没有修改已完成流程的版本。

本轮只做第五章历史输入的探索组件诊断：目标 Chapter 元数据取原生成前快照；
Brief、批准 Profile v3 与旧输入逐项一致；其他数据由真实查询按 `before_sequence=5`
选取，使用现有 CP-004E v2 和 ContextEngine。输出仍是 A7 推断，未伪装成正式探索记录。

实际选入：15 条正式 Memory、6 个身份、3 个已批准前章 Plan（第 4v1、3v1、2v2）、
Brief、Profile、目标章节、任务输入和项目元数据；没有预算排除、没有前章全文、没有
第五章后来的正文或 Memory。模型配置与前轮第五章 Planning 诊断一致。

这不是单变量 A/B：旧 Planning Context 只有 7 条 Memory，并含前章全文、旧 Plan 和
Review targets；探索 Context 按自己的既有合同选取 15 条 Memory 和 3 个近期 Plan，
不含旧 Plan/Review targets 或前章全文。重叠来源的 payload 完全一致，差异单独保存。

当前正式 Memory：16 条 current、含历史共 22 条；其中 **DERIVED_CHAPTER_SUMMARY=0**。
三个近期已批准章节各有正式 commit batch，但没有摘要。产品 CP-004E 将历史摘要定义为
可选 P1，因此可以做稀疏历史诊断；完整 013R repetition case 却要求三个已提交章节摘要，
先决条件不成立。不能把诊断称为该 case PASS，也不能将 fixture 摘要塞入 Context。

来源：`backend/novel_os/api/planning_routes.py:15`、
`backend/novel_os/services/exploration_policy.py:13`、
`backend/novel_os/services/exploration_context.py:102`、
`evals/e2e/multi-chapter/run.py:482`。

## 3. 探索结果：格式通过，必需来源引用不完整

单次 Lingzhi / gpt-5.6-sol 调用返回 3 个概念；输入 20002、输出 4811 tokens，
49.533 秒，`finish_reason=stop`。Schema 与 Runtime Authority 检查通过。

随后复核 `ExplorationResultService.validate` 的精确来源与必需引用集合：
18 条已引用来源均存在，但 16 项必需的 A3/Locked 来源中遗漏 8 项：

- 2 条 Canon：Gu Che 不是警报责任方；警报实际启动时间为十一点四十七分。
- 6 个 A3 `IDENTITY_ONLY`：Gu Che、Lin Lan、Missing Courier、Sealed Copper Box、Station Alarm、T-417。

现有服务第 48–54 行要求全部这些来源被引用，所以该输出**不能被产品结果服务接受**。
这是输出来源合同失败，不是用户没有权限，也不证明输出故事已经改写 Canon。
没有放宽校验、自动补引用或把这份结果交给 Planner；失败后没有自动重试。

注意证据层级：诊断的 Runtime `error_code=null` 保留原值；本机后续验证文件记录 FAIL
以及现有服务会返回的 `AUTHORITY_DENIED`。没有实际调用整个结果 Service，也没有新建
正式 AgentRun；不能伪称开发库的 Workflow 本轮失败或通过了持久化/freshness。

候选内容也不足以证明写作改善：选中 C1 将核查推进为“提交可追踪查询、等待结果”，
但仍以程序阻力和可核查手续为主要机制。C3 能识别重复塔内核对并被拒绝，这是局部观察；
未经有效 Plan 与首稿不能给阅读质量结论。

另外，C1 把“提交查询、结果待回”称为履约，但原 OPEN_THREAD 承诺包含核验登记并带回
可复核结果。受理凭据至多证明已启动，不能证明完整履约或关闭承诺。此处是未落库概念的
语义风险，没有已经发生的 Memory 污染。

选中概念写“Gu Che 已知铜盒损坏”并非仅来自缺失的知识记录：原冻结任务还保留了第五章
Plan v1 被拒后的实际用户规划指令，明确指出第三章他亲见损坏，并允许当场观察承接。
因此不能直接判为无依据泄漏；也不能拿它证明 Memory 已修好或自动连续性不再需要人工修补。

来源：`backend/novel_os/services/exploration_results.py:44`；本机
`exploration-input.json`、`exploration-context-delta.json`、`exploration-result.json`、
`exploration-validation-complete.json`。初次验证脚本在集合检查处停止；补充机器可读失败记录
保留全部缺失项，没有修改原 Provider 输出。

## 4. 验证与数据保护

- 本轮 2 次真实调用；Memory 组件合同通过但完整性不通过，Exploration Schema 通过但来源合同不通过。
- 必要回归 **167 PASS**，覆盖 Memory 输出预算/合同/不确定性，探索合同、Context 和真实事务流程的 RecordedProvider 集成；无真实模型混入 pytest。
- 两条 warning 来自 Starlette/AnyIO 弃用提示，无测试失败；未重跑全仓库测试，不声称全量通过。
- 独立只读复核确认第三章漏项、13 条证据引文、探索缺失 8 项引用及 013R 先决条件结论。
- 前后 API 快照：批准 Profile v3、五章完整对象、全部 22 条历史 Memory 完全相同。
- 五个 Workflow 均 COMPLETED，无 PENDING/CLAIMED/RUNNING 任务；API/数据库健康、前端均正常。
- 无依赖、迁移、表或接口变更；产品代码与默认 Prompt 保持；Planning v13 仍 EXPERIMENTAL。
- 准备脚本的本地参数/序列化错误均未产生额外 Provider 调用；原日志保留，不算产品失败或模型重试。

原始证据在 `backend/.runtime/continuity-verify-20261018/`，最终 SHA256SUMS 索引留在本机。
测试、私有输入/输出、配置和运行日志不提交；未提交测试带来的 fresh-clone 复现限制仍存在。

## 后续顺序与停止条件

1. **先收敛输出合同可靠性。** 对探索的必需引用清单核对现有编译输入和服务校验来源，
   再决定最小合同表达修复；不能自动补引用、降低 Authority 或将失败结果继续流转。
2. **再处理 Memory 覆盖。** 用已保存的第三、四章证据分别检查事件、实际见证者、持有人和
   承诺履行；验证重点是遗漏及误加，不是数量。相同规则已存在时，不继续叠加写作禁令或抽到满意为止。
3. **最后才进入有效 Plan/首稿对照。** 普通 v4 稀疏历史诊断与完整 013R repetition 分开，
   后者先补齐通过正式流程产生的历史来源；不倒灌摘要、不覆盖现有已完成章节。

这轮已在真实输出校验失败处停止，不生成第六章、不调整第二章正文。仍未取得新首稿，
不能宣称工程测试通过已经改善文学质量。
