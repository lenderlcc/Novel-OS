# NOVEL-007 — Requirement Agent + Planning Agent

日期：2026-09-15。开发分支：`wfg/novel-007-requirement-planning`。基线：`933a99e`。

## 1. Implementation Summary

实现自然语言章节需求 → CreativeBrief → ChapterPlan → focused Plan Review → Human Plan Gate 的正式业务链。
用户批准后到达 C07_WRITING，不调度 Writing，不生成 ChapterVersion。
复用 NOVEL-001–006 的数据库、事务、Workflow、Worker、Prompt Runtime、Provider、Context Engine 与审批设施。
没有新增第三方依赖；配置继续使用 TOML 文件。先前 NOVEL-006 代码和修复已以中文备注提交并推送到
`origin/wfg/novel-006-context-engine`，提交为 `933a99e`。本阶段代码留在新分支等待 Review。

## 2. Vertical Slice Architecture

```text
Workflow API → WorkflowRuntime → TaskScheduler → AgentTask
    → Worker / AgentRuntime → Prompt Runtime + Context Engine → ModelProvider
    → typed result + Authority / freshness validation
    → PlanningResultService → Repository → PostgreSQL
    → Workflow event → next task / HumanGate → USER approval → C07
```

Provider 执行在短数据库事务之外。任务完成时重新取得项目根锁，核对 lease、Workflow 状态、Context freshness、版本与业务权限，
将 Artifact、Audit、Task、Run、Workflow 变化和下一任务写在同一个 application transaction 中。
Domain 使用标准库 dataclass / enum，不依赖 FastAPI 或 ORM；API 返回独立 DTO。

## 3. Requirement Agent

正式注册 A02 的 `PARSE_CHAPTER_REQUIREMENT`，输出 `chapter-requirement-result.v1`。
模型解释原始需求；服务校验引用、已批准 Requirement 的原类型和完整正文、约束来源、歧义升级条件。
MUST / SHOULD / PREFERENCE / FORBIDDEN / PRESERVE 与 AI assumptions 分开；既有 QUALITY_EXPECTATION / CHANGE_REQUEST 分别无损保留在 quality_expectations / change_requests。长期偏好只记录候选。
Mock 是确定性契约样例，录制的结构化响应用于离线测试，不是自然语言解析算法。

## 4. Requirement Prompt Modules

新增版本化模块 `requirement-agent` role、`parse-chapter-requirement` task、`requirement-normalization` skill。
沿用 `novel-os-core`；所有模块有 manifest、版本、content hash，并纳入 PromptLineage。
Prompt 要求保留限定词、否定和完整语义，区分示例/可选建议与硬要求，禁止把推断提升为用户要求。

## 5. CP-003A

新增 CP-003A v1：raw TASK_INPUT 与目标 Chapter 为 P0，作用域内有效 Requirements / Decisions 为 P1，最小 Project 信息为 P2。
使用明确项目、章节、状态、Authority 与版本查询，不读取完整聊天历史，不进行 Embedding 或相似度检索。

## 6. CreativeBrief Schema

`CreativeBriefOutput` 包含 intent_summary、chapter_objective、五类主要约束、保留既有类型的 quality_expectations / change_requests、required_outcome、desired_reader_effect、
character_focus、plot_focus、creative_freedom、unresolved_ambiguities、assumptions、conflicts、
persistent_preference_candidates、source_refs、confidence。
Brief 的约束总容量与 Plan/Review coverage 均为 512，高于 Profile 200 条 Requirement 的单源上限；引用容量为 1024。整体输出仍受 150,000 字符上限和 Context 预算约束。
约束有唯一 id、原文 text/quote 与 source_type/logical_id/version；已存在 Requirement 的 text 必须等于完整 content，类型不得改写。
Workflow、Chapter、版本、创建时间和 lineage 是服务产生的 Artifact 字段，不允许模型填写。

## 7. CreativeBrief Persistence

