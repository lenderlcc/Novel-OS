# NOVEL-012 — Memory / Canon Commit Engine

日期：2026-09-30。分支：`wfg/novel-012-memory-commit`。开发基线：`b726cb5`。本报告记录工程验证与真实模型/人工验收的不同状态；真实 Canon 提交需要用户确认，不以 Mock 或助手判断替代。

## 1. Background

此前正文、质量审阅与 Directed Revision 已有 exact-version lineage，但未形成用户确认的长期 Story State。本阶段建立 accepted Draft → A07 Proposal → 人工选择 → 原子 Commit → Completed 闭环。

## 2. Scope

仅 NOVEL-012。复用基础设施，无新依赖、环境变量、Vector DB、Redis、知识图谱、自动学习或发布功能。未提交/推送代码；测试文件留在本地，遵守此前不提交测试的要求。

## 3. Existing Memory Audit

已有 NOVEL-006 Context profile、MemoryQuery extension adapter、Authority、SourceRef、knowledge_scope/character_id；已有 Chapter current/approved 指针、v3 workflow、C14/C15/C16 enum、A07 enum、用户事件 fencing、根项目锁、AgentTask/Run/PromptLineage/ContextPackage 和审计。没有可用的正式 Canon commit store。保留这些能力，仅新增必要的业务持久化与 Service。

## 4. Memory Layers

A3：CANON_FACT / CHARACTER_STATE / CHARACTER_KNOWLEDGE / RELATIONSHIP_STATE；A6：OPEN_THREAD / DERIVED_CHAPTER_SUMMARY。认知记录的 Authority 不等于认知内容的真值。

## 5. A07 Memory Agent

A07_MEMORY、EXTRACT_CHAPTER_MEMORY、chapter-memory-result.v1。唯一 capability REPORT_RESULT。模型仅产生候选，不拥有 DB write / Canon overwrite / Profile mutation 工具。失败使用原错误分类和人工重试路径。

## 6. Chapter Finalization

用户接受 exact current Draft，Service 调整 approved pointer，冻结请求，进入 C14；Proposal 完成后 C15 等待人工。CONFIRM_MEMORY 原子进入 C16/COMPLETED。空集合也需确认。返回正文保留历史，未写 Canon；接受动作不撤销，修改仍创建新 Draft。

## 7. Extraction

只处理 CP-009 的已接受正文。Prompt 强调高价值未来连续性、避免装饰细节、主题推断和对话主张直接成为事实，允许空结果。纯文字语义质量单独验收，不由单元测试假装证明。

## 8. Candidate Schema

严格 Pydantic，最多40候选；稳定 ID、六种类型、subject/slot/value、state、epistemic、source/evidence、importance/layer/confidence/uncertainty、boundary checks。禁止客户端或模型赋 Authority/status/version，通用 proposed_changes 和 memory_proposals 限定空。

## 9. Normalization

NFKC 名称/别名、同批两阶段实体合并、项目内身份校验。模糊/跨类型/未出现实体拒绝自动消歧。语义 value 比较保留小数点，防止 1.5 与15误判重复。

## 10. Evidence

每项 source_ref 只能为当前接受的 ChapterVersion；最小精确摘录与1起始段落索引双重验证。Plan/Review/Feedback 可提供边界或诊断，不能成为发生事实的来源。

## 11. Character State

同主体属性追加版本；明确 state_before 匹配已有值时视为状态转移，否则为冲突。旧状态保留，当前查询排除被后续替代的版本；按章节时点查询恢复当时状态。

## 12. Character Knowledge

必须绑定 CHARACTER owner；KNOWS/BELIEVES/SUSPECTS/DOUBTS 分开。认知修正追加版本。known_fact_id 仅限 KNOWS，校验同项目、此前章节、当前有效 Canon 和相同 value。

## 13. Knowledge Firewall

Writer 仅检索已批准 Plan 所绑定 POV 的状态、关系和认知，以及其显式知道的 Canon。未知/多 POV 默认为无私有知识。CP-005 v6 移除上一章整篇和显式 ChapterVersion 原文，避免旧章原文旁路。锁定正文依赖仍验证 exact version/freshness，不再要求正文进入 Writer 内容包。

## 14. Relationship State

