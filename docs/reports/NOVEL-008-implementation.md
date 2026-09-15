# NOVEL-008 — Writing Agent + Chapter Draft Production

日期：2026-09-15。开发基线：`9762f59`；分支：`wfg/novel-008-writing-agent`。

## 1. Implementation Summary

在稳定 001–007 之上增加正式 Writing 链路：用户 Plan Gate → C07 → CP-005 v3 → A04 / WRITE_CHAPTER → WritingResult → immutable ChapterVersion DRAFT → 确定性检查 → C08。新增两个表；未新增依赖、环境变量配置或后续 Ticket 功能。

## 2. Writing Vertical Slice Architecture

API → application Service → Repository → PostgreSQL。WorkflowRuntime 保持唯一状态转移入口；Worker 调用纯 AgentRuntime / PromptRuntime，所有模型输入来自 ContextPackage。新 `/workflows/chapter-writing` 使用 chapter-planning v2；v1 和历史实例保持 C07 边界。

## 3. A04 Writing Agent

使用既有 A04_WRITING 身份，新增正式使命与 PROPOSE_DRAFT 能力。允许局部措辞、动作、对白、场景细节和节奏选择；重大剧情、结局、世界规则、核心人物及锁定决策变化必须显式上报。Writer 不兼任正式 Reviewer。

## 4. WRITE_CHAPTER Task

进入 v2 C07 的同一个工作流事务自动调度，幂等键沿用 workflow/state_version/task_type。没有任意 Agent 调用接口。TaskScheduler 同时写入不可变 WritingTaskBinding，绑定 Plan 行 ID、版本、预期当前正文版本、CP-005 profile 和输入指纹。C08 不创建下游 AgentTask。

## 5. CP-005 Integration

发布 CP-005 v3，仅用于 WRITE_CHAPTER。旧 MOCK_WRITE / CHAPTER_WRITING 仍用 v2。P0：exact approved Plan、目标 Chapter、MUST/FORBIDDEN/PRESERVE/CHANGE_REQUEST、锁定决策及有效批准决策；P1：上一章 approved body 和 supporting requirements。当前 Decision 没有 major 标记，因此保守地把全部相关批准 Decision 放入 P0。

## 6. Approved Plan Binding

WritingTaskBinding 将 Plan ID/version 与 Task 关联。执行前和落库前核对 chapter.approved_plan_version、Plan.approved_at/status、workflow.plan_version；不要求 current_plan_version 相等。Plan v1 APPROVED + v2 PROPOSED 仍使用 v1，包括模型调用过程中创建 v2 的情况。任务快照、PromptLineage 和 ContextPackage 均不可变。

## 7. WritingResult Schema

同一个 WritingAgentResult/WritingResult Pydantic 模型用于生成 JSON 输出契约和解析结果。必填 chapter_id、plan_id、plan_version、content、scene_execution、introduced_elements、proposed_new_facts、plan_deviations、unresolved_questions、assumptions、knowledge_risk_flags、style_notes、confidence。每层 extra=forbid；正文拒绝空白/NUL，最多 100000 字符，版本严格整数，置信度有限且位于 0–1。

## 8. Scene Execution Metadata

每个计划场景必须有唯一 scene_id，记录 exact planned_function、简短 execution_summary、source_location、function_completed 和 deviation。检查场景集合与功能来源；不要求或保存隐藏 Chain of Thought，不使用字数、对白数或段落数作为文学评分。

## 9. Plan Deviation Model

PlanDeviation 包含 type、location、planned_behavior、actual_behavior、reason、impact、severity、requires_replan、confidence。LOCAL 放行；MODERATE 保存并供后续 Review；MAJOR 或 requires_replan 阻塞。明确的重大 outcome/ending/world/core character/locked decision/future structure/FORBIDDEN 类型即使声称 LOCAL 也阻塞。

## 10. Proposed New Facts

ProposedFact 包含 fact、scope、importance、reason、source_location、confidence，仅保存于 Writing metadata。正文中出现事实也不会升级 Authority。MINOR/SUPPORTING 可保留，MAJOR 新事实/新增元素阻塞正常正文路径。没有 CanonFact 或 Memory 表、Service、写接口。

## 11. Knowledge Risk Model

KnowledgeRisk 明确 character_ref、fact、knowledge_type、source_location、risk、confirmed_leak。未确认风险保留为元数据，明确已发生知识泄漏则 BLOCK。GLOBAL_ONLY、KNOWLEDGE、BELIEF、SUSPICION、MISUNDERSTANDING、UNKNOWN 保持不同语义。未引入 CharacterKnowledge 持久化。

