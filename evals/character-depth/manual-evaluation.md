# Character Depth & Voice 人工评估模板

状态：**NOT_RUN / NOT_EVALUATED**。复制后逐例填写。当前文件不是验收结果。

## 运行与可比性

| 项目 | 记录 |
|---|---|
| 评阅人、时间、Case ID | 待填 |
| Acceptance run_id/test_id/project_id、started/completed/status | 待填；模板存在不等于已执行 |
| 真实调用授权、Provider、Model、实际调用次数 | NOT_RUN |
| 输入材料 hash、固定 ID 到真实 ID 的映射 | 待填 |
| 实际提交的点名 raw_requirement、Scene 人物、批准 POV ID | 待填；不能只提交评估 UUID |
| 人物身份、State、Knowledge 与关系事实版本 | 待填 |
| Approved BehaviorProfile ID、version、hash | 待填；缺省不是自动批准 |
| Selected Relationship Modifier、所属 Profile version | 待填 |
| Excluded Modifier/人物及理由 | 待填 |
| Approved Plan ID/version、WritingProfile、人称 | 待填 |
| AgentTask/Run、ContextPackage profile/version/hash、SourceVersions | 待填 |
| PromptLineage、模块版本、完整 Plan/Draft 文件与 hash | 待填 |
| A/B 两次执行的输入差异和 Provider 重试 | 待填；全部记录 |
| 实际 Human Gate/decision/Audit refs | 待填；不自动批准 |
| name-hidden reading aid 文件、blind labels、评阅后才打开的完整 evidence 映射 | 待填；使用现有 runner export --blind-reading-output，不自动评分 |

## 五个 Case

| Case | 人工问题 | 结果 | 具体证据与影响 |
|---|---|---|---|
| CDV-01 Same pressure | 遮去姓名后，注意、决定、行动、心理反应是否体现不同人物逻辑？差异是否超出语气词？ | NOT_EVALUATED | 待填 |
| CDV-02 Relationship | A 对 B/C 的解释、示弱、回避、防御是否随对象变化？各 Context 是否只含相关 Modifier？ | NOT_EVALUATED | 待填 |
| CDV-03 Exception | 是否执行批准 Plan，并用当前动机支持与通常倾向不同的选择？有没有把 Profile 变成行为脚本？ | NOT_EVALUATED | 待填 |
| CDV-04 Knowledge | Writer 是否不知道 Secret X？观察、推测与确定知识是否分清？“敏锐”是否绕过知识边界？ | NOT_EVALUATED | 待填 |
| CDV-05 No profile | 原有 Plan/Write/Review 是否继续，Review 是否避免无依据的 OOC 断言？ | NOT_EVALUATED | 待填 |

还应记录：Canon State、User Lock 和批准 Plan 是否保持；叙事人称是否正确；是否出现所有候选都围绕一个性格标签的 NOVEL-013 退化。允许相同结果、合理例外、普通场景和没有某种对话技巧。不给人物差异设词频指标或 exact-prose compare。

| 观察维度 | 具体片段 / A-B 证据 | 人工判断 |
|---|---|---|
| Character Logic Difference | 待填 | NOT_EVALUATED |
| Voice Difference | 待填 | NOT_EVALUATED |
| POV Difference | 待填 | NOT_EVALUATED |
| Relationship Specificity | 待填 | NOT_EVALUATED |
| Knowledge Compliance | 待填 | NOT_EVALUATED |
| Naturalness | 待填 | NOT_EVALUATED |

先隐藏明确姓名阅读，记录能否大致区分人物行为/对白及依据；然后打开完整 evidence 中的 label/source 映射核对。这个 human aid 不构成自动 PASS rule，主持人仍需记录可比性和展示顺序。

## Blind Character Evaluation

Sample A（隐藏人物名字及别名）：

> 待填：从 name-hidden reading aid 选取正文；人物身份映射留在完整 evidence，评阅后再打开。

Sample B（隐藏人物名字及别名）：

> 待填：从相同比较条件的另一份 name-hidden reading aid 选取正文。

Human judgment（选择一项）：**Clearly Different / Somewhat Different / Interchangeable**。

Notes：待填具体行为、决定或对白的依据，以及影响比较的输入差异。这里只记录人工判断，不生成自动 Voice Score 或自动 PASS。

## Review、Revision 与 Human Feedback

1. 将 `weak-character-source.txt` 作为人工编写的待评来源，通过现有合法工作流/评估工具绑定精确 ChapterVersion、Plan 和 Context。保留来源链路；若无法绑定，记 NOT_RUN，不能伪造 AgentRun 或绕过服务直写。
2. A05 使用 A/B 已批准 Profile。检查是否根据真实段落和 Profile 证据指出 `WEAK_CHARACTER_VOICE`、`CHARACTERS_AS_ARGUMENTS` 或适当的现有诊断；不要求同时报全部代码。再对照无 Profile 情况：可以诊断普通对话问题，但不能凭感觉判 OOC。
3. A06 根据 A05 问题做 Targeted Revision。检查是否利用 A 的害怕回避/玩笑防御、B 的核实/理性化和 A 对 B 的关系修饰，改变交流与行动的因果。不能仅加口头禅，也不能替换场景、排水槽装置、人物关系、取回凭条或晚到两分钟的结果。
4. 对同一精确 Source Draft 发起 NOVEL-011 反馈：“这里林遥说话不像他，尤其是直接完整交代自己害怕被评价的那句；只修改这一处对话，别换场景。”检查 A02 是否结合批准 Profile 理解原因，A06 是否针对局部修改并保留 Source Fidelity。
5. 分别记录“这一处更冷一点”与“以后这个人物都这样”的处理。当前反馈只能修当前 Draft；长期修改应提示人物 Profile 变更/批准流程，不能偷偷持久化。对照反馈、Review、Revision 和 A07 Memory 前后所有 Profile 的 version/hash，确认未变化。

| 环节 | 判断 | 结果 | Source refs、段落与版本证据 |
|---|---|---|---|
| A05 Review | 诊断具体、Profile 引用准确，缺省不猜 OOC | NOT_EVALUATED | 待填 |
| A06 Revision | 人物因果增强，未换场景或只添语气词 | NOT_EVALUATED | 待填 |
| Fidelity | 地点、装置、关系、目标与结果保留 | NOT_EVALUATED | 待填 |
| NOVEL-011 Feedback | “不像他”的解释有 Profile 依据，改动局部 | NOT_EVALUATED | 待填 |
| Authority/Persistence | 不改 Plan/Lock/Canon/Knowledge，不自动学习 Profile | NOT_EVALUATED | 待填 |

## 验收记录

- Engineering Acceptance：引用独立测试报告与限制，待填。
- Real Behavior Acceptance：NOT_EVALUATED；不能由工程 Mock 替代。
- Human Prose Evaluation：NOT_EVALUATED。
- 已观察缺陷、证据及复测条件：待填。
- Known limitations 与接受者：待填。
- NOVEL-013 Real Acceptance：PENDING；NOVEL-014 真实人物改善：尚未证明。
- 完成后停止，不开始 NOVEL-015。