复用 typed state/version 链，支持人物关系属性的明确变化。未扩展社交图或新关系编辑器。

## 15. Open Threads

A6 检索提示，与已确认事实分离，不强制把临时动作/暂时情绪当长期任务。

## 16. Derived Summary

每章至多一份 A6 摘要；Planning 只取有限近期先前摘要；不向 Writer 无条件注入全局摘要以泄漏人物未知信息。

## 17. Duplicate Detection

按规范化实体、type、slot、value/epistemic/known-fact 关系比较。同批重复合并或记录 skipped；只选第二个重复项仍会写入一次。跨章节已存在重复保留旧记录、不重复增殖。

## 18. Conflict Detection

NONE / DUPLICATE / STATE_TRANSITION / CONTRADICTION / AUTHORITY_CONFLICT / AMBIGUOUS。同批矛盾标记双方；选中冲突阻止整个提交，取消冲突候选后可提交其余项。已提供 A3 Canon 与 approved/locked 依据必须逐项检查；语义不同措辞的矛盾依赖模型检查和人工确认，不声称有自然语言确定性推理器。

## 19. Authority

Draft 不可覆盖已批准方向或锁定依据。完成前检查 exact-Draft 最新 Review 的 hard_gate_issues/P0 Authority 问题。confidence 不授予权限；A6 不覆盖 A3。AI agent identity 不可调用用户确认操作。

## 20. Human Confirmation

候选界面分组并默认排除冲突；可取消、返回、明确确认空集合。确认绑定页面 Draft 和 active proposal，历史 Draft 无法确认另一版本。真实 Case 05 的选择权留给用户。

## 21. Commit Transaction

WorkflowRuntime/application service 持有项目根锁。batch、subject、entry、同步 PostgreSQL 索引、Chapter Completed、workflow event/transition/audit 一起成功或回滚。数据库有 exact lineage/作用域、不可变、唯一版本、原子提交延迟约束与 completed guard。Repository 只 flush。

## 22. Versioning

memory request/proposal/batch/subjects/entries 追加式不可改删。状态使用 logical_id/version/supersedes_id；项目 canon_revision 由 committed batch 序号构成。ChapterVersion current/approved 复用原语义，无平行正文版本指针。

## 23. Indexing

结构化 project/subject/type/authority 索引和 statement 的 PostgreSQL GIN FTS，同一事务维护。FTS 保留基础索引能力，没有新增搜索产品。无需异步索引服务，index failure 会回滚事务。

## 24. Context Integration

CP-004 v6、CP-005 v6、CP-009 v1；既有 profile 不覆盖。Planning output v2/prompt v6 可绑定 nullable POV subject，历史 v1保留。查询只访问已提交内容，按项目、相关实体、类型与章节时间限定，proposed/cancelled/stale 候选不进入 Context。

## 25. Frontend

“完成本章”“整理本章记忆”“本章将记住”“确认并完成”“返回正文”和 Completed 只读状态；冲突对比、候选 include/exclude、折叠摘要、Debug lineage/batch。保留现有工作台结构，无知识图谱 UI。

## 26. Freshness

提取前、结果返回、人工确认三处检查 accepted/current/approved Draft、Profile、批准依据、locks 与 Canon revision。输入变化使提案 stale。未来实体/状态已存在时禁止旧章倒序覆盖，留给未来 reconciliation。

## 27. Tests

测试代码在本地、不提交。包括：六种候选、字段越权、精确 quote/source、identity aliases、小数、认知归属、authority/canon冲突、空结果、选中/排除、幂等并发、失败回滚、锁/Canon/Draft变化、历史状态、完成后写保护、原文知识旁路、locked dependency Writer、Repository 不 commit、前端状态/确认 fencing。全量、lint、migration、Docker 的最终数值见本节后续验证表。