## 12. Writing Prompt Modules

新增 writing-agent role、write-chapter task、writing-quality profile 和五个 Writing skill，均为 v1、STABLE、内容 SHA-256 manifest。通过 NOVEL-005 注册表组合 System → Role → Task → Skills → Quality → Authority → CP-005 Data → generated Output Contract。编译器没有数据库查询。

## 13. Scene Execution Skill

从意图、阻力、选择和后果实现场景功能，不把 Plan bullet 逐条扩写成对应段落。局部表达可自由组织；场景元数据引用原计划功能和可观察执行证据。

## 14. Dialogue Skill

对白体现人物目的、关系、回避、犹豫、误解、隐藏信息和互动，不只是提供情报或解释设定；没有对白配额。

## 15. Character Voice Skill

遵守已有 voice cues、关系和知识边界；根据情境区分语域、节奏及答复方式。缺少线索时只允许局部表达，不生成永久人格 Canon。

## 16. Narrative Rhythm Skill

由场景压力与注意力组织节奏、过渡和停顿；允许悬置、余韵和不完整收束，不规定句长或段落模板。

## 17. Natural Prose Skill

natural-prose 直接包含 AS-01/02/03/04/05/06/07/12 的实质指导，强调具体性、克制、角色声音和自然互动；不制造错字、语法错误、随机文本损伤、机械同义替换或 detector evasion。

## 18. Naturalness Prevention Rules

AS-01 过度解释；AS-02 情绪标签；AS-03 均匀节奏；AS-04 模板转场；AS-05 功能化对白；AS-06 角色声音趋同；AS-07 过度收束；AS-12 过度提示。测试检查完整模块、编译 Prompt 及其非机械约束，不仅检查文件存在。完整语义和文学质量评估延后。

## 19. PromptLineage

每个实际模型调用绑定既有不可变 PromptLineage：模块 ID/version/hash、schema ID/version/hash、model profile、编译 Prompt hash。Generation 引用准确 lineage_id；数据库触发器核对 run/task/schema/profile/provider/model，阻止关联别的调用。

## 20. ContextLineage

每个 Run 单独创建不可变 ContextPackage，复用 CP-005 精确 profile 版本和 hash。冻结 source snapshots 包括空集合以发现新来源；模型前与落库前复核。目标 Chapter 指纹忽略仅由输出造成的 version/updated_at 变化，仍保留 title/sequence/status/authority、approved Plan 和当前正文指针。

## 21. Generation Lineage

WritingGeneration 显式关联 ChapterVersion、AgentTask、AgentRun、PromptLineage、ContextPackage、Plan ID/version、Brief，保存 model_profile/provider/model、时间戳、content_hash、结构化 metadata 和 check_status/check_codes。外键、唯一约束和触发器约束关系；不保存 API Key 或原始 provider 响应。

## 22. Writing Result Handler

AgentResultHandler 完成 schema / authority / lease / Context freshness 校验；WritingResultService 验证 Plan/Chapter/Brief、精确 lineage 和显式偏离。合格结果创建 Draft，记录 metadata/check，应用层发送 DRAFT_READY，WorkflowRuntime 在进入 C08 前核验实际持久化关系。Agent 无权自行发事件。

## 23. ChapterVersion Creation

复用 NOVEL-002 ChapterVersionService.create_version_in_transaction，在 Project 根锁下检查 Chapter/正文逻辑锁及 expected_version。正文原样保存，生成来源为 AGENT、Authority 为 A7_AI_INFERENCE、状态 DRAFT。Generation 不重复存正文，BLOCK 结果只存 metadata 和正文 hash。

## 24. current_version / approved_version behavior

成功生成与业务再生成只更新 current_version。E2E 验证已有 approved v1 时先生成 current v2，再生成 v3，approved 指针始终为 v1；历史版本内容不变。

正式 C08 的 RESUME 保留已通过确定性检查的 workflow.draft_version。外部通过 Core API 新建的 current_version 不会被自动认领为 Writing 结果；两者不一致时，再生成继续返回 VERSION_CONFLICT，保留独立用户编辑。模拟流程原有的版本刷新行为保持不变。

## 25. Retry vs Regeneration

