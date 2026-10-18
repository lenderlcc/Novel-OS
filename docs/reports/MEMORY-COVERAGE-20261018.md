# A07 Memory 覆盖与来源合同对照

## 结论

2026-10-18 继续工程收敛。开始时本地及远端 main 都是
`949a28e27f1c693786784b921c7ea9d419893d4d`，此前修改已推送。
本轮使用真实第三章已接受正文及原冻结 Context，执行两次不同变量的 Lingzhi /
`gpt-5.6-sol` 组件诊断；没有重写正文、重开已完成 Workflow 或修改正式 Memory。

**知识覆盖出现改善，整体仍未通过。** 新方法输出了此前漏提的 Gu Che 可见损坏知识，
并区分 Lin Lan 的检查结论；但一条 Authority 来源 ID 错误，现有证据校验拒绝整批结果。
因此 `memory-quality/v2` 和 `extract-chapter-memory/v8` 都保留 **EXPERIMENTAL**，
默认仍为 Quality v1 / Task v7。第四章只准备了输入，没有调用。没有将实验结果落库或宣称修复完成。

## 已确认根因与边界

1. **遗漏在生成阶段，不是 Normalizer 删除。** 上轮 v7 返回 7 条，原始输出和归一化一样；
   正常结束、未碰到 16384 输出上限。第三章第 37、40 段明确有 Gu Che 协助取盒并看见变形，
   第 37–38 段有 Lin Lan 实际检查，输入中也没有对应已存知识可供去重。
2. **输入目标存在张力。** Task v7 第 19–21 行要求保留有据的持续变化与实际知情者，
   Quality v1 第 1 行却写 `not coverage`，并偏向短列表。两层确实同时进入实际编译提示词。
   这是已确认的目标表达矛盾；不能凭少量调用证明它是唯一原因。
3. **仅取消覆盖降权不够。** 第一阶段只改 Quality，Lin Lan 知识出现、Gu Che 仍缺失。
   第二阶段才改提取方法：按事件阅读，再分别确认每人的获得行为及较窄命题，而非先选少量结论。
4. **最新失败是引用完整性，不是知识权限。** 模型给 Gu Che 的命题限于亲眼看到“严重变形”，
   没有升级为 Lin Lan 的完整技术结论；但该候选一处 `authority_checks.source_ref.logical_id`
   不属于输入。`validate_evidence` 正确拒绝，不能自动修 UUID、降低边界检查或补造 Canon。

代码依据：`backend/novel_os/memory/policy.py:35` 的逐段引文和精确边界集合校验；
`backend/novel_os/prompts/tasks.py:214` 的现有任务与版本选择；
`backend/novel_os/prompts/library/task_template/extract-chapter-memory/v7/content.md:19`；
`backend/novel_os/prompts/library/quality_profile/memory-quality/v1/content.md:1`。

## 最小修改

| 文件 | 目的 | 默认行为 |
| --- | --- | --- |
| `quality_profile/memory-quality/v2/content.md` 与 manifest | 将准确性、Authority 与有证据的覆盖分别要求；Canon 与实际知情记录不互相替代；不设置数量指标 | EXPERIMENTAL，未启用 |
| `task_template/extract-chapter-memory/v8/content.md` 与 manifest | 在完整保留 v7 合同基础上，先核对事件、实际获得行为和较窄知识，再去重序列化 | EXPERIMENTAL，未启用 |

两个路径均位于 `backend/novel_os/prompts/library/`。没有改 Schema、Service、Normalizer、
Authority、Provider、表、迁移、依赖或 API；没有新增并行 Agent/审核器，没有案例名特判。
历史内容及哈希保持不变，显式 pin 才能选择实验版本。
如未来晋升 Quality v2，必须同时给旧 `chapter-memory-result.v1` 任务固定 Quality v1，
避免旧任务因当前无版本引用而改变历史合同；本轮尚未晋升，无需改旧任务。

## 实验控制与结果

保留原第三章 accepted Draft v1、批准 Profile v3、17 个实际来源和模型配置。
第一阶段仅替换 Quality v1→v2；第二阶段固定 Quality v2，仅替换 Task v7→v8。
新诊断 task/package UUID 和相应 hash 不同，其余来源 payload、快照、模型、Schema 相同。
增加方法文案后重算预算，未丢弃任何来源。没有使用 fixture 或本章未来 Memory。

每次复用现有 AgentRuntime / PromptCompiler / Pydantic 输出合同；第一阶段继续执行
现有精确证据校验和只读历史归一化。第二阶段在证据校验失败处停止，没有进入归一化。
这些是诊断执行，不是完整业务持久化/freshness 验收，也没有新的正式 AgentRun。

