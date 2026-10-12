# Generation Quality v0.1 — 冻结初稿对照

状态：**PREPARED / REAL NOT_RUN / HUMAN NOT_EVALUATED**。本轮只导出真实记录、离线重建提示词和验证工程合同；模型调用为零。不修改正式第二章，不开始正式第三章。

## 已保存基线

`manifest.json` 固定两个真实案例，原始材料存于其 `baseline_root`（本机忽略目录，不包含密钥）。复用 `evals/e2e/multi-chapter/run.py` 的只读 export / run_evidence 保存输入、版本、Draft、Review、Task、Run、Context 和 PromptLineage。两个 Writer 的历史模块 pins、Schema、Context 均已重新编译，compiled hash 与运行记录完全一致；这是应用层提示词证据，不是原始 HTTP 抓包。

| 案例 | 比较对象 | 作用与限制 |
| --- | --- | --- |
| `chapter02` | 《没有证据的怀疑》原始 Draft v1；当前 v5 仅作修改历史证据 | 检验旧疑点被写成新发现、2000–2500 字目标与事件容量、知识边界；不得用 v5 代替初稿成绩。 |
| `untouched-chapter06` | 项目 `23c028ee…` 第六章《继续2》，唯一 Draft v1，revision_count=0 | 未经反复人工修订的独立案例；原情节有选择、损失和具体结果，可检查是否误罚有效交锋。 |

两案历史模型均为 Lingzhi / `gpt-5.6-sol`，ModelProfile hash 相同。各案 A/B 必须固定自身实际批准 Profile：第二章 v3，独立第六章 v2。两案 Profile 并非相同，尤其后者没有后来添加的字数条款；不能跨案比较绝对指标来推断字数因果，也不能把第二章 Profile 擅自复制到其他项目。

历史审阅已发现程序化对白与总结旁白，不能描述为完全漏检。保留其原始等级和理由，比较新审阅是否补足信息重复、动机及实际变化证据，同时监测误报。

## 对照设计

使用冻结实际输入在独立文件评测中复用既有 PromptRuntime、Provider、Schema、ContextSerializer 和校验器；不写产品数据库，不伪造正式 Plan 审批或 Memory。评测标识与产品 Task/Run ID 分开标明。历史导出及质量评测复用现有 `evals/quality/run.py`；不新增平行审核引擎。

1. **无调用准备**：逐案核对需求、已批准 Profile、人物画像、POV、此前正式 Memory、Plan/Brief 及来源 hash。旧输入没有的资料保持缺失；若后来补充并批准，双方同时冻结新输入，并标记为新实验，不能与历史初稿冒充同输入 A/B。
2. **规划对照**：每案 A 用原规划合同/Context；B 用补丁合同/Context。除了本次已登记的证据选择和澄清处理，模型、原始材料和其他模块全部固定。各生成一次 Plan，再各一次 Plan Review，共 8 次调用。若 B 发出合理澄清，记录“发现输入缺口”，停止该案；这不是正文质量 PASS。任何技术失败停止，不筛选重抽好样本。
3. **人工关卡**：先比较 Plan 的旧信息、本章新增变化、人物选择及后果、篇幅容量。新 Plan 只有明确人工认可为评测输入后，才进入 Writer；不能静默改变批准的正式 Plan。
4. **初稿生成**：两个案例、两个臂各一次 Writer，共 4 次。禁止人工删改、A06修订和失败重抽。Writer Prompt 本轮不新增写作禁令；记录精确 Plan / Context 差异，包括已有 CP-005 v8 去重。前章全文仅用于 Planner/Reviewer，不绕过 Writer Knowledge Firewall。
5. **同标准审阅**：四份初稿都用同一补丁后的 A05 Compliance + Narrative 各一次，共 8 次，避免不同 Reviewer 标准混淆正文差异。保留老 Review 作为历史参照，不把模型自报 addressed 或 Fidelity PASS 当成成效。
6. **盲读**：使用 `human-evaluation.md`，先读打乱顺序的正文，再揭示条件。每项须附原文片段、作用和影响；有效人物交锋不是重复论证，材料不足不能靠编造新线索取高分。

完整首批**最多 20 次单次调用**：8 规划/计划审阅 + 人工确认后 12 写作/质量审阅；无自动重试。单案单臂样本只能给初步方向，不能宣称统计显著或后续所有章节均改善。若仅审阅冻结初稿，4 次调用可检查 Reviewer，但不能证明生成改善。

这是组合补丁对照，不能把全部差异归因于某一字段。若出现改善且需确认原因，再另行批准单变量消融：固定同一已认可 Plan 仅比较 Context投影；或固定输入和模型只比较两份 Plan。字数目标、角色资料、模型参数不能同时改动后声称是代码效果。

## 调整登记与执行门槛

- 已有：Planning v11 / Plan Review v7 的容量与信息变化规则；CP-005 v8 无损去重；CP-006 v5 独立修订诊断输入。
- 本轮：Plan Review 及探索 Planning补足前章已批准事实证据；Planning可通过有类型的澄清输出停在既有人工处理路径；Narrative Review校准初稿与相邻段落的作用/因果判断。
- 保持：Writer Prompt、批准 Profile、正式章节与 Memory、Authority、POV owner过滤、字数偏好的层级、两路A05与Severity规则。
- 数据缺口：第二章没有 Gu Che 正式身份/合法知识绑定，也没有两位人物的批准行为画像。工程回归会用明确合成数据验证通路；真实评测不得把合成数据冒充实际设定。缺画像不自动阻塞普通章节；明确要求的单一 POV 无法绑定时，应解释所需身份确认，不能自动创建。
- 授权：历史授权针对第二章修订/保存，不能据此替独立第六章或新的20次系统对照授权。本轮未调用模型。执行前明确核对 Lingzhi/gpt-5.6-sol、两个案例的外发范围、8+12 次分阶段额度，以及失败和人工关卡停止规则。

## 判定

工程 PASS 只说明正确选版、隔离、预算、澄清和流程可运行。真实初稿需同时减少无新增作用的重复/段落，并保留人物选择和有效交锋，且不增加 Canon/Knowledge/Plan 违规。更短、对话更多、PASS 数量更多均不能单独作为改善证明。缺真实样本或人工判断时填写 NOT_RUN / NOT_EVALUATED，不补写结论。
