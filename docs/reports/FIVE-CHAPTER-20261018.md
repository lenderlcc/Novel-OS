# 五章真实验收推进：2026-10-18

本文保留恢复前的运行快照。第五章现已完成工作流，当前状态与剩余问题见
[顺序收敛修复报告](ORDERED-REPAIR-20261018.md)；下文的“现为”指本次原快照时点。

## 结论

**整体五章验收未通过。** 第三、四章已经完成真实生成、双质量审阅、版本接受和
Memory 确认；第五章首个 Plan 被测试代理拒绝，重规划返回 `SCHEMA_PARSE_ERROR`，
现为 `C90_BLOCKED`。没有第五章正文，没有继续调用或制造通过结果。

这次已取得足够的跨章节失败证据，后续应集中修复 Memory 完整性、验收输入和输出
诊断，不再反复修改第二章，不以增加章节或盲目重试代替修复。

## 范围与执行方式

- 用户授权“继续向下推进，全权由你来执行，中途不用找我确定”。正常版本审批、
  Draft 接受与 Memory 候选选择由助手通过现有 API 代办，原因中记录委托。
- 项目：`688d6d8a-e6ae-4197-a320-c3cc1b81bf32`；沿用实际批准的网文 Profile v3，
  record `2c20019e-3e5c-421f-9545-303d354f3291`，hash
  `ea711d16a708b30fb53c3e09e9b284c3dff0dd754b90184611769c34706e77e2`。
- 模型统一为 Lingzhi `gpt-5.6-sol`。本轮 20 次真实调用，19 个 Run 成功、1 个失败；
  每个任务 attempt=1，无技术自动重试。累计 input 397,853 / output 84,477 tokens。
  两次 Memory 正常弃置后重提取包含在 20 次内，不计为首轮提取通过。
- 复用项目限定的常驻 Worker。没有测试专用生成路径、直接 DB 写入、伪造 Canon、
  更换批准 Profile、修改第一/二章正文、提交 Git 或推送。
- 只读取场景的章节要求与验收断言；没有使用 recorded/fixture 正文替代真实输出。
  未自动创建人物画像；当前没有 Gu Che / Lin Lan 已批准行为画像，因此不能宣称声线
  或人物画像适配通过。

## 实际结果

| 章 | Plan / Draft | 质量审阅 | Memory / Workflow | 调用 |
| --- | --- | --- | --- | --- |
| 1 独享的暗号 | 原 Draft v4，不变 | 历史结果 | 原完成状态，不变 | 0 |
| 2 没有证据的怀疑 | 原 Draft v6，不变 | 历史结果 | 原完成状态，不变 | 0 |
| 3 真相与损坏 | Plan v1 / Draft v1 | Compliance PASS；Narrative PASS_WITH_WARNINGS | 6 条提交，C16_COMPLETED | 8 |
| 4 去掉错误事实 | Plan v1 / Draft v1 | Compliance PASS；Narrative PASS_WITH_WARNINGS | 5 条提交，C16_COMPLETED | 8 |
| 5 从记忆继续 | Plan v1 被拒绝；无 Draft | 只完成首轮 Plan Review | 重规划 SCHEMA_PARSE_ERROR，C90_BLOCKED | 4 |

第三章有机械事故、不可逆损失和责任判断变化，确有事件推进；尾部仍出现“这不是
全面的信任……”等关系解释和连续状态总结。警报 11:47 的排除证明依赖材料覆盖充分，
其说服力是独立阅读保留意见，不能仅凭 Compliance PASS 判为完全可靠。

第四章产生新物证 T-417、计划交接时间及目的地，Missing Courier 仍未找到；但持续
重复“线索不算结论”“证据只给了一半”等证明边界，并以“已见、待核、未知”收束。
自动 Narrative Review 也报出 OVER_STRUCTURED_DIALOGUE、OVER_EXPLAINED_REASONING、
AUDIENCE_STYLE_MISMATCH。因此程序感和重复论证已经在未反复修订的新章复现，
**不是第二章特例，也未证明生成质量改善**。保留两个首稿及第一次审阅，没有重写。

2000–2500 字是原 Profile 指导；本轮没有为补足字数扩写，也没有统一中英混排计数
口径来证明篇幅符合。不能把 Workflow 完成视为篇幅或人工文学质量通过。

