# Generation Chain — 最小系统修复与初稿对照准备

日期：2026-10-11。范围：代码与只读运行证据核实、最小修复、离线回归、生成对照设计。**真实模型调用 0；正文、批准偏好、正式 Memory 未修改；未推进第三章；未提交或推送。**

工程验证与文学效果分开：本报告不把 Mock/RecordedProvider 通过、Fidelity PASS、A06 自报 addressed 或反复修好的正文当作生成改善证据。

## 1. 当前实际证据

本轮重新从应用 API 导出，未沿用旧报告的状态，也未用 fixture 代替实际故事。基线位于 `backend/.runtime/generation-quality-20261011/`，详细文件 hash、版本、模型及 Prompt pins 见 [评测 manifest](../../evals/generation-quality/v0.1/manifest.json)。该目录被 Git 忽略，包含小说原文，但不包含 Provider 凭据。

| 对象 | 本轮观测 |
| --- | --- |
| 项目 | `688d6d8a-e6ae-4197-a320-c3cc1b81bf32` |
| 第二章 | `749f1271-6897-4797-9e58-e2d1da271a7b`《没有证据的怀疑》 |
| Workflow | `333a12fe-4bca-44c9-9852-2854a9eba424`，C09_INTERNAL_REVIEW / PAUSED，state_version 49 |
| 当前正文 | Draft v5 `e34d1169-7be2-47da-b776-e6b3432eee22`；未批准 |
| 比较用初稿 | Draft v1 `8d7a9b11-f48f-4594-99ef-13219d0f2e26`，不能用 v5 替代 |
| 第二章 Plan | 已批准 v1 `300683ff-7506-4c2f-979e-8c79644903d5` |
| Writing Profile | 实际批准 v3，hash `ea711d16a708b30fb53c3e09e9b284c3dff0dd754b90184611769c34706e77e2`，含 2000–2500 字偏好 |
| 第一章 | 最终批准 v4 `11454080-c744-4aeb-9296-a872d365e32f`，Memory 已提交 |

原 Writer run 为 `f1b4e862-67a0-4400-8299-5790a452408a`。用其原始 Context、历史 Schema 与全部 Prompt module pins 重建，compiled hash 精确相等：`11644bd46d61cdf5f58ac888599dc6bf84da42ff87d7d5b2c0424810cd3bd24c`。这是完整应用层消息证据，不宣称取得原始 HTTP 抓包。

## 2. 根因与修改对应

| 已确认问题 / 证据 | 最小处理 | 不做的推断 |
| --- | --- | --- |
| 原 Planner CP-004 v8 已有第一章批准正文与五条 Memory；计划仍把前章已存在的时间疑点作为本章推进。原 Plan Review CP-004R v4 却没有前章正文或正式 Memory，缺少独立比较的材料。 | 新增 CP-004R v5，复用现有 `previous-approved-chapter` 与 `committed-memory` reader。前章正文如存在为 P0，不能预算静默丢弃。探索路径 CP-004 v10 补相同批准历史，旧 Plan 不再充当“已经发生”事实。 | 不能声称 Planner 从未收到前章，也不能保证增加证据后模型必然识别重复。 |
| 当前旧 Planning 合同只接受可执行 Plan；表达 NEEDS_HUMAN 会在 Service 被拒绝，材料不足没有合法停下的结果。 | Planning Schema v4 增加有类型的 `planning_clarification` 分支，复用现有 Ambiguity、Audit、C90 BLOCK 与 `correct_requirement`。不生成假 Plan、不改审批指针、不派下游任务。 | 没有增加平行引擎、澄清表或自动补充设定。 |
| 原 Writer 输入确实有批准的网文 Profile，但 `character_id=null`，实际库缺 Gu Che 正式身份与其知识绑定，两人无批准行为画像。 | 保留 Knowledge Firewall；新 Planning v12 对明确单一限知要求无法绑定的情况给出具体澄清，不悄悄降级 POV。组合回归证明合法 POV 知识、关联 Canon 与批准画像可同时进入最终 Writer 消息。 | 缺画像是数据缺口，不应被说成全部文笔问题的根因；普通未指定/多 POV 不一律阻断。 |
| Writer Plan 同义字段重复投影、旧 Review 缺修订目标证据属于此前已修复但需复核的链路缺口。 | 保留并回归已有 CP-005 v8 无损去重、CP-006 v5 精确版本的修订诊断输入，不另建路径。 | 无损去重不删除事实；不把第一章含秘密的全文灌入 Writer。 |
| 原 Narrative Review 已指出程序化对白、规则外显及总结旁白；后续 v5 只有 Fidelity 与 A06 addressed，没有执行独立 A05 审阅。 | Narrative v6 在原流程中校准信息/选择/后果、邻接段落与行为动机的判断，保留局部 P2 与核心 P1 差异。CP-006 v5 提供冻结用户反馈、原文段落、修订目标，A05 独立判断。 | 不说“审核完全没发现”；不把偏好统一升级 MUST；不自动启动当前暂停任务。 |

