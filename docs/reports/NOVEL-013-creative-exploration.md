# NOVEL-013 — Creative Exploration for Planning

## 1. Background

A03 过去从 CreativeBrief 直接生成一个安全可行的 Plan。本阶段在同一 A03 内加入一次内部探索，比较不同的故事机制，再交给正式 Planning。探索不获得用户决策权，不成为独立 Agent 或用户选题流程。

实现分支：`wfg/novel-013-creative-exploration`。基线为本机已有 NOVEL-012 HEAD `1cb275d2439af3e9c5e2982002ca9c1d4fc9e107`；已 fetch 核实 origin/main 是其祖先，将本地 main 快进到该基线后创建分支。开发前的未提交改动单独记录并保留。本次未提交、推送或合并。

## 2. Phase 1 Status

| 阶段 | 状态 |
| --- | --- |
| NOVEL-001–012 Engineering | COMPLETE |
| E2E-001 Engineering Acceptance | PASS_WITH_BLOCKERS_RESOLVED |
| E2E-001R Real Provider / Human Multi-Chapter Acceptance | PENDING |
| Phase 2 / NOVEL-013 | Engineering COMPLETE; Real Provider / Human Acceptance PENDING |

013 不表示真实五章验收通过。原 E2E-001R 项目保持在第 1 章 Plan 人工审批 Gate，本阶段没有批准该 Plan、创建其 Draft、执行 Memory Commit 或消耗模型额度。

## 3. Manual Findings From Case 01~05

用户提供的人工结论是：约束遵循和自主细节决策已有基础，但 HIGH Creative Freedom 时常选择低风险、易闭合、设定依赖少的事务机制。Case 03 的历史例子为“例行交接 → 记录不匹配 → 核验失败 → 协作解决”。这些发现是开发依据，未在本阶段重新做五个案例的真实模型验收。

本阶段没有把这些案例、特定动作或场景写成 Prompt 黑名单。若真实 B 仍选择安全但一般的机制，应记录 `SAFE_GENERIC_CREATIVE_CHOICE`，不能通过自动重试或案例特判制造通过结果。

## 4. Scope

新增 A03 Task、专用输出 Contract、两个版本化 Context Profile、不可变诊断记录及只读 API、现有 Debug 展示、离线回归与人工评估资产。沿用现有 Runtime、Provider、Parser、Context、任务队列、事务、A05 Plan Review 和人工 Plan Approval。

未增加 Agent、Workflow 状态、Human Gate、用户候选选择页、Vector DB、故事模板库、创意分数、长程 Planning 或 Retrieval Phase 2。Writer、Quality Review、Revision、A07 和 Memory 语义保持原合同；它们仅有接纳同一 workflow v4 所需的版本兼容调整。

主要文件：`agents/exploration_schemas.py`，`services/exploration_policy.py`、`exploration_results.py`、`exploration_context.py`，`domain/models/repositories/planning.py`，`0018_creative_exploration.py`，`CP-004E.v1.json`、`CP-004.v7.json`，`chapter-planning.v4.yaml`，新版本 Prompt，现有调度/结果/Planning/API/前端 Debug 文件。文档更新 02/04/05/06，新增 11；新增 `evals/creative-exploration/` 五份小型资产。现有 E2E 导出脚本仅增加对新 history 集合的兼容。

开发前已存在的 Memory / A07 Schema、迁移 0017、Canon reader、Memory Commit 及相关 Prompt 改动保留原样，不属于 013 实现。基线哈希核对无原文件丢失。没有新增依赖；测试文件保留在本机，本次未提交测试代码。

## 5. A03 Creative Exploration

`EXPLORE_CHAPTER_CONCEPTS` 仍属于 A03 / PROPOSE_PLAN。C04 中先探索，再调度 `PLAN_CHAPTER`。探索完成不会发出 PLAN_READY；只有正式 Plan 完成才进入现有 Review。

HIGH 默认 3–4 个机制候选；MEDIUM 且允许 LOCAL_CONFLICT 时 2–3 个；其他 MEDIUM 和 LOW 跳过。已经固定具体事件或方向时允许 FOCUSED 一个候选，但必须解释原因。普通 A05 修复复用探索；用户明确拒绝、修改或换方案才触发新探索。

## 6. Candidate Model

Pydantic `StoryConceptCandidate` 包括 concept_summary、core_event、conflict_engine、character_pressure、story_progression、reader_interest、continuity_fit、requirement_fit、creative_freedom_fit、audience_fit、execution_feasibility、required_new_elements、major_change_risk/reason、similarity_risk/reason、authority_fit/reason、strengths 和 risks。

