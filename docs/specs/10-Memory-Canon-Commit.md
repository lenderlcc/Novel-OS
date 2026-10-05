# NOVEL-012 — Memory / Canon Commit

## 范围与已有能力

复用正式 chapter-planning.v3、current/approved ChapterVersion、A07、REPORT_RESULT、Prompt/Context/Run lineage、项目事务锁和 PostgreSQL。旧 simulation 的 C14/C15 行为不变。新增能力只处理用户当前明确接受的章节，不回填旧章节，不自动学习 Profile，不提供 Reopen/Reconcile。

章节正文、已批准 Plan、Review、HumanFeedback、Writing Profile 各自保持原有角色。Draft 的保存或批准不等于 Canon 提交。A07 只有报告候选的能力；用户确认后由 application service 写入。

## 生命周期

1. 空闲 C10/C11 WAITING_HUMAN 点击“完成本章”，携带 event_id、expected_state_version、确切 chapter_version_id。
2. Service 检查当前正文、活动反馈/修订、锁及最新 exact-Draft Review 的 P0 Authority 硬问题，批准确切当前正文，并冻结 MemoryRequest 的 Authority snapshot、Canon revision、CP-009。
3. C14_MEMORY_PREPARATION / WAITING_AGENT 调度 EXTRACT_CHAPTER_MEMORY。成功只产生 immutable Proposal，进入 C15_MEMORY_COMMIT / WAITING_HUMAN。
4. 用户勾选候选并提交 CONFIRM_MEMORY。所有写入、索引更新、审计、Workflow C16 和 Chapter COMPLETED 在同一事务内完成。
5. 空列表仍需明确确认；冲突可取消勾选，不能强制覆盖。返回正文保留提案历史、不产生 Canon。模型失败进入 BLOCKED，可显式重试或返回。
6. COMPLETED 后禁止改正文、计划和再运行 Revision。恢复编辑需要未来的 Reopen/Reconcile Ticket。

接受正文和提交 Memory 是两个用户动作。前者选择 approved_version；后者固定章节完成状态。返回正文不会撤销已发生的正文批准，后续修改仍必须创建新 Draft。

## 类型与 Authority

| 类型 | 层 | 含义 |
|---|---|---|
| CANON_FACT | A3_CANON | 已确认的重要事实 |
| CHARACTER_STATE | A3_CANON | 人物位置、持有物等当前状态 |
| CHARACTER_KNOWLEDGE | A3_CANON | 某角色知道、相信、怀疑或存疑的认知状态 |
| RELATIONSHIP_STATE | A3_CANON | 有明确来源的关系变化 |
| OPEN_THREAD | A6_DERIVED_MEMORY | 尚待解决的连续性提示 |
| DERIVED_CHAPTER_SUMMARY | A6_DERIVED_MEMORY | 至多一份章节检索摘要 |

CHARACTER_KNOWLEDGE 的 A3 表示“该人物具有这种认知”经过确认，不表示认知内容是真理。BELIEVES/SUSPECTS/DOUBTS 不转换成 CANON_FACT。只有 KNOWS 可以引用此前已提交、同值的 known_fact_id。Authority 完全由 Service 按类型产生，confidence 只影响确定性；A07 不可传 status/version/authority_level。

## Schema、Evidence 与 Normalize

Pydantic MemoryAgentResult 是 structured output 和 runtime 的同一 source of truth。candidates 最多40项；允许为空；不允许 ProposedChange 或通用 memory_proposals。

每项包括类型、subject_ref、语义 slot/value、statement、state_before/after、可选 epistemic_status、importance、1～5条 evidence、source_refs、confidence、uncertainty，以及 authority_checks。Evidence 必须精确引用当前接受的 ChapterVersion，使用1起始段落索引和最多300字符原文摘录。Plan、Review、Feedback 不能充当事实 evidence。

规范化对实体名/别名做 NFKC、大小写和标点标准化；明确同批别名在短名之前统一解析。复用已有 logical subject ID；模糊身份、跨类型重名、无法验证的别名和低置信度标为 AMBIGUOUS。value 比较保留小数点等有意义标点。新增实体名及别名必须在正文出现。身份判断的语义正确性仍需要模型提取和用户核对。

低置信、uncertainty 或 Authority 阻断候选不参与同批身份合并。确认时复用相同规范化逻辑重新解析所选候选；若人物标识或别名与展示的提案不一致，拒绝提交并提示调整选择或返回重新整理，防止未选候选的身份依据被隐式写入。