模型超时/格式错误：相同 Task、新 Run，成功前无 ChapterVersion。重复结果投递按 Run 幂等，Generation 对 task/run/version 均唯一。用户在 C08 调用 writing/regenerate，提交 expected_state_version 与 expected_draft_version，创建新 Task 和正文版本；旧正文不 UPDATE。

C08 再生成或恢复前会检查当前 Brief 和 exact approved Plan。Plan 被新的批准版替代时，先记录 BLOCKED / recovery=C04；用户 RESUME 后重新规划并通过新的 Plan Gate。C08 已完成任务的输入快照包含生成前的正文版本，不能直接套用 C07 的待写入版本检查，否则会错误地阻塞所有正常再生成。

## 26. Deterministic Draft Check

验证非空正文、exact Plan、场景元数据集合及计划功能、完整 lineage、权限、输入来源快照新鲜度与实际 ChapterVersion 关系/hash。PASS 才进入 C08；显式不可接受证据保存 BLOCKED check。数据库或最后关系校验失败则整个事务回滚。没有 Full Review、quality_pass 信任或字数评分。

## 27. Major Deviation Handling

重大偏离、requires_replan、明确 FORBIDDEN 违反、重大新增事实或确认知识泄漏都会留下 BLOCKED 生成记录，不创建正常 Draft。用户可审查具体 metadata 和 check_codes。来源失效按恢复规则重新进入 C01/C04；错误来源不会在普通 RESUME 中悄悄重绑为有效。

## 28. Persistence

新增 writing_task_bindings、writing_generations。两表 append-only，禁止 UPDATE/DELETE；关键关联使用真实关系字段，不隐藏于任意 JSON。Repository 只 flush；Service / WorkflowRuntime 负责事务。Core、Workflow、Agent、Prompt、Context 和 Planning 旧表结构与迁移保持不变。

## 29. API Changes

新增 POST /api/v1/workflows/chapter-writing；GET /api/v1/workflows/{id}/writing/history（分页）；POST /api/v1/workflows/{id}/writing/regenerate（状态版本 + 正文版本）。正文读取沿用已有 ChapterVersion API。所有输入 schema 禁止额外字段；没有 direct agent API 或新的正文审批入口。

## 30. Tests Added

新增 tests/test_writing_contracts.py、tests/core/writing 下 vertical_slice、lifecycle、context_and_prompt、output_policy、writing_persistence、live 及共享 fixture。旧测试仅更新新增 profile/head 的预期与历史迁移快照表集合，保留旧用例断言和历史数据比较。新增持久化测试使用独立文件名，避免 pytest 与已有 core/test_persistence.py 的模块名冲突。最终测试数量见第 46 节。

Review 修复新增 test_recovery_regressions.py 的 8 个场景：PAUSE/BLOCK 有无独立用户正文、C08 再生成及暂停/阻塞期间批准 Plan 被替换后的完整恢复链路，以及新 PROPOSED Plan 不影响旧批准版。修改前 5 failed / 3 passed，修复后 8 passed。

## 31. Approved Plan Test Result

PASS：未批准不调度 Writer；失效审批在 provider 前阻塞；current Draft 不替代 approved；返回错误 Plan ID 被拒绝；locked approved Plan 可读；替换批准 Plan 后必须重新规划。

## 32. Context Leakage Test Result

PASS：P0 约束/批准决策、PRESERVE 保留；未批准 Requirement、不同项目数据、current Draft 正文不进入 Writer。写入前复核来源变化，无局部 Draft 残留。

## 33. Future Knowledge Test Result

PASS：普通未来 approved/draft Plan 和未来 Draft 正文均不自动进入；仅显式 required refs 可见。即使被锁定，未批准未来 Plan 也无法满足 CP-005 v3，缺失必要上下文时 BLOCK；已批准且锁定的必要 future ref 可进入。

## 34. Character Knowledge Boundary Result

PASS：序列化保留 GLOBAL_ONLY 与带 subject 的 CHARACTER_KNOWLEDGE，不把系统事实转换成人物所知。Prompt 区分 KNOWLEDGE/BELIEF/SUSPICION/MISUNDERSTANDING，确认泄漏的结构化输出被阻塞。未实现 Memory Domain。

## 35. Authority Negative Test Result

PASS：拒绝 status/authority_level/approved_at/version/system_actor/next_state/next_event/event/quality_pass；拒绝 APPROVE/LOCK/UNLOCK/COMMIT_CANON/SET_WORKFLOW_STATE/DIRECT_DATABASE_WRITE 和额外写操作。核心批准数据及锁不由 Writer 改动。