新增 `creative_briefs`：每 Workflow 的版本递增，唯一 `(workflow_id, version)`；保存原始输入、input_event_id、
supersedes_id、READY / NEEDS_HUMAN / SUPERSEDED 状态以及完整 typed body 和 lineage。
正文与元数据不可原地修改。数据库仅允许既有 Brief 转为 SUPERSEDED，不允许 UPDATE 正文或 DELETE。

## 8. Ambiguity Handling

只有 HIGH impact、confidence < 0.6、cannot safely infer 同时满足时，才接受 NEEDS_HUMAN 与 escalation。
保存包含问题、影响及需要用户决定事项的 Brief，Workflow 进入 C90_BLOCKED，不调度后续 Planning。
低/中影响歧义记录 assumption 与 confidence 后继续。用户通过需求修正 API 提交完整澄清，重新生成新 Brief。

## 9. Creative Freedom Model

包含 LOW / MEDIUM / HIGH、allowed_operations、scope_description 与固定 `major_changes=PROPOSAL_ONLY`。
局部细节、场景顺序、信息呈现、局部冲突是明确可授权的操作；Planning 不得扩大 Brief 的级别或操作集合。
未指定局部细节不会自动变成 Missing Requirement。自由空间与用户约束分别记录。

## 10. Planning Agent

正式注册 A03 的 `PLAN_CHAPTER`，输出 `chapter-planning-result.v1`。
由当前 READY Brief 和 CP-004 v3 驱动。服务复用原 PlanningService 创建新 ChapterPlan 版本，再保存 PlanGeneration。
生成只具有提案权限；不直接审批、锁定、修改 Workflow 或创建用户 Requirement / Decision。

## 11. Planning Prompt Modules

新增 `planning-agent` role、`plan-chapter` task、`planning-quality` quality profile。
通过既有 TaskDefinition / PromptCompiler 组合模块，AgentRuntime 中没有硬编码业务 Prompt。
强调 Plan 是 intent + structure + constraints，不是 prose blueprint；多个约束可以由同一场景共同满足。

## 12. Planning Skills

使用 `chapter-structure`、`creative-exploration`、`requirement-alignment` 三个版本化 Skill，不拆分额外 Agent。
说明场景功能、局部创作自由、精确约束覆盖、全局约束与角色知识边界；不能把 Global Canon 当作 Character Knowledge。

## 13. CP-004 Integration

新增 CP-004 v3，current CreativeBrief 必须以 exact ref 进入 P0，缺失或 SUPERSEDED 时阻塞。
保留 MUST / FORBIDDEN / PRESERVE、相关有效方向和锁定依赖，前文章节仍只按 approved_version 读取。
同一 Brief 返工时加入精确的上一 Plan / Review；需求修正后，不带入旧 Brief 的 Plan、Review 或用户返工指令。
Workflow 的 plan_version 仍用于版本分配，不能因为切换 Brief 而重置为零。
旧 Mock Planning 继续使用 CP-004 v2，历史 Profile 文件保持不变。

## 14. ChapterPlan Output

包含 objective、required_outcome、opening_function、scenes、character/plot progression、information_release、
foreshadow_actions、ending_function/state、creative_freedom、constraints、preserved_elements、locked_dependencies、
assumptions、risks、proposed_new_elements、proposed_major_changes、requirement_coverage 和 source_refs。
Scene 只接受 purpose/conflict/key_change/information_release/character_state_change/exit_condition 等结构字段。
Coverage 支持 SCENE 和 PLAN_GLOBAL；全局视角或保留约束可用 constraints/preserved_elements 作为证据，不强制虚构 Scene。
Schema 不提供 prose、dialogue、content 或 sentences 字段；自由文本的语义仍由 Prompt 与 focused review 检查。

## 15. Major Change Proposal Handling

重大变化保存 description、reason、affected_scope、required_for_plan 与 `disposition=PROPOSAL_ONLY`。
如果执行 Plan 必须依赖未批准的重大变化，服务强制 DIRECTION_CONFLICT / FAIL。
可选 Proposal 可保留供用户未来考虑；审批 Plan 不会创建 Canon / Decision，也不会改变 Proposal 的 disposition。