## 已定位并修复的两个合同问题

### 1. Memory 更新引用混用 ID

第三章原 Proposal 用 logical_id 引用旧记忆，而 Normalizer 要求当前 record id。
原 Prompt/Schema 没有明确这一区别，导致铜盒状态及警报线程无法正常更新。

最小修复：`MemoryCandidate.existing_entry_id` 的 Pydantic 描述与新 Prompt v4 明确
复制相应 ContextItem.source_id；EvidenceRef 仍使用 logical_id + version。
不接受历史 record、subject_id 或 source_chapter_version_id；没有放宽冲突检查。
正常弃置旧 Proposal，再从同一已接受 Draft v1 提取，6 条可提交。

实际铜盒 v2：`d962a19c-7e3d-4f09-b0e8-31dfc0f09a4b`，保留 logical_id
`e0175964-b43c-472b-9ac5-6b57aaa548e4`，supersedes
`a4f06a06-98de-4e3a-9eab-40d151687ac6`；旧完好状态历史保留。

### 2. 新主体名称合同不明确

第四章第一次 A07 将正文中的 `T-417` 合成为 `T-417投递单`，名称不再是正文连续
原文，现有身份保护按 AMBIGUOUS 拦截。问题是生成合同没有说明名称及 alias 的原文要求。

最小修复：SubjectRef.name / aliases 描述与新 Prompt v5 明确 NEW 名称及每个 alias
必须原文连续出现，不附加类型标签，不合成翻译。保留实体解析保护。
正常弃置后从同一已接受 Draft v1 重提取并提交 5 条；原 Proposal 保持 CANCELLED。

两次修复均有真实后续提取验证，但并未解决提取完整性；重提取也可能丢失原先合法项。

## 仍未通过的关键目标

| 问题 | 证据与影响 | 判定 |
| --- | --- | --- |
| 人物认知更新漏提取 | 正式 Memory 无 Lin Lan 历史 SUSPECTS 及当前 KNOWS_NOT_RESPONSIBLE；正文已有对应变化 | FAIL |
| 已亲历事实被视为未知 | 第三章 Gu Che 卡住配重、合力抬齿条并目睹铜盒损坏；第五章 Plan 却因无 owned knowledge 判定他没有合法知识 | FAIL |
| 陈旧待办 | 第一章“共同核查尚未发生”的 OPEN 条目仍在，后文已发生共同核查 | 未解决 |
| 持有关系漏项 | 第四章取消 Proposal 曾含合法 linlan_holds_t417；重提取提交结果遗漏原件/抄件持有者 | 未解决 |
| 私有信息保持目标 | 第五章 Plan v1 安排 Lin Lan 显式讲出私有纸条，违背 expected-memory 中 B.X=ABSENT | 首轮 FAIL，已拒绝 |
| 第五章 Writer 知识隔离 | 尚无 Writer 任务与正文 | NOT_EXERCISED |
| 错误草稿污染→修订→仅最终版本入库 | 第四章未生成万能钥匙错误，只有真实 Draft v1；未人为注入污染 | NOT_EXERCISED |
| 初稿自然度与密度 | 第三/四章均复现解释性总结及重复证明；缺少批准行为画像 | 未通过 |

第五章的私有信息问题须准确归因：Plan 安排的是**显式分享事件**，并非已证明底层
Writer 过滤器泄漏。秘密必须继续保持的验收断言存在于 expected-memory.json，但原
第五章 raw_requirement 没有携带它。验收断言与运行要求不同步也需要修正，不能把一切
归因模型或过滤代码。拒绝理由已通过正常 Gate 送入重规划；此后的结果也不能冒称
未经人工提示的首轮成功。

规划漏记问题应修复带主体归属的经历/认知提取与状态更新，并复用原 CanonContextReader
的过滤策略。不能以向 POV 灌入全部 Canon、他人秘密或历史全文来消除“记忆缺失”。

## 第五章原失败：后续核查更正

本节于同日顺序修复时更正。先前“没有失败原文、无法确定字段”的判断不准确：
现有 `CapturingModelProvider` 已在本机私有目录保存失败响应，不需要新增捕获机制。