| 验证 | 结果 |
|---|---|
| Backend 全量 pytest | 初次验证收集1427项；有效最终结果1423 PASS、4 opt-in付费测试 SKIP；后续修复验证见第33节 |
| 全量执行方式 | 四个独立 pytest 进程，各自完整 collection 后按 nodeid hash 分片，隔离 test DB/schema；没有漏选测试 |
| 重跑说明 | 全量分片当时1425项：1420 PASS、4 SKIP、1 FAIL。该失败是编辑中的 ref() 参数临时错误被独立 Worker 子进程读到；修正后原失败项、完整48项 Memory contract及六类型 commit一起复测50 PASS。新增的2项证据/Prompt历史测试也包含其中，当前总计1427 |
| Backend ruff check | PASS |
| Backend ruff format --check | PASS（391 files） |
| Frontend npm test | 149 PASS / 11 files |
| Frontend lint / typecheck / build | 全部 PASS |
| git diff --check | PASS |
| 隔离 migration | upgrade head → downgrade -1 → upgrade head → alembic check 全 PASS，无 metadata drift |
| 开发库 | 备份后升级0016_memory_commit；alembic check PASS；未对用户数据执行 downgrade |
| Docker | backend/worker build PASS；backend容器 startup、health、health/db PASS |
| 本机入口 | native Backend8000 health/db、frontend5173代理 health/db均 PASS；Docker Worker已更新 |
| Independent Review | 初次两轮及窄复审 PASS；后续整体 Review 发现的3项问题及修复见第33节 |

首轮回归还更新了历史 migration snapshot 对新增表/列的排除、当前 migration head/profile版本断言，以及 Writer 不再接收上一章整篇正文的预期；保留旧版本 profile/prompt 的验证。每次失败均检查原因，未关闭校验或删测试求通过。

本轮新增关键测试为 `tests/test_memory_contracts.py`（48）和 `tests/core/quality/test_memory_commit.py`（19），另有 locked正文依赖 Writer 与前端 memory/command fencing。真实付费调用独立于默认全量测试，不以 --live-model 触发旧阶段的付费用例。

## 28. Real Provider Acceptance

使用现有 Lingzhi / gpt-5.6-sol、TOML 配置、单次任务最多1尝试。只调用 A07，不生成新章节，不运行 Writer/Review。首次真实调用返回 SCHEMA_PARSE_ERROR，未产生 Canon；一次性容器未挂载诊断输出，原始失败内容已不可读取。第二次手工有界调用已捕获本地原始输出，5个候选通过 Pydantic，但其中一段 evidence 为截短对话补写了正文中不存在的右引号；MemoryCommitService 的精确 substring 校验正确拒绝，仍为 SCHEMA_PARSE_ERROR。没有猜测修正模型原文或绕过证据校验。

新增 extract-chapter-memory Prompt v2，明确要求最小内部连续子串、禁止为了截短而补引号/标点/省略号。v1 内容和两次失败 Run/Lineage 均保留。用通用英文对话用例验证：补造右引号拒绝，原文内部短句通过；没有 Case05 特判。第三次真实提取授权待用户答复，本轮没有自动重试循环。两次真实调用合计40,731 tokens（Provider返回的usage，非价格估算）。最新Docker Worker已验证载入 Prompt v2。

第二次失败 Run `29efa541-d9a1-4350-ba25-c24bca10efaa`；PromptLineage `5187da8d-5293-42a1-bb3c-a7a738aac1e0`；ContextPackage `bc6de806-812c-4f8c-81a4-6e91bd3fa4f9`。原始输出仅保存在忽略的本机私有诊断目录，不通过业务API公开、不提交。

## 29. Case 05 Result

原始 Project `23c028ee-cd94-4965-af85-731e560c9633`；Chapter8 `0db2fea7-db58-4cc6-9947-4fcee48bdb21`；Workflow `c96f61c2-da12-4b05-9051-073a63d7f079`；Draft03 `544d07d5-d376-4be8-b8b0-c8dbf4641eb3`，2656字符；Review v4 `ff4a07b5-a776-4c4b-9453-1a782bca6e80`。正文 SHA-256：`da6afc60818e5514e40be1128bd573df3b5eab142ed3afd9c53d5d4dd20f3295`。没有重新生成 Chapter 或正文。人工接受正文后 approved_version=3；长期记忆确认尚未发生。

MemoryRequest `d9fdc475-7c5c-4861-9770-d6e902156895`；首次任务 `d7939505-0965-452e-ac13-bdd201982fc4` / Run `ba294e33-8017-44ea-8add-1fa025345f9a`；第二次任务 `7d695073-2288-4ac8-90d8-60128b755daa`。两次均在候选落库前被拒绝，Workflow C90_BLOCKED，resume_state=C14。没有 MemoryCommitBatch、没有新增 CommittedMemory、没有 C16。