每项必须对已提供的 approved/locked Requirement、Decision、Plan、锁定 ChapterVersion 和 A3 committed-memory 给出边界检查。选中的边界缺漏属于 SCHEMA_PARSE_ERROR；已确认冲突成为可见候选冲突，不静默覆盖。相同 subject/type/slot/value 为 DUPLICATE；明确 state_before 与旧值相符的状态变化为 STATE_TRANSITION；其他不同值为 CONTRADICTION。不同措辞/属性的语义矛盾由 A07 边界检查与人工确认补充，系统不声称能确定性理解任意自然语言。

同一 subject/type/slot 按整组比较规范化 value、epistemic_status 和 known_fact_id；互不兼容的可提交候选全部标为 CONTRADICTION，已有 Authority/歧义阻断保留。重复的 STATE_TRANSITION 保留转换语义，单独选中任意副本仍写入下一版本；同时选中多个副本时由现有提交去重只写一次。只有与已提交 Canon 相同的候选才直接跳过。

## 数据与事务

0016 新增 memory_requests、memory_commit_proposals、memory_commit_batches、memory_subjects、committed_memory 五张表，以及 workflow.memory_request_id。Memory 六种类型共用追加式表，避免六套重复 CRUD。

同属性通过 logical_id/version/supersedes_id 追加版本。旧行不可 update/delete。每个完成章节最多一个 batch，同一 source/proposal 唯一。Canon revision 是项目已提交 batch 的最大序号，项目根锁下递增。现有 current/approved pointers 不增加第三套正文版本指针。

Repository 只 add/flush/query。WorkflowRuntime 是事务入口，MemoryCommitService 重新读取并验证 active request/proposal、source version、当前 approved 输入/locks/Canon revision，再写 batch、必要的新主体及选中条目、Chapter 和 Audit。重复项记录在 skipped_candidate_ids；不重写旧 Canon。数据库触发器补充 lineage、作用域、内容绑定、版本链、不可变和完成后保护。延迟约束确保 batch、用户确认事件、entries 和 Completed 一起提交。失败全部回滚。

PostgreSQL 结构化索引和 statement 的 GIN full-text index 随事务同步维护；不引入异步索引队列。实体目录检索有明确上限，超限拒绝而不是全量塞入上下文。downgrade 仅允许无 MemoryRequest 的空阶段，避免删除已接受的不可变历史。

## Context 与人物认知隔离

CP-004 v6 为 Planning 查询相关此前已提交的记忆、身份目录和有限摘要。新增 plan output v2 的 nullable pov_character_id，必须是提供的 CHARACTER 身份，由用户批准 Plan 绑定；历史 v1 schema/prompt 保留。

CP-005 v6 的 Writer 只读取 exact approved Plan 所绑定单一 POV 的人物状态、关系和认知，以及其 KNOWS 显式关联的 Canon。未知或多 POV 不自动授予任何私有知识。删除上一章整篇正文和显式 ChapterVersion 原文注入，堵住 B 的秘密通过原文绕过 firewall 的路径。锁定正文仍做 exact dependency / freshness 校验，但不再作为 Writer 必需正文内容引用。

CP-009 v1 为 A07 提供 exact accepted chapter 的编号段落、批准依据、相关既有记忆和身份。Proposal、未完成 batch 永不进入检索。所有查询 project scoped，按目标章节 sequence 截断，包括 successor 和身份创建章节；未来状态不会隐藏当时有效的旧状态。提取旧章节遇到未来已存在的相同实体/状态时要求 reconciliation，不回写历史。

## API 与 UI

- POST /api/v1/workflows/{id}/completion
- GET /api/v1/workflows/{id}/memory
- POST /api/v1/workflows/{id}/memory/confirm
- POST /api/v1/workflows/{id}/memory/discard
- GET /api/v1/projects/{id}/memory（subject/type/history、limit/offset）

命令复用 event_id / expected_state_version、真实 user actor 和现有冲突错误。读取经过 Service → Repository。错误沿用 VERSION_CONFLICT、CONTEXT_STALE、SCHEMA_PARSE_ERROR、CONTEXT_AUTHORITY_CONFLICT、AUTHORITY_DENIED。

工作台提供“完成本章”→“本章将记住”→“确认并完成”，事实/状态/认知/关系/未解决事项分组，摘要折叠；默认排除冲突项。历史正文不能确认另一份 Draft 的提案。Debug 保留 request、proposal、run/prompt/context lineage、batch、最终条目；无需知识图谱编辑器。
