# NOVEL-010 Revision Paragraph Binding Fix

日期：2026-09-28。范围：Revision 的段落证据输入、严格校验错误分类与工作台提示；未开始 NOVEL-011。

## 根因与真实失败复核

- Project `23c028ee-cd94-4965-af85-731e560c9633`，第 8 章 `hh`，Chapter `0db2fea7-db58-4cc6-9947-4fcee48bdb21`。
- Workflow `c96f61c2-da12-4b05-9051-073a63d7f079`，RevisionRequest `a3a3e128-cb7d-49b3-bc77-0ca8282d9b19`。
- Source Draft v1 `13a93dad-089e-429e-b2dd-59bffbcb5a7e`，Source Review v2 `6fce870e-ddf7-44ea-9420-34ee58a3c3d2`。
- 两次 Provider 输出均通过当前 Revision Plan Pydantic Schema，`proposed_changes=[]`、`memory_proposals=[]`；此次已不是先前的 proposal contract mismatch。
- Task `1807a250-e1e2-4416-b894-8f7f65a8e1cd` 的 3 处引文段落号错误：47→48、95→96、65→63。
- Task `7cbd175a-851c-48e8-8e77-57be3d7a7910` 的 2 处引文段落号错误：47→48、73→72。
- 引文本身在原稿中真实存在，但源稿共 100 段。Quality 输入有服务端编号表，Revision 输入没有，模型自行推算编号导致偏移。Fidelity 候选稿也缺少独立编号表。
- 对两个失败输出的**离线副本**仅校正对应段落号后，完整 RevisionResultService.validate 均通过；未将校正副本持久化，生产中也不进行自动重新定位或模糊匹配。

## 修复

1. 用现有 `paragraphs()` 切分规则生成 `{paragraph_index, text}` 表，保证生成与校验完全一致。
2. Revision 仅给 exact `target-version` 增加完整编号表；Fidelity 给 exact `revision-candidate` 增加独立编号表。正文与原版本 hash 不改变。
3. 发布新 Prompt：Planning v4、Execution v4、Fidelity v3；保留历史版本。要求复制服务端段落号和单段连续原文，引文不得拼接、跨段、改标点或自行数段；候选稿与源稿编号分别使用。
4. 严格的 evidence matcher 保持不变。Revision 专用 `REVISION_EVIDENCE_MISMATCH` 标识引用定位失败，和一般 Schema 错误区分；仍遵守原有有界技术重试机制。
5. UI 显示“引用证据定位失败”，Debug 显示实际阶段及 `Evidence Binding Failed`。Planning 失败时仍显示“修改任务未能开始。”
6. 新 CP-007 v6 将 UTF-8 保守预算设为 400000，覆盖完整源稿、候选稿及两个编号表；selectors、authority、version、future policy 均不变。v5 原文件不改，历史 RevisionRequest 继续按冻结版本执行。近 2 万字双正文与约 9 万 bytes 其他 P0 的回归载荷总量约 374133，低于新预算与已配置模型窗口。
7. 第 8 章现有 request 继续使用 v5，补编号后的 Planning 总预算估算 147864 / 240000，无删减。

未修改 Writer、Quality Review 判断、Authority、Fidelity 通过标准、Draft 不可变性或 Review 版本绑定；未增加依赖、数据库表或 migration。

## 验证记录

- 新增错误编号、重复引文、标题/空行切分、跨段/虚构/改写引文、源稿与候选稿独立索引测试。
- Repository/Service 集成验证 Planning 和 Fidelity 引用错误均阻断、不改 current_version、不意外重试。
- Mock 完整链路验证 Plan → Candidate → Fidelity → Draft v2 → Quality Review，旧稿内容保留，新 Review 绑定新 Draft ID。
- 最终生产代码下针对性后端测试：7 passed；编号与容量单元测试：12 passed。
- 前端单元测试：122 passed；eslint、类型检查与构建通过。
- Ruff check / format 与 git diff --check 通过。
- 宽范围浏览器测试遇到历史断言 `Draft v1 · DRAFT` 与当前 UI `Draft v1 · 当前` 不一致，已停止该无关批次；本次不修改产品文案迎合旧测试。
- 后端扩大回归：188 passed（含 Revision Output Contract、Fidelity、Context Budget、全部 core/quality）。该批在增加 v6 前启动；最后的 v6/target-only 补充由上述 7 项与 12 项针对性测试覆盖。
- Revision 专项浏览器回归：2 passed（真实浏览器 + 隔离测试库 + Mock Provider；正常新版本及 Fidelity 拒绝路径）。
- 独立复核已完成；发现的编号表体积回归已通过 v6 预算与 target-only 选择修复。

