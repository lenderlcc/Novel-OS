# 连续性收敛：Memory 容量与 Planning 对照

## 结果

已按用户要求提交推送已有修复到 main：`9e0128e`。随后继续既定顺序：先检查
Memory 提取，再检查 Plan 容量。用户的委托测试执行授权有效，无新增次数额度；
仍复用现有运行和验证组件，不直接写业务数据库、不修改已完成正文或提交 Memory。

**工程方面确认并修复了 A07 输出容量不足；Memory 完整性和真实写作效果仍未通过。**
Planning 实验只有局部改善，没有替换默认模板。没有继续反复修改第二章或生成第六章。

## 根因与对应处理

| 已确认依据 | 最小处理 | 验证结果与限制 |
| --- | --- | --- |
| 第四章冻结输入在原 8192 输出上限返回 `incomplete_max_output_tokens` | 复用 TaskDefinitionRegistry 已有 Writer 的任务 profile 映射方式，当前 Lingzhi A07 使用独立 `lingzhi-memory` / 16384；不修改原 profile | 相同 v7 Prompt / Schema / 正文 / Context 在 16384 下成功，实际输出 8691 tokens；不宣称该容量能容纳任意数量的候选和历史边界 |
| 第三章旧成功输出的逐候选权限检查占序列化文本约 54%，含大量重复解释 | 新增 Memory Prompt v7，压缩 reason 和冗余复述，保留每个 source_ref、outcome、证据及检查项 | 单独使用 v7 仍在 8192 下截断，证明精简文字不足；没有削弱检查以换取通过 |
| 第三章原文 37、40 段支持 Gu Che 亲见铜盒损坏，但 v6 模型结果与归一化结果都仅有其“排除警报责任”的知识 | 不把 Canon 自动复制成所有人的知识，也不改 normalizer 伪造缺失候选 | 本轮补充调用为 MODEL_UNAVAILABLE，无输出；这项漏提取仍待验证，不能归因于预算或声称已修复 |
| 第五章 Plan v2 将受限核查、如实回报、分工作为三场，重复边界论述；原 Draft 的审阅也确实发现程序化对白 | 尝试 Planning v13，仅替换原容量指导段落，用现有 conflict / key_change / exit_condition 检验选择及后果、相邻场景是否重复 | 一次冻结输入对照增加了获准查阅和实际同行，但仍重复决定共同前往，并把不测试铜盒写成一场；保留 EXPERIMENTAL，默认仍 v12 |

Memory 的核验器、六种类型、版本/事务/权限校验均未更改。Model Profile 的模型、
采样参数、Provider、超时保持；新 profile 只改变身份和输出上限，旧 `lingzhi-structured`
hash `9ae0b152887db3ea647ff150774605278c53953702322e1cde08dc0cbc5bec47` 保留。
历史 A07 v1、Writer、Planner 和 Review 仍使用原配置。Worker 的上下文预算预留与实际
HTTP 请求从同一个 profile 读取上限，不另建执行器或自动扩容/重试。

## 真实调用记录

全部为独立诊断任务，使用实际章节的冻结输入与纯 AgentRuntime；没有走结果持久化。
新 task UUID 避免覆盖历史 capture。没有创建业务 AgentRun、Memory Proposal 或 Draft，
不能把诊断成功称作完整 Workflow 验收。失败不会自动循环重试；每次调整后至多一次。

| 次序 | 对照 | 结果 |
| --- | --- | --- |
| 1 | 第四章 / Memory v6 / 8192 | MODEL_OUTPUT_INVALID；安全日志明确 incomplete_max_output_tokens |
| 2 | 第四章 / Memory v7 / 8192 | 同样截断；保留失败证据 |
| 3 | 第四章 / Memory v7 / 16384 | SUCCESS；输入 22919、输出 8691；7 条候选通过精确证据与历史上下文归一化 |
| 4 | 第五章 / Planning v13 | SUCCESS；输入 23684、输出 6338；Schema/Authority/精确来源及约束检查通过；未批准或生成正文 |
| 5 | 第三章 / Memory v7 / 16384 | MODEL_UNAVAILABLE；无响应正文或 usage，未重试 |

总计 **5 次，2 次成功、3 次失败**。MODEL_UNAVAILABLE 只能证明 Provider 调用未完成，
不能从现有记录断言具体网络故障。第四章先明确截断，再单独调整说明长度，最后只调整
输出预算；后两次编译的 Schema、非追踪 Prompt 和源项均一致。模型默认采样不能保证
确定性，因此这是一组容量诊断，不是统计上的生成质量 A/B 结论。

## 第四章候选实际变化

原正式提取 5 条。本次诊断 7 条：