## 36. Plan Deviation Test Result

PASS：LOCAL/MODERATE 落盘且保留 metadata；MAJOR 与伪装成 LOCAL 的重大类型被阻塞；FORBIDDEN、major fact、escalation、低置信度、未知/遗漏场景功能、确认知识泄漏覆盖负向路径。

## 37. ChapterVersion Immutability Result

PASS：数据库直接 UPDATE content 失败，历史正文保持原样；Writing metadata 和 binding UPDATE/DELETE 失败；新版本与批准版本分离。

## 38. Retry Duplicate Draft Test Result

PASS：format/model error 首次无 Draft；同 Task 第二 Run 成功仅一版正文。并发投递分别 APPLIED/DUPLICATE。两个独立再生成请求分别 APPLIED/VERSION_CONFLICT，只生成一个下一版本。

## 39. Stale Result Test Result

PASS：取消/暂停后的结果 STALE_IGNORED；审批、有效 Requirement、相关锁、Chapter 锁或其他正文变化使执行结果失效；模型前失效验证 provider 调用数为零。恢复时重新发现的 drift 保留阻塞证据并要求 C01/C04 重建来源。

## 40. E2E-A Result

PASS：Mock 规划/审查 → User Plan Approval → Writer → Draft v1 + metadata + lineage → deterministic PASS → C08。无下游 AgentTask，Worker 下一次返回无任务。

## 41. E2E-B Result

PASS：已有 approved body v1 → 新 Draft v2 → 用户业务再生成 v3；current=3、approved=1，v1/v2 历史内容保持不变。

## 42. E2E-C Result

PASS：WRITING_MAJOR_DEVIATION → BLOCKED generation metadata → C90_BLOCKED，无 ChapterVersion。

## 43. E2E-D Result

PASS：模型调用后、落库前变更批准 Plan/来源/工作流；结果拒绝或 stale ignored，无错误正文和 generation 部分提交。

## 44. Real Provider Writing Smoke Result

NOT RUN（显式 opt-in）：默认不读取凭据进行外部调用，未进行付费模型调用。已提供 tests/core/writing/test_live.py 与 --live-model 路径，使用独立测试项目和批准 Plan，最多 3 次 Writing 调用。固定 Mock 验证工程契约，不证明任意需求的文学完成度；10 项人工质量观察（目标、bullet 机械展开、过度解释、对白、节奏、知识泄漏、方向、新事实、转场、metadata）本次均未作真实模型评定。

## 45. Migration Result

PASS：本机 dev PostgreSQL 执行 alembic upgrade head → downgrade -1 → upgrade head → alembic check，实际 0008 ↔ 0009，未发现新增 migration operations。隔离 schema 往返测试比较所有旧表逐行数据保持一致。历史 0002/0004/0005/0006/0007/0008 往返测试保留。

Review 修复未改动 migration；再次执行 alembic current / check，确认仍为 0009_writing_agent (head)，无新增升级操作。修复后的完整 pytest 也通过所有隔离 schema 迁移往返测试。

## 46. Full pytest Result

PASS：Review 修复后在 backend/ 执行完整 `uv run pytest`，共收集 784 项，结果为 **781 passed, 3 skipped, 2 warnings in 561.13s（09:21）**。三个跳过项分别为真实 Provider、Planning live E2E、Writing live smoke，均要求显式 `--live-model`。自动测试没有调用付费 Provider。

首轮新增 Writing 测试单独运行结果为 **113 passed, 1 skipped**；本次又补充 8 项 C08 恢复回归，修改前 5 failed / 3 passed，修复后独立运行 **8 passed**，并全部纳入最终完整回归。最终包括 Writing 的 121 项通过及 001–007 的 660 项非 opt-in 测试通过。两条既有 warning 分别为 Starlette TestClient 的 httpx 弃用提示与 anyio BlockingPortal alias 弃用提示。

## 47. Lint Result

PASS：`ruff check`、`ruff format --check`（224 个 Python 文件）与 `git diff --check`。`uv build` 成功生成 wheel 和 source distribution；另检查 wheel 确实包含 Writing 代码、CP-005 v3、工作流 v2、model profiles 以及全部 8 个新增 Prompt 模块。没有新增第三方依赖；新增未跟踪文件也单独检查了行尾空白。

## 48. Docker Result