## 16. Plan Review Agent

仅给 A05 增加 `REVIEW_CHAPTER_PLAN`，输出 `chapter-plan-review-result.v1`。
新增 `plan-review-agent` role、`review-chapter-plan` task、`focused-plan-review` skill。
只评审本阶段的计划可行性、需求符合性、权限与过度规划，不实现全文质量引擎。

## 17. Plan Review Schema

包含 verdict、hard_gate_issues、quality_issues、requirement_coverage、missing_requirements、forbidden_violations、
locked_conflicts、direction_conflicts、logic_risks、over_specification_issues、recommendations、source_refs、confidence。
verdict 为 PASS / PASS_WITH_WARNINGS / FAIL。覆盖引用必须属于同一 Brief，Scene ID 必须属于被审 Plan，禁止重复覆盖 ID。
服务计算后的有效 verdict 和 issues 重新经过同一 Schema 校验后保存。

## 18. CP-004R

新增 CP-004R v1，必需 exact current Brief 与 Workflow 绑定的 exact Plan，加入有效要求、方向和锁定依赖。
不复用 CP-006 正文 Review Profile。PlanGeneration.brief_id 必须等于当前 Brief，Review 不能跨 Brief、项目或 Workflow。

## 19. Hard Gates

Missing MUST / 未履行已批准 CHANGE_REQUEST、FORBIDDEN violation、LOCKED conflict、approved direction conflict、required outcome impossible、
major logic break、major misunderstanding 均为硬失败，不能用高 confidence 或其他评分平均掉。
服务额外检查强制覆盖、原文约束保留、required major proposal，以及所有选中的锁定 Requirement / Decision / Plan / ChapterVersion 依赖。
被评审 Plan 是 subject，不要求成为自身的锁定依赖。软质量问题、低风险和过度具体化建议保留为 warning。

## 20. Planning Iteration

PLAN_REVIEW_FAILED 返回 C04，增加 planning_iteration_count，创建新的逻辑任务和 ChapterPlan 版本。
旧 Plan、Review 和 Generation 不改写。同一 Brief 下，下一次 Planning Context 包含具体失败报告。
格式错误、模型调用错误及 lease 恢复继续沿用原技术重试规则，不增加业务 iteration。

## 21. Human Plan Gate Integration

复用既有 HumanGate，只有 exact passing review 才能进入 C06。
USER APPROVE 必须同时提交当前 expected_state_version 与 Gate 的 expected_artifact_version；服务审批精确 Plan，
更新 Chapter.approved_plan_version 并到 C07。当前提案指针与批准指针继续分离。
对象级 Lock 沿用已有 Lock API；不增加场景字段级锁定子系统。

## 22. User Reject / Modify / Alternative

复用 REJECT / MODIFY / REQUEST_ALTERNATIVE 三种决定及 reason，返回 C04 并生成新 Plan。
下一任务包含 USER_PLANNING_DIRECTIVE，绑定原 Plan ID/version 和具体用户反馈；旧 Plan 不被覆盖。
只有属于当前 Brief 的反馈才进入任务。需求整体修正使用独立 correction API，不将旧指令冒充新 Brief 的需求。

## 23. Versioning

Brief：Workflow 内单调递增。Plan：沿用 Chapter 的 current_plan_version / approved_plan_version 及乐观版本检查。
Review 绑定具体 Plan ID 与 Brief ID。生成结果按 lease/run 去重，数据库唯一约束提供第二层保护。
并发投递同一下一版本结果得到 APPLIED + DUPLICATE，只有一个 PlanGeneration 和一个新 Plan。

## 24. Authority Validation

闭合 Pydantic Schema 拒绝客户端或模型伪造 status=APPROVED、authority_level、approved_at、version、system actor、next_event。
既有 AuthorityValidator 禁止 APPROVE / LOCK / UNLOCK / COMMIT_CANON / SET_WORKFLOW_STATE /
CREATE_USER_REQUIREMENT / CREATE_USER_DECISION。服务检查引用属于实际 Context 快照，逐条校验锁定依赖且禁止遗漏。
API 不提供任意执行 Agent 的入口，Fake Executor 不能执行正式业务 Workflow。