## 真实 Provider 验证

已更新 Docker Worker 并重启本机 Backend/Frontend。8000 与 5173 代理上的 health / health/db 均返回 200。Worker 加载 Prompt 4/4/3，运行范围 `chapter-quality`、`agent_max_attempts=1`，provider/model 为 `lingzhi / gpt-5.6-sol`。

对第 8 章原 RevisionRequest 执行了一次有界恢复，未重新生成 Chapter、Plan 或源 Review。5 个阶段均真实调用一次且成功，无重复调用或自动循环。

| 阶段 | Task ID | 结果 |
| --- | --- | --- |
| Revision Planning | `e8a75132-e0dc-456a-a91d-51148ac36283` | SUCCEEDED，20 条 preservation evidence，3 个 targets，0 unresolved |
| A06 Revision Execution | `f124e6a7-c102-4f3c-ac04-3775170344e1` | SUCCEEDED |
| Fidelity Validation | `7a7f37cd-8cf0-4597-bf70-df09cb798f56` | SUCCEEDED / PASS |
| A05 Compliance Review | `273db8eb-bc17-413e-a8fa-4b0b7faabf10` | SUCCEEDED |
| A05 Narrative Review | `0f1ebdee-1ad3-4cb1-87af-f8456539a85e` | SUCCEEDED |

版本与审阅核验：

- 旧 Draft v1 ID `13a93dad-089e-429e-b2dd-59bffbcb5a7e`；正文 hash `51943d1f3949bdba742870dcd5324da2ba843e4e312ed83ccd2790ddfe4cd235` 与失败前 Context 快照一致。
- 新 Draft v2 ID **`fd3046a6-40be-4560-a87e-e59d8b341ff8`**；`supersedes_id` 指向原 v1；hash `696b2b815d20f925f1d44d16f7cc9099ebecf525f05eacfc6dee1dbe5131f756`。
- `current_version=2`，`approved_version=null`，未代替用户批准。
- RevisionPlan `c7b275f8-1de7-4bb8-af29-24c4191b08dd`；Candidate `d6dfab26-c23b-4d1d-b338-82d443e2ec3b`；RevisionResult `9dc04431-ed13-4aa3-a43b-4bf8d3c612c6`，`accepted=true`，绑定新 Draft v2。
- Fidelity Context 中源稿 100 段、候选稿 92 段，分别按各自正文生成索引；源稿全文未改变。
- 新 Review 为 **v3**（先前已有 v1/v2），ID `3aabf408-2a44-4d40-adab-23b0d54b722d`，`chapter_version_id` 精确等于新 Draft v2 ID，结果 **PASS_WITH_WARNINGS**。没有再次审阅 v1。
- 最终 Workflow 为 `C11_INTERNAL_PASS / WAITING_HUMAN`，state_version=27；停止执行，等待人工验收。

Lineage 核验：

| 阶段 | AgentRun | ContextPackage | PromptLineage |
| --- | --- | --- | --- |
| Plan | `6de69666-1514-4754-9c4f-43da564675d5` | `9344c4ef-872c-4008-97a6-640689028de8` | `31faa4a5-94a6-4455-8ecf-ae9b69bc2056` |
| Revision | `c08e4ad8-11dd-4203-93ed-06f707234f6e` | `a72cfe39-8ac0-43b0-88dd-949dacb5a4cc` | `dd9219bf-adae-4367-b0b2-adb27785adc8` |
| Fidelity | `460b4893-8da5-4b61-8a8c-1f5cd6b6115d` | `15a156a7-e380-48c1-a680-649aa080ac55` | `e88879ea-51cd-4901-beb2-72c6fdda7b5f` |

原始失败输出、重试 event、最终 API 快照和测试日志保留在本机忽略目录 `backend/.runtime/`；未提交原稿、模型输出或测试文件。

Engineering acceptance：PASS。真实 Revision 引用协议与版本链路：PASS。正文质量仍需人工阅读；AI 结果 PASS_WITH_WARNINGS 不代替人工验收。