PASS：最终代码执行 `docker compose build backend` 和 `docker compose up -d --wait backend` 成功。backend、postgres、postgres-test 均 healthy；GET `/api/v1/health` 与 `/api/v1/health/db` 返回 HTTP 200，分别为 `{"status":"ok"}` 与 `{"status":"ok","database":"ok"}`。

## 49. Acceptance Criteria PASS / FAIL

对应用户要求的 48 项重点测试，结果如下。这里的 PASS 指工程契约与明确的结构化证据；不代表已经通过真实模型文学质量评定。

| # | 验收项 | 结果 / 主要证据 |
| --- | --- | --- |
| 1 | Approved Plan 调度 Writing | PASS — vertical_slice E2E-A |
| 2 | 未批准 Plan 不得开始 | PASS — lifecycle unapproved_plan_has_no_writing_task |
| 3 | stale Plan 不得调用模型 | PASS — lifecycle no_model_call_when_approval_disappears |
| 4 | current Draft Plan 不替代 approved | PASS — lifecycle exact_approved_plan_survives_new_current_draft |
| 5 | Task 绑定 exact Plan | PASS — E2E-A 与错误 Plan ref 负向测试 |
| 6 | 使用 CP-005 | PASS — context_and_prompt 的 profile / lineage 断言 |
| 7 | 缺少 P0 阻塞模型调用 | PASS — approval / required future dependency 缺失测试 |
| 8 | stale Context 阻塞模型调用 | PASS — relevant lock / approval preflight 测试 |
| 9 | Future Plan 不泄漏 | PASS — future_or_foreign_leak 与显式依赖测试 |
| 10 | superseded Plan 不泄漏 | PASS — old approval 失效及替换后恢复测试 |
| 11 | 上一章使用 approved_version | PASS — previous_approved_body_not_latest |
| 12 | 上一章 current Draft 不泄漏 | PASS — previous_approved_body_not_latest |
| 13 | Global fact 不等于人物知识 | PASS — prompt / context 知识边界断言 |
| 14 | Writing Prompt modules 已加载 | PASS — compiled Prompt 与 contract 测试 |
| 15 | 全部 Writing Skills 进入 lineage | PASS — 精确 module ID / version / hash 断言 |
| 16 | WritingResult schema 有效 | PASS — 同一 schema 生成与解析契约 |
| 17 | content 必填 | PASS — required_writing_fields 参数化负向测试 |
| 18 | 空正文被拒绝 | PASS — unit invalid_values 与 EMPTY_CONTENT 集成场景 |
| 19 | Plan 引用校验 | PASS — misbound output 与数据库关系负向测试 |
| 20 | LOCAL 偏离接受并记录 | PASS — output_policy 场景 |
| 21 | MODERATE 偏离接受并记录 | PASS — output_policy 场景 |
| 22 | MAJOR 阻塞正常推进 | PASS — E2E-C 与重大类型伪装为 LOCAL 测试 |
| 23 | Proposed fact 仅作提案保存 | PASS — PROPOSED_FACT metadata 断言 |
| 24 | Proposed fact 不修改 Canon | PASS — 无 Canon 写路径；额外 mutation / COMMIT_CANON 拒绝 |
| 25 | knowledge_risk_flags 持久化 | PASS — KNOWLEDGE_RISK metadata 断言 |
| 26 | Writer 不得批准 Plan | PASS — authority actions 参数化负向测试 |
| 27 | Writer 不得批准 Chapter | PASS — APPROVE 拒绝及 approved pointer 保持测试 |
| 28 | Writer 不得 Lock | PASS — LOCK capability 拒绝 |
| 29 | Writer 不得 Unlock | PASS — UNLOCK capability 拒绝 |
| 30 | Writer 不得 Commit Canon | PASS — COMMIT_CANON capability 拒绝 |
| 31 | Writer 不得 set next_state | PASS — fake_control_fields 负向测试 |
| 32 | Writer 不得 set next_event | PASS — fake_control_fields 负向测试 |
| 33 | Technical retry 创建新 Run | PASS — format / model error retry 场景 |
| 34 | Technical retry 无重复正文 | PASS — retry 与并发投递测试 |
| 35 | 成功生成仅一个 ChapterVersion | PASS — E2E-A 与并发投递测试 |
| 36 | Regeneration 创建不可变新版本 | PASS — E2E-B 与并发 regeneration 测试 |
| 37 | 新 Draft 更新 current_version | PASS — E2E-A / E2E-B |
| 38 | 新 Draft 不更新 approved_version | PASS — E2E-B 的 v1/v2/v3 指针断言 |
| 39 | ChapterVersion content 不可原地修改 | PASS — 数据库直接 UPDATE 负向测试 |
| 40 | GenerationRecord 正确关联 lineage | PASS — E2E-A 与 cross-bound generation 负向测试 |
| 41 | 取消后的 stale result 忽略 | PASS — changed_input_or_workflow 参数化测试 |
| 42 | 状态变化后的 stale result 忽略 | PASS — pause / state change 场景 |
| 43 | 批准 Plan 变化使结果失效 | PASS — E2E-D 与 replanning recovery 测试 |
| 44 | Project isolation | PASS — foreign context 排除与数据库跨域关联拒绝 |
| 45 | 回滚后无 partial Draft | PASS — generation/audit/check/transition 故障注入 |
| 46 | 确定性检查成功 | PASS — E2E-A |
| 47 | 确定性检查失败 | PASS — invalid evidence 与 transaction rollback 测试 |
| 48 | 001–007 回归仍通过 | PASS — 修复后完整 pytest：781 passed，包含旧阶段全部 660 项非 opt-in 测试 |