| Candidate | 类型 / 主体 | conflict_status |
| --- | --- | --- |
| t417_verified_record | CANON_FACT / T-417，合并记录已有字段和登记缺口 | NONE |
| linlan_holds_t417_original | CHARACTER_STATE / Lin Lan，原件与留档抄录 | NONE |
| guche_holds_t417_copy | CHARACTER_STATE / Gu Che，持有抄件 | NONE |
| linlan_knows_t417_record | CHARACTER_KNOWLEDGE / Lin Lan / KNOWS | NONE |
| guche_knows_t417_record | CHARACTER_KNOWLEDGE / Gu Che / KNOWS | NONE |
| courier_whereabouts_update | OPEN_THREAD / Missing Courier / OPEN | STATE_TRANSITION |
| guche_verify_locker_records | OPEN_THREAD / Gu Che / OPEN | NONE |

变化是补出持有人和各自有证据的知识，并非用候选数量证明完整。原件和抄件明确分开，
调查计划仍是 OPEN，没有写成已执行事实。未知投递结果、私有暗号和失踪者去向没有被
当作新知识。现有完整性缺口（第三章见证知识、旧承诺的履行/关闭）尚未全部验证。
所有新候选只在私有诊断文件，未替换原正式版本，也没有绕过 Human Confirmation。
历史只读归一化不能代替正式 Service 的 freshness、事务确认和后章检索验收。

## Planning 实验与验收范围

v13 增加“获得监督查阅机会、实际共同前往”，比旧 Plan 停留在“请求待回应”有变化。
但 S2 先决定共同核查，S3 再决定共同前往；“时间有限”没有提供具体等待代价。
S2 的“不测试铜盒”仍把保护边界当成剧情。删除该场而保留现状交代，主要行动仍成立。
“三场支撑 2000–2500 字”的假设未被充分支持。独立复核同意上述判断，因此 v13 只以
EXPERIMENTAL 留存，不启用为默认，也不追加 v14 继续试探。没有给 Writer 新增禁令。

新发现：当前五章的实际 `workflow_definition_version` 全部为 **3**；
`services/exploration_policy.py::supports_exploration` 仅在版本 4 启用探索。
第五章 Brief 为 MEDIUM 且允许 LOCAL_CONFLICT，但当前旧 Workflow 不会执行这个环节。
这是实际覆盖范围缺口，不足以证明缺少探索就是所有重复正文的根因。不能把旧五章的
结果宣称为 NOVEL-013/014 的完整真实验收，也不能直接修改已完成 Workflow 的版本。

下一轮按顺序：
1. Provider 恢复后，以已保存第三章冻结输入补核见证知识；不重新生成正文，不把知识自动继承自 Canon。
2. 用现有 v4 Creative Exploration → Planning 链路建立有来源的独立对照，固定实际批准 Profile 和合法前章状态；不得把 fixture 偏好冒充实际批准值。
3. 再比较未经人工反复修改的首稿与第一次审阅：信息重复、无效段落、人物选择、实际后果和知识边界分别记录。当前没有新首稿，**写作效果改善尚未验证**。

## 文件与验证

产品变更：
- `backend/novel_os/prompts/tasks.py`
- `backend/novel_os/providers/profiles.toml`
- `backend/novel_os/prompts/library/task_template/extract-chapter-memory/v7/`
- `backend/novel_os/prompts/library/task_template/plan-chapter/v13/`（EXPERIMENTAL）
- README、PROJECT-STATUS 与本报告。

本地必要回归新增 `tests/test_memory_output_budget.py`，检查 A07 实际请求预算、模型/采样
不变、其他任务及历史 v1 隔离。现有 Memory/Planning 合同测试的最新版本断言同步更新。
测试代码仍按用户历史要求不提交。没有新依赖、迁移、表、字段或公开 API。

- 本轮相关回归 **236 PASS**（包含 Provider HTTP mock；不代表真实模型成功率）。
- PostgreSQL 状态版本历史及事务回滚 **2 PASS**。
- 独立复核定向测试 **15 PASS**；生产差异未发现阻塞。
- Ruff check / format --check、git diff --check 通过。
- 空闲时重启项目 Worker，PID 54017 → 56738；加载 Memory v7 / 16384，默认 Planning v12；API 数据库健康和前端均 200。首次立即读取 PID 早于 launchd 完成替换，稍后只读确认成功，没有再次重启。
- 提交前先前修复另有后端 134 PASS、前端 49 PASS、build/lint 通过，不能简单相加成唯一总用例数。
- 首次扩测的两个失败为已有旧 Prompt 版本断言；保留历史 hash 断言、更新最新解析版本后复跑通过。
- 与前轮完整快照核对：批准 Profile v3、五个 Chapter 完整对象、全部 22 条正式 Memory 均未变化，五个 Workflow 均 COMPLETED，无 PENDING/CLAIMED/RUNNING 任务。

原始输入/结果、编译 Prompt、模型配置、日志及校验快照保存在
`backend/.runtime/continuity-next-20261018/`（不入库；SHA256SUMS 保留证据索引）。
本报告不等同全量回归或五章文学验收通过，未提交测试带来的 fresh-clone 复现限制仍存在。