## 25. PromptLineage

A02、A03、A05 均通过 NOVEL-005 Runtime 生成不可变 PromptLineage，绑定 Task、Run、模块版本/hash、输出 Schema、
ModelProfile、渲染输入及 usage 等原有执行记录。Artifact 保存 prompt_lineage_id，数据库校验其与 run/context 一致。

## 26. ContextPackage Lineage

三类 Artifact 保存 context_package_id 与被选中来源的 source_versions。
复用构建前后及 Provider 执行后的 freshness 校验；新增 Draft 不覆盖批准上下文，外部新 Plan 会使旧 Review 执行失效。
旧快照保持不可变，Inspector 可以追溯，不把 stale snapshot 改写成新上下文。

## 27. Metrics

新增 Workflow 范围查询：需求成功率、NEEDS_HUMAN 比例、修正次数/比例、confidence 分桶、首次内部 Review 是否通过、
planning iterations、首次用户决定是否批准、拒绝/修改/替代次数、hard gate 分布及 technical retries。
分母为空返回 null。修正比例为 correction events / 已生成 Brief 数；first-pass 返回本 Workflow 的布尔值，
跨 Workflow 的总体 rate 可由调用者汇总。当前没有单独的 metrics 持久化表或分析平台。

## 28. Persistence

新增三张表：creative_briefs、plan_generations、plan_review_reports，不重复创建 ChapterPlan。
共同关联 project/chapter/workflow/run/prompt_lineage/context_package；FK、唯一约束和触发器约束来源一致性及不可变性。
生成的 ChapterPlan payload 也受不可变触发器保护，审批/锁定等生命周期动作仍由原服务处理。
Repository 只查询、add、flush；事务完成由 application service 控制。Artifact 版本创建同时写 AuditRecord。

主要新增文件组：

- Domain / ORM / Repository：`backend/novel_os/{domain,models,repositories}/planning.py`。
- Service：`planning_policy.py`、`planning_context.py`、`planning_results.py`、`planning_queries.py`。
- Schema / Mock：`agents/planning_schemas.py`、`agents/planning_mock.py`。
- API：`api/planning_schemas.py`、`api/planning_routes.py`。
- Workflow definition：`workflow/definitions/chapter-planning.v1.yaml`；三个 Context Profiles；十二个 Prompt 模块目录。
- Migration：`alembic/versions/0008_requirement_planning_requirement_and_planning_evidence.py`。

对旧模块的修改限于注册、任务定义选择、正式结果处理、Context source reader、Workflow 业务入口和调度接入；没有重建基础设施。

## 29. API Changes

以下路径均位于 `/api/v1`，以 Workflow 为业务入口：

| Method / Path | 行为 |
| --- | --- |
| POST `/workflows/chapter-planning` | 接受自然语言与 Chapter 身份，创建 C00 Workflow |
| POST `/workflows/{id}/events` | 复用 USER_SUBMITTED 显式提交及已有控制命令 |
| POST `/workflows/{id}/requirement` | 带 state/Brief expected version 修正需求 |
| GET `/workflows/{id}/creative-brief` | 当前 Brief 与状态/lineage |
| GET `/workflows/{id}/creative-brief/versions/{version}` | 历史 Brief |
| GET `/workflows/{id}/planning/plan` | Workflow 绑定 Plan + Generation |
| GET `/workflows/{id}/planning/plan/versions/{version}` | 同一 Workflow 的历史 Plan |
| GET `/workflows/{id}/planning/review` | 当前 Plan 的有效 Review |
| GET `/workflows/{id}/planning/history` | 分页三类证据 |
| GET `/workflows/{id}/planning/metrics` | Workflow 统计 |
| POST `/human-gates/{id}/decision` | 复用既有版本绑定的人类决定 |

README 已补充运行、查询、审批、澄清、TOML Provider 配置和 opt-in smoke 示例。

## 30. Tests Added