| 版本 / 阶段 | 本轮调用 | 输出 tokens / 结束 | 结果 |
| --- | --- | --- | --- |
| Q1 / T7，上轮冻结基线 | 0 | 7315 / stop | 7 候选，双方铜盒知识漏提 |
| Q2 / T7，Quality 单变量 | 1 | 7730 / stop | 9 候选，补出 Lin Lan 检查知识；Gu Che 可见损坏仍缺，覆盖 FAIL |
| Q2 / T8，提取方法单变量 | 1 | 9393 / stop | 12 候选，目标知识补出；1 个来源 ID 错误，整体 FAIL_VALIDATION |
| 第四章 Q2 / T8 泛化对照 | 0 | NOT RUN | 第三章校验失败，未继续付费执行 |

第一阶段输入 23289、总计 31019 tokens，延迟 57077 ms；第二阶段输入 23532、
总计 32925 tokens，延迟 65421 ms。两次都收到完整响应，非网络错误或输出截断。
第一阶段 9 候选的 16 条引文及 45 条必需边界检查通过；只读归一化为 2 个
STATE_TRANSITION、7 个 NONE，没有直接提交。

第二阶段独立核验 12 候选、22 条引文、12 个正文 source_refs、60 条边界引用：

- Gu Che：仅知道铜盒严重变形，证据第 40 段“Gu Che看着那团变形的铜”。
- Lin Lan：实际两次检查后知道无法恢复原先封闭状态，证据第 37–38 段。
- 两人各自获知 11:47：Lin Lan 的核对/写入（44–45），Gu Che 的共同时间线及同步复核（49–50）。
- 所有引文精确匹配；实体和现有记录 ID 无其他异常；没有把午夜纸条私密知识给 Gu Che、
  没有宣告真正责任方或信使去向，也没有将 Gu Che 的观察扩成技术检查结论。
- 唯一引用异常在 `gu_knows_box_deformed` 的关系边界：正确值
  `237717e0-835a-4cd5-9c86-707b5dcc8915`，实际输出
  `237717e0-835a-4cd5-9c86-70794b722ec3`。造成一条未知引用和一条必需引用缺失。

Provider/Runtime 的原始 `error_code=null` 保留；后续证据校验的 FAIL 单独记录，不能用
Schema SUCCESS 覆盖业务拒绝。没有改写原输出、自动补引用、重新抽样到通过。
这个样本的语义改善不能证明全章覆盖完备、第四章泛化有效或后续写作质量提高。

## 验证与数据保护

- 本地针对性回归 **156 PASS**（Memory 合同/状态变化/历史归一化/输出预算/Prompt 编译），
  113.58 秒；两条已知 Starlette/AnyIO 弃用警告。不把工程测试等同真实提取质量通过。
- Ruff check / format 检查通过（328 个产品 Python 文件）；`git diff --check` 通过。
- 新增本地测试验证两阶段单变量编译隔离，以及实验模块不改变当前/旧 schema 默认行为。
- 独立 fresh-context 复核了两个新模块、实际输入、第三章全部候选和第四章预定验收项。
- 前后 API 快照完全相同：批准 Profile v3、5 个 Chapter 完整对象、22 条历史 Memory。
- 5 个 Workflow 都为 C16_COMPLETED，无 PENDING / CLAIMED / RUNNING 任务；API、数据库健康，UI HTTP 200。
- 未重启服务：默认产品行为没有变动。没有新 Plan/正文、Memory commit 或第六章。
- 按用户此前要求不提交测试、原始私有输入/输出、本机配置及运行日志。测试留在本地的 fresh-clone 复现限制继续存在。

证据位于本机 `backend/.runtime/memory-quality-20261018/`：`before.json` / `after.json`、
阶段一 `chapter-3-{input,result,normalized}.json`、阶段二
`acquisition/chapter-3-{input,result,validation}.json`、调用日志及独立复核文件。
`acquisition/*-preparation-superseded.json` 是首次准备时对照 hash 选择错误的未执行输入；
已保留后重新准备，未发送 Provider，不计入调用。最终 SHA256SUMS 索引留在本机。

## 后续顺序

1. 先解决精确来源引用的生成可靠性，再谈默认晋升。复用既有 Context / 输出合同，
   评估从权威输入确定允许引用集合；不得从错误输出猜 ID，也不得把缺失检查自动视为 COMPATIBLE。
   现有严格拒绝行为保留，不新增第二套权限验证链。
2. 用已冻结第四章的持有人、实际读过的字段、未执行承诺做泛化验证；负例包括不能把
   持有抄件等同读完全部字段、不能传播私密纸条、不能提前关闭信使/责任人线。
3. 两章合同和语义同时通过才考虑晋升及正式新流程验证；不补写已完成五章的缺失记忆。
4. 然后进入有效 Plan/首稿对照。完整 013R 所需历史摘要仍未具备，当前稀疏历史组件诊断
   不能代替完整 013R，也不能代表五章文学验收通过。

基线、Quality 调整、方法调整三轮仍未达到整链路验收，按有界诊断原则停止本轮继续付费抽样，
保存实验版本和失败证据；不回到反复改第二章、不新增产品功能。
