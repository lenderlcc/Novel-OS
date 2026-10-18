# 探索引用与 Brief 版本绑定收敛

2026-10-18，继续执行上一轮的工程收敛顺序。开始时本地与远端 main 均为
`f14b7c8432e17ae7d4223a5f69019e098b0de461`。本轮只修已证实的探索输出合同问题，
并继续核对 Memory 覆盖；不改第二章正文，不新建测试项目或推进第六章。

## 根因与最小修改

1. 服务要求全部已选 A3 来源及既有锁定依赖被引用，包括仅供身份识别的实体；
   原 Prompt 只概括为 locked/Canon evidence，没有明确列出必需三元组。
   上轮完整返回的结果漏掉 2 条 Canon 与 6 个身份，格式通过但无法被服务接受。
2. 提取到 `domain.planning.exploration_required_refs` 作为输入和验证的共用规则：
   当前 Brief、全部 A3、原有四类 locked dependency。没有减少任何必需来源。
   CP-004E v3 将该清单序列化给模型，预算估计与最终 Prompt 使用同一序列化路径。
3. v3 单次复验补齐引用，但模型将 Brief 的逻辑 ID（workflow ID）填入 `brief_id`，
   而该字段要求具体版本记录 ID（source_id）。结果被拦下，没有进入 Planning。
4. 保留已运行的 v3，新增 CP-004E / Prompt v4：显式提供 `brief_record_id`，
   并区分结果的版本绑定与 `source_refs` 的逻辑引用。没有在结果中自动纠正 ID 或补引用。

新版本缺少必需引用走既有 `SCHEMA_PARSE_ERROR` 输出验证路径；伪造来源、错误版本、
错误 Brief 绑定、锁和权限检查继续拒绝。CP1/2 保留旧投影与错误行为；CP3 保留这次诊断输入。
Pydantic 继续定义输出形状，依赖当前 Context 的动态集合覆盖仍由原结果服务语义验证。
没有新增代理、接口、表、迁移、依赖或另一套结果处理路径。

改动文件：

- `backend/novel_os/domain/planning.py`：共用必需引用规则与原锁定来源集合。
- `backend/novel_os/context/serialization.py`：版本化清单及 Brief 记录绑定；纳入既有预算。
- `backend/novel_os/services/planning_policy.py`：复用同一锁定来源集合。
- `backend/novel_os/services/exploration_results.py`：共用引用检查，保留权限拒绝。
- `backend/novel_os/prompts/runtime.py`：按保存的 CP1/2/3/4 精确选择对应 Prompt。
- `backend/novel_os/context/profiles/CP-004E.v3.json`、`CP-004E.v4.json`。
- `backend/novel_os/prompts/library/task_template/explore-chapter-concepts/v3/`、`v4/`。

## 真实验证

沿用上轮第五章历史探索诊断的全部 29 项实际来源，逐项验证 ContextItem 完全相同；
没有重查后加入新剧情信息。批准 Profile v3、模型 `Lingzhi / gpt-5.6-sol`、8192 输出上限、
任务约束均保持；仅 Prompt/Context 合同与诊断 task ID、包 ID、hash 变化。
保留其中已有的用户规划指令，不能将结果称为完全无人介入的连续性表现。

| 运行 | 引用覆盖 | Brief 绑定 | Provider | 后续处理 |
| --- | --- | --- | --- | --- |
| 上轮 CP2 / Prompt2 | 缺 8 项 A3 来源 | 正确 | 完整返回 | 拦截 |
| 本轮 CP3 / Prompt3 | 必需 17/17，引用 20 项均精确 | 错填 logical_id | 20711 输入 / 5600 输出，56.764s，stop | 拦截，定位 ID 混用 |
| 本轮 CP4 / Prompt4 | 必需 17/17，引用 26 项均精确 | 精确 source_id | 20780 输入 / 6068 输出，62.069s，stop | 组件合同通过 |