新增 133 个离线测试（55 个合同/单元用例，78 个业务集成/数据库/并发/E2E 用例），覆盖 Schema、权限、引用、业务 Service/API、Repository、数据库不可变约束、版本、并发及 E2E；另加一个默认跳过的真实模型 E2E。
文件：`test_planning_contracts.py`、`test_planning_vertical_slice.py`、`test_planning_regressions.py`、
`test_planning_context_and_concurrency.py`、`test_planning_review_fixes.py`、`test_planning_migration.py`、`test_planning_live.py`。
`planning_support.py` 提供录制响应；原 Driver 抽至 `workflow_test_support.py`，避免直接导入 pytest conftest 造成重复夹具实例。
旧迁移回归显式定位原 revision，避免新增 head 改变 `downgrade -1` 的原测试目标。

## 31. Requirement Agent Test Result

覆盖五类需求的录制自然语言解释、来源原文、Schema、明确自由空间、长期偏好候选不提交、推断不冒充用户约束。
对七类已批准/锁定 Requirement 参数化测试遗漏、重新分类、截断限定语均拒绝；七种合法原类型完整走通。新增 31 条同类 MUST 全链路回归，以及 Profile 200 项容量与输出合同对齐测试。
结果纳入最终 pytest 记录。这些测试验证合同和边界，不宣称已测量真实模型的中文解释准确率。

## 32. Ambiguity Escalation Result

LOW / MEDIUM 推断继续，assumption 可见；HIGH + 低 confidence + 无法安全推断阻塞。
confidence 恰好 0.6 不触发低置信门槛；可安全推断的 HIGH 歧义不自动升级。
NEEDS_HUMAN 不产生 Plan 或后续任务；不必要升级被拒绝。

## 33. Planning Test Result

验证新 Plan 创建、完整结构、coverage、重大 Proposal 边界、锁定依赖、自由空间不能扩大，以及 Scope 外正文字段拒绝。
锁定 Decision 或 Requirement 被遗漏时禁止落库；合法锁定 Requirement 贯穿 Brief → Plan → Review。

## 34. Plan Review Test Result

所有硬问题覆盖名义 PASS；required major proposal、缺失 coverage/约束均 FAIL。
全局 PRESERVE 的 PLAN_GLOBAL 覆盖不因 scene_ids 为空被误拒，缺失全局证据仍 FAIL。
Plan 生成后新增的 Requirement Lock 也由 Review 兜底发现，不能用模型 PASS 绕过。
软质量与 over-specification 返回 PASS_WITH_WARNINGS。

## 35. Human Gate Test Result

验证精确 Plan 审批、stale expected version 返回 409、AI 无批准权限、REJECT / MODIFY / ALTERNATIVE 进入下一轮。
修正需求关闭旧 Gate；C07 停止，没有 Writing task / draft。C07 也不会被后台 backfill 误调度或阻挡旧 Mock Workflow。

## 36. Planning Iteration Result

Review FAIL 和用户返工均创建新 Plan 版本与新业务 iteration；旧 Plan/Review 可查询且不可修改。
FORMAT_ERROR_ONCE / MODEL_ERROR_ONCE 重试不增加 planning_iteration_count。
同一 Brief 返工使用旧 Review/反馈；新 Brief 排除旧证据但继续 Plan 版本序列。

## 37. E2E-A Result

PASS 路径：raw input → A02 / Brief v1 → A03 / Plan v1 → A05 / PASS → HumanGate → USER APPROVE → C07。
校验三类证据的 Run、PromptLineage、ContextPackage，Chapter approved_plan_version=1，正文 current/approved version 均未创建。

## 38. E2E-B Result

自修复路径：Plan v1 → Review FAIL → iteration 2 → Plan v2 → Review PASS → HumanGate → C07。
v1 内容仍然保留；v2 为独立版本，业务迭代计数为 2。

## 39. E2E-C Result

重大歧义路径：A02 → NEEDS_HUMAN → Brief NEEDS_HUMAN + Workflow BLOCKED。
没有 Plan、没有 A03 调用，Worker 下一轮无可执行任务。