`CreativeExplorationOutput` 记录确切 Brief、FOCUSED/DIVERGENT、候选、选择及淘汰理由、source_refs 和 blocked_reason。Schema 检查候选/引用唯一、选中项存在且安全、每个非选中项恰有一条淘汰理由、模式和结果状态一致。模型不能填充服务端版本、批准字段或 Authority。

## 7. Story Mechanism Diversity

Prompt 要求改变因果冲突、人物压力和推进方式，不能只换地点、物件、手势或名称。普通 HIGH/MEDIUM 的候选数量由 Service 按真实 Brief 核对，FOCUSED 必须保留可检查理由。

机制是否真正不同属于模型和人工语义判断。代码没有用词汇差异、动作黑名单、模板匹配、Embedding 或数值阈值伪装成创意质量验证。RecordedProvider 测试只验证该结构和传递合同。

## 8. Character Fit

探索使用已有角色状态、目标、关系、已知事实和获授权的知识输入。Prompt 要求指出压力如何作用于人物、为什么该人物会做出该选择；不能为了新鲜感改变已确定身份、关系或方向。

Global Canon 仍不等于 Character Knowledge。原 Knowledge Firewall、Owner、epistemic status 和 Memory Domain 未改变；缺少人物资料时不得编造其私有知识。真实 Character Fit 仍需人审，测试不声称能自动证明人物行为合理。

## 9. Recent Repetition

使用最近最多 3 章的 approved Plan 紧凑投影及既有 committed final summary 作为 P1 repetition hints。Plan 按 approved_plan_version 读取；摘要来自现有 committed batch / DERIVED_CHAPTER_SUMMARY。

相似度使用 LOW/MEDIUM/HIGH 及具体理由，关注机制、情绪和推进方式。历史不是禁止清单，也不自动产生新的硬约束。近期历史不读取未批准 Draft、未来章方案或历史全文；当前 Plan 的明确修复仍沿用原精确绑定。

## 10. Major Change Boundary

重大方向、身份、关系状态、世界规则、Locked Decision 和 Canon 仍属于受保护输入。HIGH major_change_risk 或 REQUIRES_MAJOR_CHANGE 候选必须淘汰并标记 REQUIRES_MAJOR_CHANGE；其他 Lock/Canon 越界标记 VIOLATES_AUTHORITY。

所有候选都不安全时保存 BLOCKED 诊断并进入现有阻断路径，不强行 fallback，不新增审批 Gate。`proposed_changes` 和 `memory_proposals` 在专用输出 Schema 中限制为空。

## 11. Selection Policy

A03 按 Requirement、Continuity、Character、Audience、Authority、Feasibility、Story Value 和近期重复风险定性选择。选中项必须为 WITHIN_BOUNDS，major_change_risk 为 LOW/MEDIUM。每个淘汰项保存解释，供 Debug 和人工评估。

正式 Planning 只获得该选中候选的 A7 投影及标识；比较性的 selection_reason 留在诊断记录中，避免将被拒方案带入模型上下文。没有总分、排序服务或可被客户端伪造的批准。

## 12. Context Integration

CP-004E v1：REQUIRED_ONLY、隐式未来 horizon=0，读取确切 READY Brief、有效 Requirement/Decision/Lock、Approved Writing Profile、相关已提交连续性资料，以及紧凑历史 P1。CP-004 v7：同样保留权威 P0，另加入确切 selected concept EXTENSION / A7。

沿用 authoritative_constraints、review_revision_targets、recommendations 的现有分离。选中候选不升级为 constraints、Canon 或下一章种子；全候选、淘汰内容和比较理由不进入通用 Context。Writer/Revision/Memory Profile 未注册该扩展 reader。旧 workflow v1–3 仍绑定 CP-004 v6。

重复选中的 summary 使用与既有 Canon reader 相同的紧凑 payload，复用原 dedup，而非产生虚假的 Authority 冲突。没有调整 Memory Retrieval Strategy。

## 13. Prompt Version

新增不可变模块：explore-chapter-concepts v1、creative-exploration skill v2、plan-chapter v7、planning-agent role v2、planning-quality v2；同步 manifest hash。旧内容和版本不覆盖。

CP-004 v7 使用 plan-chapter v7 / skill v2；历史 Context 使用原 v6 / skill v1，历史 schema v1 保持模板 v5。Worker 在 Context 构造前保守估算较大模板成本，避免后续实际 Prompt 超出预算。

## 14. Workflow Integration