两次调用各执行一次，没有自动重试。最终返回 3 个合法数量的概念，选中
`C1_TraceableCheck`，Schema、Runtime Authority、精确引用、必需集合、Brief 绑定均通过。
原始响应、首次失败和后续成功分别保留，没有覆盖历史 capture。

这是**冻结历史输入的真实组件验证**。没有在已完成的旧 Workflow 中伪造新 AgentRun，
没有执行正式结果持久化/freshness，也没有保存新 Plan 或调用 Writer。
正常 Worker → 服务 → 持久化 → Planning 的连通性由隔离数据库的集成测试覆盖。
不能将二者合并声称完整真实 v4 Workflow 已验收通过。

选中概念仍以“正式发起可追踪查询、等待结果”为核心。它区分了启动与结果未回，
但不能据此证明事件容量充分、程序感降低或首稿改善。正式 Memory 仍没有近期章节摘要，
完整 013R repetition case 的先决条件依然不满足；稀疏历史组件验证不是该 case PASS。

## 回归与独立复核

- 最终针对性回归：**264 PASS / 1 SKIP**。68 项探索/版本/事务测试及 196 项共享
  Context/Prompt/合同测试；跳过项是需另行 opt-in 的真实 Provider pytest。
- 覆盖必需集合含身份与锁定来源、可选引用仍可选、预算包含新字段、历史版本路由；
  正常 Worker 下漏引、伪造 ID、错来源版本、错 Brief 绑定不产生探索记录和下游 Plan。
  正常完整引用仍按原流程保存并推进。
- `ruff check`、`ruff format --check`、`git diff --check` 通过。
- 两类既有 Starlette/AnyIO 弃用提示，无失败；未宣称全仓库测试通过。
- 独立只读审查确认共用规则、版本兼容和权限边界无阻塞；追加 Brief 绑定复核通过。
- 测试按用户此前要求只留本机、不提交。因此新回归无法从纯远端 checkout 完整复现，
  这一发布限制未被消除。配置、密钥、原始输入输出和日志均不提交。

## 继续执行：Memory 覆盖核对

复用第三、四章已有 v7 成功输出与实际已接受正文，按 8 项有证据的连续性风险核对，
没有再随机调用模型。两个新增确认的缺口属于同一类：

- 第三章第 37–40 段分别写 Lin Lan 拖出、检查铜盒，以及 Gu Che 看着变形的铜。
  输出有铜盒损坏 Canon，却没有两人的对应知识候选。冻结当前 Memory 中也没有这些
  知识可供去重。Gu Che 的可记范围只包括亲见损坏，不能自动扩展到 Lin Lan 的内部检查
  结论或私密纸条。原始候选与 normalized 相同，不能归因于归一化删除。
- 第三章两人确认 Gu Che 非警报责任方的知识有提取；第四章原件/抄件持有人、各自核对
  信息及未执行核查承诺也有提取。因此不是所有 owner knowledge 都失效。

这是一份选择性风险核对，不是完整性分数。现有 Prompt v7 已要求分别提取实际见证者；
仅再写一条相同禁令、复制 Canon 为知识、自动补候选都不能证明问题已修复。
本轮没有改 A07、没有提交新的 Memory，提取完整性仍为 FAIL。

下一步先在现有 A07 内验证提取顺序/覆盖方法，继续固定第三、四章输入、批准偏好及模型，
同时检查遗漏与误加；未经真实对照不能提升默认合同。随后再做有效 Plan 与首稿的
阅读质量对照，不把本次引用可靠性 PASS 当作写作质量 PASS。

## 数据与证据

前后 API 快照确认已批准 Profile v3、五章对象、22 条历史 Memory 完全相同。
五个 Workflow 均 COMPLETED，无 PENDING/CLAIMED/RUNNING 任务。没有审批、Memory commit
或第二章正文修改。

原始证据位于本机 `backend/.runtime/exploration-contract-20261018/`：
`input.json/result.json/validation.json` 保留 v3 失败；`v4/` 保留最终单次调用；
`memory-coverage-audit.json` 保存原文引文与来源 hash；最终回归日志、运行状态及
`SHA256SUMS` 单独留存。