E2E-A/B/C/D、Natural Prose guidance、并发投递/再生成、迁移往返、构建与 Docker 均已验证。真实 Provider smoke 为已实现但未执行的 opt-in 项，不作为无凭据 CI 的通过条件。

## 50. Architecture Deviations

已在编码前说明：0008 已被 NOVEL-007 使用，因此新增 0009；为了保持已发布行为，chapter-planning v1 保持 C07，新增 v2 支持 C08；正式 Writing 的 plan_approved guard 使用 approved pointer，与 simulation 的 current+approved 规则分离；没有大规模重构。

任务先创建并冻结 Plan，再为具体 AgentRun 构建 ContextPackage，保留 004–006 的 lease/run 绑定次序。Decision 无重大级别字段，因此所有相关 approved Decision 均按 P0 处理。核心领域仍不依赖 FastAPI/ORM；API 返回 Pydantic DTO。

## 51. Known Issues

初次独立只读 Code Review（GPT-5.5，与实现模型不同）覆盖 exact Plan binding、Context/knowledge leakage、Authority、偏离处理、版本不可变性、并发/幂等、lineage、回滚和 Scope。审查者独立执行了 91 项 Writing 集成测试及 21 项契约测试。

后续整体 Review 复现并修复两项问题：P1 通用 RESUME 将 Core 的 current_version 直接绑定到正式 C08，绕过了 Writing 生成证据；修复为仅模拟流程刷新指针，正式流程保留已校验的绑定。P2 Writing 恢复规则只覆盖 C07，导致 C08 的批准 Plan 失效后无法继续；修复为覆盖 C08 再生成与恢复的 Plan/Brief 检查，按 C04/C01 重建来源。8 项新增回归先验证失败再验证修复通过；没有修改表结构或历史 migration。

修复后的独立只读复核已完成，未发现剩余问题。复核范围包括恢复、guard、再生成和新增回归用例，确认 C08 不应重放生成前的待写入版本检查，并确认模拟流程保留原行为；该次复核为静态审查，测试结果由本报告第 46 节记录。

开发中复现并修复的恢复根因：通用 RESUME 刷新工作流快照，但 Writing 的不可变来源绑定仍指向旧 Plan，可能使任务在 C07/C90 无法继续。局部修复在 BLOCK/RESUME 重查 Writing binding，并将已失效来源交回 C01/C04；包含暂停/阻塞后才发生漂移的回归测试。未改变旧 v1 行为。

确定性校验不做自动文学理解，无法识别模型未如实报告的所有语义偏离；这是 NOVEL-009 的职责。真实模型可能超过配置输出限制，当前单章单次调用，未用未验证的多场景分布式生成替代。全套测试仍有两条既有 FastAPI/Starlette 依赖弃用提示。

## 52. Deferred Items

NOVEL-009 Full Chapter Review / OOC / Timeline / Logic / pacing / AI-writing-smell detector / QualityAggregator；NOVEL-010 Revision；NOVEL-011 Chapter Acceptance；NOVEL-012 Canon/Character/Event/Plotline/Memory Commit。无 Vector DB、Redis、Kafka、Neo4j、Frontend、Style Learning 或 author imitation。NOVEL-008 完成后停止，不自动开始下一 Ticket。