## 40. Real Provider Smoke Result

SKIPPED：本次未执行任何付费模型调用。`test_planning_live.py --live-model` 提供显式 opt-in 的真实 A02 → A03 → A05 链路，
使用既有文件配置、隔离测试 schema，最多七次尝试；检查 lineage/context 与最终 HumanGate，usage 和 ModelProfile 沿用已有 Run/PromptLineage 查询。
默认 pytest 跳过此测试和 NOVEL-005 原有真实 Provider smoke。真实语义质量仍需要用户授权后的 smoke/评估。

## 41. Migration Result

已执行并通过 `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` → `alembic check`。
实际版本为 `0007_context_engine → 0008_requirement_planning → 0007_context_engine → 0008_requirement_planning`。
`alembic check`：No new upgrade operations detected。容器内 current 也是 0008 head。
附件中的 0006/0007 编号与已完成的 Context Engine head 冲突，因此新增 0008，未修改 0001–0007 迁移。
隔离数据库往返测试逐表对比旧数据，含新业务 Workflow 的旧表记录，确认 Core / Workflow / Agent / Prompt / Context 历史保留。
降级会删除 007 三张证据表；重新升级不会恢复这些已删除证据。旧 simulation 检查以 NOT VALID 恢复，保留既有历史同时约束旧版本新增写入。

## 42. Full pytest Result

初次实现执行 `.venv/bin/pytest -q --tb=short`：**642 passed, 2 skipped, 2 warnings in 277.55s**。后续 Review 修复及最新验证见第 49 节。
包含 NOVEL-001–006 原有 509 个通过用例，以及新增 133 个离线通过用例；两个跳过项均为显式 opt-in 真实模型测试。
专项独立复核的 96 个业务/合同用例也全部通过。

测试使用本机 PostgreSQL 测试服务的独立 schema；开发数据不用于测试断言。
两个既有依赖弃用 warning 来自 Starlette testclient/httpx 和 anyio BlockingPortal，不影响结果。

## 43. Lint Result

`ruff check`：PASS；`ruff format --check`：PASS；`git diff --check`：PASS。
`uv build`：wheel 与 sdist 均成功。打包包含新增 Prompt、Context Profile 和 Workflow definition。
没有新增依赖或变更 lockfile。

## 44. Docker Result

`docker compose build backend` 与 `docker compose up -d backend`：PASS。
`GET /api/v1/health` 返回 200 / `{"status":"ok"}`；`GET /api/v1/health/db` 返回 200 / `{"status":"ok","database":"ok"}`。
最终 backend / postgres / postgres-test 均为 healthy；容器复用 PostgreSQL 服务和原 TOML 配置，后台 Worker 没有自动开启真实 Provider。

## 45. Acceptance Criteria PASS / FAIL

下表编号对应用户附件中的 50 项关键测试；语义解释项以录制响应验证结构化合同，真实模型效果见第 40 节。

| 编号 / 验收内容 | 结果 | 证据 |
| --- | --- | --- |
| 1–7 自然语言、Schema、五类约束、自由空间 | PASS | contracts、recorded_language_interpretations |
| 8–11 歧义、assumption、NEEDS_HUMAN 不规划 | PASS | ambiguity 参数化测试、E2E-C |
| 12–13 无伪造 MUST / 持久化用户偏好 | PASS | invalid_requirement、categories_and_persistent_candidate |
| 14–16 Brief immutable / superseded / exact ref | PASS | DB immutability、correction、context 回归 |
| 17 Draft 不泄漏 | PASS | 前文 v2 approved / v3 current 回归 |
| 18–20 Plan、coverage、LOCKED Decision | PASS | E2E-A、plan defects、lock 校验 |
| 21–22 Proposal 不自动批准、无正文输出字段 | PASS | optional_major_proposal、scene schema |
| 23–29 Review PASS/FAIL 和全部硬门槛 | PASS | effective_verdict 参数化测试、E2E-B |
| 30 过度规划提示 | PASS | soft_quality_warns、Prompt / typed issue |
| 31–34 新版本、旧版本、业务/技术计数 | PASS | E2E-B、retry、immutability |
| 35–38 HumanGate、AI 权限、exact/stale approval | PASS | E2E-A、authority、stale_human_plan |
| 39–41 Reject / Alternative / Modify | PASS | human_feedback 参数化回归 |
| 42–45 PromptLineage / exact ContextPackage | PASS | E2E-A 三类 artifact、数据库绑定校验 |
| 46–49 权限、cancel stale、跨项目、rollback | PASS | negative / concurrency / rollback tests |
| 50 NOVEL-001–006 全量回归 | PASS | 见第 42 节 |
| 重复并发结果只创建一个下一 Plan | PASS | APPLIED + DUPLICATE，数据库计数为 1 |
| Migration / lint / build / Docker | PASS | 第 41、43、44 节 |
| 真实模型 smoke | SKIPPED | 只提供 opt-in，未发起付费调用 |