第二次输出只提取5项，其中未具名主角被标记 AMBIGUOUS，没有自动补造主角身份。重要性/完整性与真实人物认知仍需后续人工验收，不能声称真实闭环已通过。

## 30. Known Limitations

- 语义重要性、不同措辞的冲突、别名含义和 quote 是否真正支持陈述仍需真实模型及人工核对；确定性校验不等于文学理解。
- 主体目录超过500项则提取拒绝并要求缩小范围；不把所有 Memory 塞入 Context。
- 不支持多 POV 私有认知合包，未绑定 POV 时 Writer 不取私有记忆；不自动推断主角身份。
- Completed 之后不能编辑，旧章节倒序写入遇未来同实体/状态需未来 reconciliation。
- 本机 Docker backend 容器内 health/db 正常，但 host 8000 forwarding 不通；保持既有 native Backend + Docker PostgreSQL/Worker 运行方式。本次未更改宿主 Docker 网络。

## 31. Deferred Work

Publishing、搜索/图谱界面、Memory analytics、向量库、自动偏好学习、Prompt autotuning、历史回填、多用户、分享、Reopen/Reconciliation、自动 Canon 重写/冲突解决均未实现。

## 32. Acceptance Result

**NOVEL-012 = CONDITIONAL PASS（工程通过，真实行为与人工闭环未通过）。**

| 层面 | 结果 |
|---|---|
| Engineering Acceptance | PASS：Mock/recorded provider完整确认、Commit/C16、版本/事务/权限/知识边界通过 |
| AI Behavior Acceptance | NOT PASSED：真实Case05两次被严格输出/证据校验拒绝，Prompt v2尚未获真实复验 |
| Human Memory Acceptance | PENDING：没有用户确认，也没有真实Canon commit |

剩余验收步骤：授权或在页面手工重试A07；获得合法候选后检查遗漏、临时细节、推断、认知归属、Open Thread与Summary；勾选确认后核对batch/entries/C16及下一章定向检索。未执行的这些步骤不标为 PASS。用户也可点击返回正文，不会写入长期记忆。

Independent Review 已完成两轮及最终窄复审，前10项及 locked dependency 回归均关闭，当前审查范围无剩余 Blocking / Required。不能将未发生的人工 Canon 确认标为 PASS。

## 33. Review Fix — 2026-10-01

后续整体 Review 在测试库复现3项选择边界缺陷：不确定候选的别名污染其他人物身份；单独选择重复状态转换时更新被静默跳过；第三条及之后的同属性冲突候选漏检。

修复仅调整现有 memory policy 与 commit service。身份解析排除不确定/Authority 阻断来源；确认前复用同一 normalize 对所选子集核对 subject_id/normalized_subject，不一致时返回 CONTEXT_AUTHORITY_CONFLICT，整批不写入，提示调整选择或返回重新整理。重复转换保留 STATE_TRANSITION，复用 selected_keys 去重，兼容原0016 supersedes约束。冲突校验改为完整属性分组，使用规范化 value、epistemic_status 与 known_fact_id，并保留既有阻断原因。没有新增封装、持久化模型或迁移。

新增回归覆盖：低置信/歧义/Authority 来源及不同顺序、三条以上同属性冲突、API只选Jun后的实际数据库归属、仅选转换副本和同时选两条、真正旧Canon重复跳过、未选有效/晚阶段歧义别名来源拒绝与调整选择恢复。测试代码继续只保留本地。

修复后全量验证收集1450项，四个分片分别381/375/363/327 PASS，总计1446 PASS、4项付费opt-in SKIP，无失败。Frontend全量149 PASS；Backend Ruff check/format（391 files）、Frontend lint/typecheck/build、git diff --check全部通过。隔离测试库执行upgrade head → downgrade -1 → upgrade head → alembic check全部通过，未对用户数据降级。独立复审确认3项修复闭环，没有新增必修问题。

本轮没有调用真实模型或写入用户Canon，Case05真实行为与人工确认仍按第28～32节保持待验收。