原 Plan Review Context：`437d68bc-2971-4422-b518-b849c5724d61`；原 Planning Context：`44d2b760-eb76-49ba-8511-597b4d6ee579`。完整快照均在基线导出中。

### 具体正文与审核证据

- 第一章结尾已确认记录时间不合，并安排继续调查，铜盒完整。第二章不能仅把再次确认这一点称为新发现。合作范围改变、付出代价或实际行动也可以推进，不强制新增 Canon 真相。
- 第二章初稿第 55 段“他不知道她是否还有别的材料，也没有凭她短暂的停顿猜测”，把知识边界显式解释给读者；第 77 段再次声明不打开铜盒；第 80 段重述调查与怀疑仍未结束。
- 原 Narrative run `14ead76e-3903-435a-8b5a-6fe08412b634` 已引用这些问题，给出 OVER_STRUCTURED_DIALOGUE、REQUIREMENT_VISIBILITY_BIAS、AUDIENCE_STYLE_MISMATCH 等 P2。因此问题不是只做合规检查。
- 当前 v5 第 68 段已经展开核查，69、72–74 段又汇总材料开放、合作与未决状态。其六项 addressed 和 Fidelity PASS 没有独立证明删减目标或衔接质量达标；v5 的 Narrative task 未执行，不能引用 Draft v1 Review 为其背书。

篇幅 2000–2500 字与有限事件容量可能加重填充，这是**合理推测**，尚未通过固定其他变量的生成对照验证。本轮不改批准 Profile，也不增设机械场景数/字数硬阈值。

## 3. 上下文缺失分型与处理

| 类型 | 当前证据 / 现有机制 | 处理 |
| --- | --- | --- |
| 资料不存在或未批准 | 本项目 Gu Che 身份/知识及两位批准行为画像缺失；不能由当前空 Context 单独推断全部历史状态 | 不编造、不自动批准。明确 POV 无法绑定时用 Planning 澄清；可安全推断的普通资料缺口仅记录 assumptions/risks。 |
| 检索未选择 | 原 Plan Review profile 根本没有前章正文/Memory selectors；Writer Plan 缺 POV 导致无合法 owner | 修 Profile 选择；不把资料“不在输入”误报成“世界里不存在”。 |
| 权限隔离 | Writer 仅取 POV 本人合法知识/状态、关系，以及明确 KNOWS 关联事实；他人秘密、未来事实不允许进入 | 保留原 reader/filter；测试同时验证正向召回与负向隔离，不以放宽权限提高召回。 |
| 预算裁剪 | 原 Writer excluded_items 为空，无本次所涉预算丢弃证据。现有 ContextEngine 记录 LOW_PRIORITY / budget 排除，P0 超限阻断 | 延用现有预算与缺失错误；新增 Review 前章证据 P0，不静默删掉后假装检查完成。 |

历史 SourceSnapshot 主要保存来源指纹，不完整记录所有 SQL 前置过滤原因，无法事后重构每个未返回记录的精确原因。本轮明确保留该证据限制，不新建泛化诊断系统。当前批准身份/画像与已保存实际 Prompt 分别核对，不能相互替代。

基于真实第二章原 Plan Review/Planning 快照，仅在内存组装新版 CP-004R v5：READY，context 估算 58,502 + Prompt 开销 22,875 + 输出预留 8,192，小于 100,000；前章 v4 与四条允许 Memory 被选入，另一条 Character Knowledge 仍被既有 policy 排除。见 `plan-review-prospective-budget.json`。这是离线预算证据，不是真实新 Review。

## 4. 代码与版本边界

本轮新增/修改：

- `backend/novel_os/agents/planning_schemas.py`、`agents/registry.py`：Planning v4 专用澄清分支及旧 v3 pin。
- `backend/novel_os/services/planning_results.py`：完整来源/锁检查后记录澄清 Audit，复用 BLOCK。
- `backend/novel_os/services/context.py`、`context/profiles/CP-004.v10.json`、`CP-004R.v5.json`：历史证据选择。
- `backend/novel_os/prompts/library/task_template/plan-chapter/v12/`：可执行 Plan 与具体澄清分支一致，不凭篇幅不足自动升级重大风险。
- `backend/novel_os/prompts/library/task_template/review-chapter-narrative/v6/`：段落作用、邻接因果及重复信息校准。
- 相关测试文件与 `evals/generation-quality/v0.1/` 初稿对照材料；本报告。

测试改动清单（均位于 `backend/tests/`）：`test_planning_clarification_contract.py`、`core/workflow/test_planning_clarification.py`、`test_planning_progression_contract.py`、`test_exploration_contracts.py`、`test_planning_contracts.py`、`core/workflow/test_planning_context_and_concurrency.py`、`core/workflow/test_exploration_context.py`、`context/test_context.py`、`core/quality/test_memory_context_isolation.py`、`core/quality/test_dialogue_acceptance.py`、`test_quality_dialogue_acceptance.py`、`test_review_revision_outcome.py`。`core/workflow/test_planning_regressions.py` 的 Repository 事务边界测试另改用文件相对路径，以便从独立测试配置目录运行。旧文件仅扩展相关断言/场景，不复制执行框架。