- Workflow `ab4021bf-4dcf-4e86-aca3-7b0160fbe260`，原失败 state_version 9。
- 被拒 Plan v1：`873a9549-5f28-4794-b1e0-b4fac5e89d61`。
- 失败 Task：`33e47d9a-9457-4619-81ff-a6319233b7bf`；Run：
  `a436d559-df00-4e23-84da-467a5fb84514`。
- schema `chapter-planning-result.v4`，耗时 52.586 秒，finish_reason=stop，
  input 23,449 / output 5,407 tokens。保存的响应能通过当时的 Pydantic Schema。
- 真正失败发生在 `PlanningResultService.validate`：旧 CP-004 v8 将所有主体身份
  以 P2 裁出上下文，输出 ID 与先前 Plan 的正确 Gu Che ID 一致，但校验要求该身份必须出现在当前
  快照中，抛出 ValueError，随后被统一归类为 SCHEMA_PARSE_ERROR。
- 使用原响应和原上下文离线重放已复现；新配置下同一规划输入的身份条目由 0 个
  变为 6 个。后续修复、调用和最终状态见
  [顺序收敛修复报告](ORDERED-REPAIR-20261018.md)。本报告其余快照保留原运行时点。

## 验证与变更文件

本轮新生产变更仅为：

- `backend/novel_os/memory/schemas.py`：字段合同描述。
- `backend/novel_os/prompts/library/task_template/extract-chapter-memory/v4/`、`v5/`：
  版本化 Prompt 及 manifest；历史版本不覆盖。
- `backend/tests/test_memory_contracts.py`、`test_memory_transition_contracts.py`：回归用例。
- 本报告及 `docs/PROJECT-STATUS.md`：实际进度。仓库原有其他未提交改动保留。

测试：Memory 合同/状态变化/不确定性 + Prompt registry/compiler **154 passed**，
2 条既有 Starlette/anyio 弃用警告。ruff check / ruff format --check（本轮 3 个 Python
文件）及 git diff --check 通过；非全仓库全量测试。没有新增表、迁移或依赖。
独立复核另运行 95 项相关用例，并用非本案例名称验证拒绝伪造 alias/错误 ID。
最终报告也经独立只读复核，调用数、失败终态和未覆盖项与运行快照一致。

运行核对：

- 第一/二章完整已接受版本对象及 current/approved 指针不变；Profile 完整对象不变。
- 原 7 条 Memory 与之前快照逐条一致；Ch3→Ch4 的原 13 条记录也未被改写。
- Ch3/4 WritingResult → Task → Run → PromptLineage → ContextPackage → 具体 Plan/Draft
  完整关联，正文 hash 相符；Review 绑定各自 Draft v1。历史 Proposal 可查。
- 20 个任务没有剩余 PENDING/CLAIMED/RUNNING；失败明确终止，常驻 Worker PID 48989 空闲。
- API health / DB health 正常、前端 HTTP 200。托管 Worker 仍限定本测试项目。

## 下一步收敛顺序

1. 已更正：复用现有私有捕获完成失败定位，修复身份预算和错误归类；见后续报告。
2. 修复 Memory 完整性：亲历知识、判断变化、已完成待办、持有关系。用现有真实已接受
   章节做离线提取/校验对照，保持旧记录不变，禁止为了全绿直接补数据库。
3. 对齐五章验收断言与实际输入；区分“事实为真”“人物知道”“本次不能披露”。
4. 完成上述后再做第五章受控恢复和独立新章初稿比较；保留首轮失败，不能用助理多轮
   修好的正文声称系统自然度通过。暂不新增功能、扩展架构或继续打磨第二章。

## 本地证据

完整版本化快照位于 `backend/.runtime/five-chapter-continuation-20261018/`（本地忽略目录）：
baseline、各章 input / plan-gate / first-review / completed、原始 Draft Markdown、
命令及响应、ContextPackage、PromptLineage、失败 Run 和 final-runtime-verification。
`chapter-5-plan-v1-observation.json` 保留拒绝判断及 assisted recovery 限制。
`memory-contract-tests-final.log` 保存 154 项测试结果。
这些是本机运行证据，没有声称已提交到仓库或可仅靠报告重建完整数据库。