## 46. Architecture Deviations

- 迁移编号使用 0008：0007 已属于 NOVEL-006，保留历史迁移不改写。
- 增加 `chapter-planning` 非模拟 definition；保留已确认的完整 Mock definition。C02/C03 沿用控制状态，内部确定性推进。
- 沿用 C00 创建后 USER_SUBMITTED 显式提交语义，没有重写 Workflow API 或新增任意 Agent 执行入口。
- 完整 AI Plan 保存在 PlanGeneration 的 typed JSONB，关联现有 ChapterPlan；不重复建 Plan 领域表。
- 测试 Driver 做局部抽取，解决 conftest 重复加载，未改变生产架构。

独立审查由两个不同模型的只读 review 执行，范围覆盖业务权限/硬门槛与 Context/persistence。
已修复：锁定 Requirement 遗漏、PREFERENCE 升级 MUST、全局覆盖误拒、修正 Brief 后沿用旧 Plan/Review/directive、
Review 锁定兜底只检查 Decision；复核发现的七类 Requirement 映射/容量兼容性也已修复。同时修复 C07 backfill 影响旧任务的问题，并添加回归。
初次只读复核：业务审查专项 96 passed；Context/持久化审查专项通过。当时未发现未解决的 Required / Critical finding；后续独立 Review 发现的五项来源生命周期和审批问题见第 49 节。

## 47. Known Issues

- 真实 Provider smoke 未运行；Mock/录制测试不能证明实际模型对任意中文需求的解释准确率。
- 原文引用、类型一致、版本与权限可由服务验证；自然语言含义、否定范围、场景是否真正满足要求仍需 focused model review 和最终用户审批，不能以引用校验代替语义评估。
- 原有本机单用户控制面沿用可信用户身份，不新增多租户认证系统。
- API/模型输出有字段与大小限制；过大的需求/产物按既有验证与失败处理机制拒绝，不无限扩展 Context。
- 业务 FAIL 可继续规划循环，仍需操作方按既有 Pause/Cancel 控制；本阶段未增加费用或业务迭代预算平台。
- 降级移除 007 证据，生产数据保留需备份；已有依赖的两个弃用 warning 尚在。

## 48. Deferred Items

NOVEL-008 Writing / 正文 / ChapterVersion 生成；NOVEL-009 Full Quality Engine；NOVEL-010 Revision；
NOVEL-011 完整人类反馈诊断；NOVEL-012 Memory Commit。
未实现 Character / Event / Canon Memory、Vector/Graph DB、Redis、Kafka 或 Frontend。
字段级 Lock Element、跨 Workflow 统计产品和真实模型质量评估留待各自明确范围。本阶段结束后等待 Review，不继续后续 Ticket。

## 49. 2026-09-15 Review 修复

先检查根因和隔离 PostgreSQL 复现，再实施局部修复。新增回归文件为 `backend/tests/core/workflow/test_planning_source_lifecycle.py`。