延用的前轮改动：Planning v11、Plan Review v7、CP-005 v8/`context/serialization.py`、CP-006 v5/`services/revision_context.py`/`repositories/revision.py`、Narrative v5。工作树另有之前任务的未提交修改，不在本轮冒称重新实现。

旧 Planning v3 保留历史 Schema/Prompt；旧探索任务使用 CP-004 v9，新 v4 使用 v10。已经保存的 Context/PromptLineage 不重写。尚未构建 Context 的旧 Plan Review 排队任务会按 registry 选择 CP-004R v5；不能宣称仅影响新建任务。长驻 Worker 缓存 registry，后续获准真实运行前应安全重建 Runtime 并核实际 lineage；本轮不重启 Worker。

## 5. 验证结果

本轮使用独立测试数据库、Mock/RecordedProvider 和无真实凭据的测试配置；不操作正式项目。

| 验证组 | 结果 | 本机证据（均在基线目录） |
| --- | --- | --- |
| Planning 澄清、来源/锁负向、批准历史隔离、探索/Review 实际 Context | 72 passed | `planning-targeted-evidence.txt`，原 stdout 在本轮工具记录，摘要明确注明 |
| Context、Schema、历史 pin、预算与反馈诊断 | 227 passed + 1 通过复跑 | `contract-context-tests.log`、`context-registry-rerun.log`；初跑遇旧 latest=9 断言，更新为新版 10 后该项通过 |
| Planning 补充纯离线组 | 105 passed（与上两组有重叠，不累加） | `planning-unit.log` |
| Writer 最终提示词的合法知识/Canon/批准画像组合及隔离 | 3 passed | `writer-context-tests.log` |
| Narrative 等级校准、历史兼容、修订反馈与三个真实 API/RecordedProvider 场景 | 54 passed（含上述 Context 组的 8 项反馈诊断，不累加） | `quality-targeted-evidence.txt`，明确是执行摘要而非原始日志 |
| Workflow 扩展回归（Plan、探索、锁、并发、回滚、修订后独立 Review） | 66 passed + 1 通过复跑 | `workflow-regression.log`、`repository-boundary-rerun.log`；初跑仅源码相对路径查找失败，测试改为文件相对路径后通过 |
| Ruff check / Ruff format --check | PASS / 457 files already formatted | `ruff-check.log`、`ruff-format.log` |
| git diff --check | PASS | `diff-check.log` |
| 两案历史 Writer Prompt 重建 | 2/2 exact hash match | 各案 `writer-prompt.json` |
| 实际章节、Workflow、Profile、Memory 与 16 个基线文件 | 9/9 一致性检查通过 | `final-state-check.json` |

测试组存在交集，因此不把各组数字相加伪称唯一用例总数。现有 FastAPI/Starlette httpx 与 AnyIO 弃用警告未在本任务扩大处理。没有新增数据库结构或 migration。

独立复核未发现 Authority 绕过、旧 Plan 指针覆盖或新增平行审核路径。Schema 只允许重大、低置信度且无法安全推断的澄清；具体自然语言是否构成材料不足仍需要模型/人工判断，离线 Schema 测试不能证明模型每次都能正确识别。

## 6. 真实效果验证计划与未完成证据

详见 [生成对照方案](../../evals/generation-quality/v0.1/README.md) 与 [人工盲读表](../../evals/generation-quality/v0.1/human-evaluation.md)。已冻结第二章原始 v1，以及另一个项目第六章《继续2》的唯一 Draft v1（revision_count=0）；两个历史 Writer Prompt 均精确重建，2/2 hash 相等。

后续分两段：两案 A/B Planning+Plan Review 最多 8 次；人工认可评测 Plan 后，4 次 Writer + 8 次双路质量审阅，完整最多 20 次单次调用，无自动重试。它们是隔离评测，不推进正式第三章，也不伪造正式审批或 Memory。

模型固定 Lingzhi `gpt-5.6-sol`，每案固定自身实际批准 Profile、输入和无关参数。两个案例 Profile 不相同，不能跨案直接解释字数因果。缺失资料不能只给补丁组补齐；新增资料必须双方同用且标记新实验。组合对照若改善，仍需单变量消融才能归因单个调整。

**Engineering：本轮所选回归 PASS（含上述两项修正后复跑），不是全仓库完整验收。AI Behavior：NOT_RUN。Human Prose：NOT_EVALUATED。** 原第二章修订授权不能扩展为另一项目及新的系统对照授权；本轮未付费调用。下一步若执行，需明确这两个案例的外发范围与分阶段额度。当前不要求用户填写泛化人物问卷；只有真实 Planning 无法合法确定具体身份/已知信息时，才呈交针对该决策的具体问题。