新入口 `POST /api/v1/workflows/chapter-exploration` 复用已有 CreatePlanningWorkflowDTO，启动版本化的 `chapter-planning` v4；状态、转移和 Gates 与 v3 相同。Workspace 使用新入口，旧入口/实例继续工作。

普通一次探索后仍最多 2 次自动正式 Plan，候选数量不计为 Planning iteration。A05 不满意不能无限重新探索；人类明确换方案可以开始一次新的探索。显式 RESUME 才允许从已变化来源重新取快照；停顿期间手工新增 Plan 时，恢复 C04 绑定当前 Plan 指针，同时保留来源新鲜度检查。

## 15. Persistence

Migration `0018_creative_exploration` 新增 `creative_explorations`，并为 `plan_generations` 增加 nullable creative_exploration_id / selected_candidate_id 对。最终 ChapterPlan Schema 不变。

诊断绑定 project、chapter、workflow、Brief、AgentRun、PromptLineage、ContextPackage、来源版本、结果和创建时间。DB 检查精确执行关系、同 Brief/Workflow 的选中绑定、唯一 AgentRun，并禁止 UPDATE/DELETE。既有核心写入接口保持原合同；诊断记录仅创建和只读查询，没有新增 hard delete。

Repository 仅 flush；结果处理与 Workflow application use case 控制事务。探索、Audit、调度原子提交；正式 Plan、Generation lineage、Audit、转移原子提交。并发重复 completion、lease fencing 和 rollback 沿用现有执行链路。

## 16. Authority

诊断记录的 Authority 由服务端产生，为 A7_AI_INFERENCE。它不获得 Plan/User/Canon 的 Authority。服务端核对任务归属、精确 lineage、Brief 引用、当前 Lock/Canon 引用和真实 Creative Freedom。

DB 防止跨 Workflow/Brief 绑定；API DTO 不允许客户端直接授予 Authority。Schema、Prompt 和 Service 在候选安全选择及空 proposal 上使用同一合同。实际自然语言是否违背 Canon 不能仅靠模型声明证明，仍由 A05 和人工审批把关。

## 17. Freshness

模型调用前和持久化前回放 Context Profile、来源快照与 selectors，包括初始空集合后来增加的 Lock/Canon/Profile/批准记录。不会拿 latest 替代 approved。排队的 Plan 固定 selected artifact，不能悄悄改用另一选中项。

来源过期时禁止保存正式 Plan。Brief 仍有效的来源变化，经显式恢复重新探索；Brief 过期使用原 C01 恢复及原始用户输入重新理解。未变化的 BLOCKED 结果不能通过重复 RESUME 自动循环。人工 REJECT/MODIFY/REQUEST_ALTERNATIVE 失效旧选择但保留其不可变历史；current、by-id 和 history 的动态 freshness 与运行时共用这条判定。正常 APPROVE 不使选择失效，也不能让此前已失效的旧选择重新变为 READY。

## 18. Debug UI

复用既有 Debug drawer 显示完整候选比较、选中项、淘汰/风险原因、输入 Brief、ContextPackage、PromptLineage 和 AgentRun ID。只读 current / historical / paginated history API 提供证据，记录状态和动态 freshness 分开展示。

普通 Workspace 仍只有最终 Plan 及批准/修改/换方案按钮，没有候选投票或新增 Gate。离线浏览器回归完成新入口 → Mock Exploration → Plan → A05 → Plan Gate → Debug，未点击批准；截图位于 `backend/.runtime/novel013/debug-exploration.png`。

## 19. Cost / Latency

符合触发条件的初次 Planning 增加 1 次探索任务；LOW 或不允许 LOCAL_CONFLICT 的 MEDIUM 不增加调用。普通 A05 修复复用诊断，不按创意质量自动增加次数。技术重试遵循已有 attempt budget。

本阶段没有真实 Provider 调用，没有付费 token 或真实调用延迟数据。Mock/RecordedProvider 的运行时间不能代替成本结论。后续人工 B 应记录实际探索、Plan、Review 的 calls/tokens/latency。

## 20. Tests

2026-10-05 最终验证：