| Review 问题 | 确认的根因 | 修复行为 |
| --- | --- | --- |
| CreativeBrief 来源过期 | READY/Brief version 只表达产物状态；新 Run 的 Context freshness 没有追溯 Brief 的 A02 来源 | `PlanningFreshness` 重放产物绑定的原 Context Profile、Request 和 selector 快照，检测有效来源新增、替换、消失以及 Authority 变化；A03/A05 模型前和结果落库前检查；失效时 BLOCKED，RESUME 回 C01 生成新 Brief |
| A05 遗漏锁定依赖 | 通用 Context 只展开已批准 Plan 的依赖，而 A05 的目标是 PROPOSED | 从工作流精确绑定的 PlanGeneration 读取依赖及版本，核验活动 Lock，加入 explicit/required refs；依赖失效时回 C04，不替换成 latest |
| Gate 审批过期 Review | expected_version 保护 Plan 自身，但没有检查 Review 来源快照 | 审批写入前校验 Review 来源；过期 Gate 标记 STALE、返回 HTTP 409，Plan/批准指针不变；按根因恢复到 C01 或 C04 |
| 通用审批绕过工作流 | Core Plan 审批未区分手工 Plan 与 Agent 生成 Plan | Service 根据 PlanGeneration 判断来源；生成 Plan 必须绑定正确且 WAITING 的 PLAN_APPROVAL Gate、C06 工作流和仍有效的评审；通用入口返回 AUTHORITY_DENIED，手工 Plan 保留原审批行为 |
| A05 RESUME 重复阻塞 | 通用 BLOCK 丢失 Plan 版本漂移的恢复位置，C05 恢复不刷新绑定 | 根据实际数据库来源判定恢复状态；Plan 漂移回 C04，RESUME 更新当前 Plan 绑定；已有 v2 时重新规划生成 v3；来源变化回 C01 时同样刷新绑定 |

产物 freshness 复用 NOVEL-006 的不可变 ContextPackage 和 FreshnessValidator，但不以旧 Run 的 workflow state_version 判断跨阶段产物是否有效。Brief 校验保留 Chapter 的标题、序号、状态和 Authority 检查，仅排除其后续 Plan 创建/审批产生的 Chapter version/timestamp 变化；Review 的来源在审批自身写入之前完整比较。

事务仍由 Service / Workflow use case 控制，使用原 Project 锁顺序和审批 savepoint。Repository 仅查询和 flush，不增加 commit；不改 migration、数据库表、API DTO、配置方式或依赖；不实现后续 Ticket。

专项验证：**59 passed**，其中新增 **18** 个参数化回归场景。涵盖来源集合新增/替换/移除、未批准 Draft 不污染 Brief、审批失败不改批准指针、无 Review/FAIL/等待 Gate 时的通用审批拒绝、Plan 漂移发生于模型调用前/期间、锁定依赖于评审前/期间/Gate 后失效、完整恢复至有效 Gate。原先“Requirement 在 Plan 后加锁则 Review FAIL”的测试改为更早的来源失效拦截，并断言零模型调用、重解析、旧版本保留和新版本评审通过。

CLI 迁移在配置文件指定的独立测试 schema 中执行：`alembic upgrade head` → `0008_requirement_planning`；`alembic downgrade -1` → `0007_context_engine`；`alembic upgrade head` → `0008_requirement_planning`，全部 PASS，结束后清理测试 schema。

独立复核未发现新的 Required 问题；复核者单独执行规划、来源生命周期及旧工作流回归：**99 passed**，并独立验证 Review 后释放依赖锁会使审批返回 `409 CONTEXT_STALE`。

最新全量执行 `.venv/bin/pytest -q --tb=short`：**660 passed, 2 skipped, 2 warnings in 267.62s**。两个 skip 均为需显式开启 `--live-model` 的真实 Provider 测试，本次没有付费模型调用；两个 warning 为既有 Starlette/httpx、anyio 弃用提示。

`ruff check`、`ruff format --check`（196 个文件）及 `git diff --check` 全部 PASS。五项 Review 问题已修复并经回归及独立复核验证；停在 NOVEL-007，等待用户 Review。