| 检查 | 结果 |
| --- | --- |
| Backend full pytest | 1,565 passed / 4 skipped / 0 failed / 0 errors |
| 全量覆盖核对 | 1,569 collected，四个分片分别执行 416 / 400 / 393 / 360 项；无漏项、无重复 |
| 013 专项 Contract / Context / Integration | 30 / 10 / 29 项，全部包含在全量 PASS 中 |
| Backend ruff check | PASS |
| Backend ruff format --check | PASS，413 files already formatted |
| git diff --check | PASS |
| Frontend npm test | 152 passed / 12 files |
| Frontend lint / typecheck / build | PASS / PASS / PASS |
| 013 Playwright 浏览器流程 | 1 passed，7.9s，Mock，未批准 Plan Gate |
| Migration | upgrade head → downgrade -1 → upgrade head：0018 → 0017 → 0018，PASS；既有数据往返保持 |
| alembic check | PASS，No new upgrade operations detected |
| Docker build / startup | PASS / PASS，非 root 用户 novel |
| Docker health / health/db | 200 / 200；往返迁移后仍 200 / 200 |
| 原本机服务健康回归 | 8000 health / health/db、5173 页面均 200 |
| Independent Review | PASS，发现的两项 P2 已修复，无剩余 Blocking / Required |

全量沿用 NOVEL-012 的四进程 hash(nodeid) 分片方式：每个进程完整 collection，再选择互斥子集。最终 collection 集合及 JUnit 计数一致。修复旧 latest-Prompt/task-scope 断言后重新执行受影响的完整分片；上述汇总只使用最终四份成功结果。四项 skip 全为真实 Requirement / Planning / Writing / Provider 的付费 opt-in，未传 `--live-model`，不是工程回归漏测。既有 Starlette TestClient/anyio 弃用 warning 不影响结果。

复现命令：Backend `.venv/bin/pytest -q`（最终全量以既有 hash 分片运行 `pytest.main`）；`.venv/bin/ruff check .`；`.venv/bin/ruff format --check .`；根目录 `git diff --check`。Frontend `npm test`、`npm run lint`、`npm run typecheck`、`npm run build`、`npx playwright test e2e/creative-exploration.spec.ts`。隔离 Docker 容器内执行 `alembic upgrade head`、`alembic downgrade -1`、`alembic upgrade head`、`alembic check`。

Docker 最终镜像 `novel013-acceptance-backend:latest`：`sha256:b974f740dc9cd6322c8a3623981e5eb5f0719fbddadcbce09e97bea462f312a2`。关键产品源码哈希与最终代码一致。测试使用独立 novel_os_test schema、Mock 配置、不发布端口、不启动 Worker；临时容器/schema/配置已清理，开发数据库没有执行 downgrade。

本机证据：`backend/.runtime/novel013/pytest-final-summary.json`、`collection-0..3.json`、`pytest-0..3.log/xml`、`docker-evidence-final.json`、`docker-migration-final.log`、`frontend-tests.log`、`frontend-browser.log` 和 Debug 截图。证据目录为 gitignored；没有新增产品 runner 或依赖。

新回归覆盖：专用 Contract 与 Structured Schema 一致、HIGH/MEDIUM/LOW/FOCUSED、重大变更与全不安全阻断、空集新增来源及过期结果、approved/current 历史隔离、未来/正文/被拒候选隔离、已有 Knowledge Firewall、精确选中来源引用、人工换方案和恢复、最多两次自动 Plan、并发重复 completion、事务回滚、DB 不可变/lineage、0018 roundtrip、v1–3 兼容、API 分页及只读 Debug。

独立 Review 已关闭两处 P2：比较理由泄漏到选中投影、暂停期间 Plan 指针变化造成恢复循环。独立回归 33 passed；未发现剩余 Blocking / Required。离线测试均使用 Mock/RecordedProvider 或隔离测试数据库，未 opt-in `--live-model`。

## 21. Case 03 A/B

`evals/creative-exploration/case-03.json` 保存真实历史原文及只读核对的 A baseline：Project `23c028ee-cd94-4965-af85-731e560c9633`，Chapter `2ad1d3b7-afca-445b-9841-76e0e0e0bc6c`，Plan `0a3f3992-005e-4ac4-8f9b-24fe0676427d`，ContextPackage `dae29f6c-b7c8-496b-8ad5-36e2e7ac0b9c`，PromptLineage `82451c23-5841-4b02-831c-d0cdec603294`。

B = NOT_RUN，Human = NOT_EVALUATED。没有为 A 或 B 发起新的付费生成。旧 Profile v1 没有 narrative-perspective 字段，后续比较须冻结其确切 hash 及可比权威资料，记录差异；不能换成新 Profile 却称为同条件 A/B。A baseline Plan 和人工标签不得输入 Agent。

人工表记录 A_BETTER / B_BETTER / TIE，以及机制多样性、Character/Continuity/Audience Fit、故事价值、Authority、重复风险和失败标签。继续真实 B 必须有本阶段的新明确触发，不能沿用 E2E-001R 授权。

## 22. Repetition Context Evaluation

`repetition-context.json` 提供独立的机制级历史场景；`authority-boundary.json` 提供重大变更和知识边界场景；`manual-evaluation.md` 提供定性记录。共五份资产，无新增 runner、评分服务或自动模型调用。

离线测试证实近期 approved Plan 与 final summary 的范围/去重、P0 保留、P1 裁剪、未来/正文/Rejected 隔离。它们没有证明真实模型避开重复；该语义结果仍为 NOT_RUN / PENDING。禁止把评估答案或期望标签作为故事事实输入。

## 23. Known Limitations

真正的机制多样性、Character Fit、Novelty 和故事趣味仍需真实模型与人工验收。模型填写 WITHIN_BOUNDS 不是形式化 Canon 证明；系统维持 A05/人工 Gate，而不新增不可靠 NLP 检查器。

FOCUSED 合理性是有证据的语义判断，离线仅检查理由和结构。近期提示局限于三章紧凑已批准记录，不包含全书知识库。缺失角色输入不会由探索补成事实。真实成本/延迟与 Case 03 B 尚未测量。

本地运行中的旧服务/开发数据库不在本阶段自动部署范围，使用新代码前须升级到 0018 并重启。此次 Docker 验证使用独立 schema，不对原项目执行 downgrade，也不启动真实 Worker。

## 24. Deferred Work

真实 Provider Case 03 B、人工 A/B、真实多章重复/角色评估、实际成本数据；E2E-001R 五章人工连续性验收保持待完成。未开始 NOVEL-014、长程 Planning、Vector RAG、Retrieval Phase 2、故事模板、创意评分/优化器或 A07/Memory 改造。

## 25. Acceptance Result

Engineering Acceptance：PASS。Core regression、Context/Authority/lineage、并发/回滚、前端、迁移、Docker 和独立 Review 均通过，无剩余 Blocking / Required 工程问题。

AI Behavior Acceptance：NOT_RUN / PENDING。Human Creative Evaluation：NOT_EVALUATED / PENDING。

NOVEL-013：CONDITIONAL PASS（工程通过；真实创意/人工 A/B 待验收）。阶段保持 IN DEVELOPMENT / awaiting review。工程结果与真实创意表现分开判断；本报告不以离线 PASS 宣称产品创意质量提升。完成本阶段后停止，等待 Review，不自动开始 NOVEL-014。

## 26. Review Fix — Human Directive Freshness (2026-10-06)

本轮 Review 发现一项 P2：人工要求重新规划后，运行时已使旧探索不可复用，但查询层只回放原始来源快照，current、by-id 和 history 仍将其标为 READY。不可变 TASK_INPUT 不会自动反映后续人工指令，因此仅检查来源不能证明选择仍然有效。

查询层复用 ExplorationPolicy 的人工失效判定，并保留原来源新鲜度检查。该判定按 artifact 自身的 workflow/Brief 绑定，只读取 REJECT/MODIFY/REQUEST_ALTERNATIVE；复用 Repository 的可选决策过滤，其他调用保持默认行为。后续 APPROVE 不会误标当前选择，也不会遮蔽已失效旧选择的历史指令。没有新增状态、接口、依赖、迁移或平行执行链路；记录的 status、body、Authority 和 lineage 保持不可变。

回归先在未修复代码上复现三种人工指令的错误：3 failed / 2 passed；修复后这 5 项全部通过。扩展执行 6 个受影响测试文件，共 107 passed / 0 failed：Exploration integration 31、Contract 30、Exploration Context 与既有 Planning vertical slice/regressions/context-concurrency 46。覆盖三种人工指令后的全部查询、新探索替换、替换方案批准后旧 STALE/新 READY、正常批准、A05 自动修复复用，以及原版本/来源隔离、并发/回滚、0018 往返迁移测试。

Backend ruff check：PASS；ruff format --check：PASS（413 files）；git diff --check：PASS。独立复审：PASS，无 Blocking / Required。本轮是受影响范围的回归，未重新执行上方 2026-10-05 的全量验收或 Frontend/Docker 验收。

证据保存在 gitignored 的 `backend/.runtime/novel013/freshness-fix-before.log`、`freshness-fix-after.log`、`freshness-fix-exploration.log/xml`、`freshness-fix-planning.log/xml`。测试使用 Mock 和独立测试数据库 schema；没有真实 Provider 调用、原项目 Gate 操作、提交推送或服务重启。
