# NOVEL-010 — Targeted Revision Engine

日期：2026-09-24。分支：`wfg/novel-010-revision-engine`。

本报告区分工程验证、模型行为验证和人工文字评价。Mock 测试通过不代表文学质量已通过。最终执行结果见第 20～26 节。

## 1. Background

在 NOVEL-001～009、009A、STYLE-001/002 和 UX-001 基础上，增加用户主动触发的 Review → RevisionPlan → Revised Draft → Re-Review 闭环。原先审阅发现问题后只能展示，无法产生具有明确修改依据的新版本。

开发分支从当时的最新远端 main `2e898e1` 建立，再快进纳入已完成的 009A `05b7fcd`，使 010 使用最新正式 Dialogue / Character Review；未改写 main 或远端历史。本次未执行 commit/push，现有本地测试及其他未提交文件保留。

## 2. Scope

新增三类 immutable Revision evidence、A06 两阶段任务、版本与 Authority 验证、显式请求 API、现有 Workflow 的最小扩展，以及轻量前端修改入口/版本切换。

主要实现文件：

- `backend/novel_os/domain/revision.py`、`models/revision.py`、`repositories/revision.py`。
- `backend/novel_os/revision/{schemas,policy,mock}.py`。
- `backend/novel_os/services/revision_{binding,context,results,workflow}.py`。
- `backend/novel_os/api/revision_routes.py`、`backend/alembic/versions/0012_targeted_revision.py`。
- `backend/novel_os/context/profiles/CP-007.v3.json` 与五个 A06 Prompt 模块。
- 现有 Agent registry/runtime 集成点、WorkflowRuntime、Context reader、Console composable/视图/Debug/进度组件。

没有新依赖，没有新增 Provider、第二套状态机、Vector RAG、Redis 或 Kafka。正式规范更新 02/04/05/06/07，并新增 `docs/specs/08-Revision-Engine.md`。

## 3. Revision Principles

以原正文为底稿，处理结构化 Review 的高优先级问题，保留已有优点和批准方向。Review 是诊断，不是新故事授权；修改成功不能自动批准正文或提交 Canon。用户一次点击只授权一次修改及其重审。

## 4. A06 Revision Agent

复用 `A06_REVISION`，拥有 `PLAN_CHAPTER_REVISION` 与 `REVISE_CHAPTER` 两个任务。不新增 Revision Planner Agent。Agent 仅返回受约束的结构化结果，无 SQL/Repository/Workflow set-state 工具，不能自行创建任务或批准故事。

本机 `chapter-quality` 执行范围包含两个 A06 task type；`chapter-writing` 等较窄范围保持原有限制。UI 点击前重新读取 execution config，避免页面缓存误导。

## 5. RevisionPlan

字段包含 kind/chapter/source Draft/source Review、target_issue_ids、preserve_items、revision_targets、do_not_change、revision_strategy、scope、blocked_reasons、source_refs、confidence。scope 默认 TARGETED，另支持必要的 FULL_PASS。

服务从 source Review 原始 issue 索引生成稳定 UUID；同一 Code 的多个问题不会合并丢失。目标必须完整分配为 safe target 或 blocked reason，不能遗漏、重复或虚构。问题 Code、severity、evidence 必须与原问题一致。KEEP 与 DO_NOT_CHANGE 使用服务提供的 immutable 条目 ID，完整值保存在 request contract 和 Context 中，模型不能改写其含义。

## 6. RevisionResult

保存 source Draft、source Review、RevisionPlan、addressed/unresolved issues、preserved items、declared changes、blocked reasons、source refs 和 confidence。addressed 与 unresolved 必须完整覆盖原选择问题，不能把 plan 中明确阻塞的问题宣称修复。

执行输出带正文，持久化 metadata 不复制大段正文，而是关联新的 ChapterVersion 和 SHA-256。安全阻塞可返回 null content。低置信度、没有安全 target、没有实际修改或没有可处理问题不会伪造新版本。

## 7. Authority Boundary

A0～A7 顺序保持不变。Review/Revision advice 以 A7 进入 Context，不能升级成 Requirement、Lock 或 System hard constraint。禁止 proposed_changes/memory_proposals 绕过正文输出通道；Plan、Brief、Profile、Lock、Canon 均不由 A06 写入。

DO_NOT_CHANGE 显式包含 Brief MUST/FORBIDDEN/保留项、approved Plan、相关 approved/locked Requirement/Decision、锁定依赖、已批准相关前章和 approved Profile/POV。当前待修正文不整体作为不可变故事约束，避免禁止一切修改。

## 8. Strength Preservation

Review strengths 的描述、证据、保留方向进入 exact Revision Context，与 Brief/Plan 保留项一同组成 KEEP。Validator 要求 plan/result 完整引用这些条目。

这能证明模型接收了保留要求且不能在 metadata 中删除要求，不能单靠引用 ID 证明 prose 实际保留了人物犹豫或替代选择的吸引力；后者由 A05 与人工阅读验证。

## 9. Minimum Necessary Change

Prompt 明确要求以现有 Draft 为底稿、优先保留/删除冗余/局部替换/局部重组，不为重写而重写。允许连续对白或多个段落一起修改，不限定机械单句 patch。

针对结构化对白、抽象 stakes、过度解释、无选择细节、过度闭合、人物声音和角色工具化，提供通用方向。不得靠随机沉默、固定打断比例、重大新背景或机械删心理描写“修复”。正式 Prompt 未写入 Case 04/05 人物、剧情或专属答案。

## 10. Context Integration

复用现有 Context Engine。CP-006 已属于 Quality Review，因此扩展既有 Revision profile 为 **CP-007 v3**，不抢占 CP-006、不改旧 CP-007 v1/v2 的定义。

P0 包含 source Draft、Review、immutable authority contract、Brief、approved Plan、approved WritingProfile，以及执行阶段的 exact RevisionPlan。P1 只取相关依赖和最近最多三章 approved 内容；不读未批准 Draft、未来章节或整项目数据。

Revision 必须有 approved WritingProfile，且原 Review 已绑定该版本。无 Profile、仅有 Draft Profile，或审阅后才批准 Profile，都不能直接开始修改；用户需先批准并明确重新审阅。Service、CP required selector 和数据库约束三层保护，不静默补默认值。

尚未建立的 Character/Canon Memory 不在本 Ticket 虚构数据库。延续 Global Canon ≠ Character Knowledge，未知事实不能作为已有 Character Knowledge 使用。

## 11. Prompt Versions

新增以下 immutable v1 模块及内容 hash manifest，输出 schema 由 Pydantic 提供：

| 模块类型 | 模块 ID | 版本 |
| --- | --- | --- |
| agent_role | revision-agent | 1 |
| task_template | plan-chapter-revision | 1 |
| task_template | revise-chapter | 1 |
| skill | targeted-revision | 1 |
| quality_profile | revision-quality | 1 |

每次执行保留 PromptLineage、ContextPackage、AgentTask、AgentRun 和既有 ModelProfile provenance；历史模块不原地覆盖。

## 12. Versioning

新增 `revision_requests`、`revision_plans`、`revision_results` 三表，禁止 UPDATE/DELETE。每次成功执行生成 source.version+1 的 immutable ChapterVersion，parent/supersedes 指向确切 source，source=AGENT、authority=A7、status=DRAFT，未批准、未锁定。

只更新 current_version，不改变 approved_version。原 Draft 与原 Review 保留；新 Review exact bind 新 Draft。DB 同时验证 current pointer、版本号、parent/supersedes、非空内容与 hash，防止 Service 之外伪造 successor lineage。

## 13. Freshness

Request 固定 source Review/QualityBinding/ContextPackage 及 CP-007 snapshot/hash。QualityBinding 已固定 Brief、approved Plan/Profile、Draft 和相关 source fingerprints。Context 构建、Provider 调用前及结果落库前检查这些输入。

Draft、Review、已批准 Plan/Profile、相关 Decision/Lock 等变化即 CONTEXT_STALE/BLOCKED，不偷偷换 latest。创建尚未批准的新 Plan/Profile 不影响已批准版本；测试明确检查这些 Draft 的秘密字符串没有进入 A06 Context。

## 14. Workflow Integration

复用 `chapter-planning.v3`：

```text
C10/C11 WAITING_HUMAN
  → USER REQUEST_REVISION
  → C10 WAITING_AGENT / A06 PLAN_CHAPTER_REVISION
  → REVISION_PLAN_READY
  → C10 WAITING_AGENT / A06 REVISE_CHAPTER
  → REVISION_READY / 新 Draft
  → C08 → C09 / A05
  → C10 或 C11 WAITING_HUMAN
```

新增 active revision_request_id。状态推进仅由 deterministic Workflow Service 发出合法事件，A06 不能选择 next_state。旧 v1/v2 与 simulation 行为保留。

API：`POST /api/v1/workflows/{id}/revision`，显式传 event_id、expected_state_version、source_review_id、expected_draft_version；`GET /api/v1/workflows/{id}/revisions?limit=100&offset=0` 返回 request/source_binding/plan/result。history 使用批量 join 与分页。

Request、事件、状态、task 同事务；结果、Draft、Audit、task terminal state、下一事件/task 同事务。Repository 只 flush。复用 Project → Workflow → Task 锁、optimistic version 与 worker lease fencing。

## 15. Re-Review

成功修改自动进入既有 NOVEL-009/009A Compliance + Narrative 两遍审阅，两个 pass 属于同一次正式 A05 Review。新 Review 不继承旧 verdict，不降低判断标准，可以报告修改引入的新问题。

技术 Provider 失败使用既有 retry/lease。安全性无法完成属于业务 BLOCKED，保留原因和 evidence，不当作 Provider 错误重试。业务阻塞不能直接 RESUME 重复写 immutable artifact；界面提供显式重新审阅出口。技术重试耗尽保留原恢复入口，源变化时也可明确改为重新审阅。

## 16. Iteration Limit

一个 request 至多一个 plan、一个 result、一个 successor Draft。相同 event 重发幂等；并发不同 event 只有一个成功；重复/迟到结果不产生第二份 Draft。

Review v2 即使 FAIL 也清除 active request 并停止在人工状态，不调度 A06 v3。再次修改必须由用户基于新的 Review 再点击。普通 PASS_WITH_WARNINGS/FAIL Review 不会自动触发第一次 Revision。

## 17. Frontend

沿用当前创作工作区，增加“修改”进度和“根据审阅修改”主操作，PASS 隐藏主修改按钮。无已批准 Profile 的历史审阅显示补齐偏好并重新审阅的说明；未批准时点击重审不会发送模型任务。

阶段文案为分析修改范围、修改正文、重新审阅；原因、declared changes 和审阅结果简单呈现。v1/v2 轻量切换，Review 按 exact Draft 和 workflow 选择，并显示 Review 版本及对应 Draft 版本。Human Evaluation storage key 与组件 key 绑定 Draft，不继承旧评价。Prompt/Context/Run 原始信息保留在 Debug。

浏览器测试覆盖完整 Mock 路径、请求已接受后刷新、v2 + Review v2、切回 v1 + Review v1、FAIL 后 STOP。截图保存在 `/tmp/novel010-revision-workspace.png`；不包含真实用户正文。

## 18. Case 04 Evaluation

状态：**NOT_RUN — 等待用户显式 opt-in**。没有调用真实 Provider，没有新建人工 Case。

固定历史输入：Project `23c028ee-cd94-4965-af85-731e560c9633`，Chapter `119ae046-5b27-4b71-9ad2-eaae9518af99`，Draft v1 `86c02b4b-7117-4ee0-9528-77870b30fc08`，hash `4ed3c41579cd11b3dca885ceb521af32ab230141ec69bd261139a328c9fb6f49`。历史导出有 approved Profile v1/current Draft Profile v2，没有正式 AI Review，因此需要先由用户明确生成 Review。

模板：`evals/revision/010/case-04/{manifest.json,evaluation.md}`。人工检查人物具体性、冲突对称感、对白、搭棚过程压缩，同时保留双方立场合理、不真正破裂、轻松结尾和未彻底解决的矛盾。

## 19. Case 05 Evaluation

状态：**NOT_RUN — 等待用户显式 opt-in，且历史输入缺少 approved Profile**。

固定历史输入：Project `14c99102-f5b0-4a0f-82b6-be829fae15b5`，Chapter `23208bf8-ecc7-4054-8ae9-46cf4bc15181`，Draft v1 `e3e88aaf-ae0b-48fe-a230-9893b79761cb`，hash `f9b2957d6785af1adee9cb79860ca4833d6afa08eec7f86582eb28774cf4b6cf`；历史 Review `55bad299-a861-4a62-89db-f7003d310ea3`。

不能借用 Case 04 Profile，不能以无 Profile 的旧 Review 启动 010。需用户先为 Case 05 批准 Profile、明确重新审阅并记录新 Review；补齐输入后的结果不能声称与旧输入完全相同。

模板：`evals/revision/010/case-05/{manifest.json,evaluation.md}`。检查对白程序感、stakes 具体性、重复解释、代入感，以及继续原计划、替代选择吸引力、真实犹豫、无重大新 Canon。两例均填写 Improved=YES/PARTIAL/NO、Strength Lost=YES/NO、New Major Problem=YES/NO，不建立数字评分。

## 20. Test Results

| 检查 | 最终结果 |
| --- | --- |
| Backend 全量 `pytest -q`（001～010） | PASS，1201 passed / 4 skipped，1159.36s |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS，312 files already formatted |
| `git diff --check` | PASS |
| Frontend `npm test` | PASS，7 files / 89 tests |
| Frontend lint / typecheck / build | PASS |
| Playwright Revision E2E | PASS，1 test / 11.1s |

四个 skip 均为未显式启用 `--live-model` 的付费测试：Requirement、Planning、Writing 与 Provider smoke。不是跳过失败测试。本次真实 Provider 调用为零。两个 warning 来自现有 Starlette TestClient 的 httpx/AnyIO deprecated API，不影响断言结果，本 Ticket 未升级依赖。

010 专项共 78 个后端参数化用例，全部包含在上述全量通过结果中；前端 Revision 专项 16 个，包含在 89 个测试中。全量原始日志：`/tmp/novel010-final-verified-pytest.log`；前端日志：`/tmp/novel010-front-test-final.log`、`/tmp/novel010-browser-final.log`。Ruff、format、lint、typecheck、build 及 diff 检查均为退出码 0。

新增覆盖包括：

- Domain/schema：valid plan/result、伪造 source/issue/evidence、KEEP/DO_NOT_CHANGE 完整性、blocked 与 addressed 矛盾、A06 registry/Prompt 版本。
- Service/API/DB：完整 v1→v2→Review→STOP、PASS 禁止修改、错误 Review、Profile 必需且 exact approved、只写正文、append-only、hash/provenance 约束、repository 不 commit、transaction rollback。
- Freshness：两阶段、Provider 前/返回时，Draft/Plan/Profile/Lock/Decision 变化；未批准新 Plan/Profile 隔离。
- Runtime/concurrency：Provider 重试、重复投递、lease recovery、并发 trigger/version conflict、并发 result 只有一个 successor、低置信度/安全 BLOCKED、技术失败后源变化的显式重审出口。
- Frontend：CTA/PASS、缺失 Profile、进度/刷新/重复点击、exact Review/Draft 切换、Debug lineage、恢复动作。

既有迁移测试修正了升级到新 head 后的版本预期；历史 schema 校验使用当时实际存在的表/列，避免拿 0012 ORM 查询已 downgrade 的 0011 数据结构。未删除旧行为断言。

## 21. Migration / Docker Results

Migration：0011 → **0012**，新增三表和 workflow active request FK，增加关系/不可变触发器并最小扩展原 workflow guard；downgrade 恢复原 guard 并移除 010 对象，不删除此前 Draft/Review。

使用 PostgreSQL 测试服务 `55433` 的隔离 schema，最终验证结果：

| 检查 | 结果 |
| --- | --- |
| `alembic upgrade head` | PASS，0012_targeted_revision |
| `alembic downgrade -1` | PASS，回到 0011_quality_review |
| 再次 `alembic upgrade head` | PASS，回到 0012_targeted_revision |
| `alembic check` | PASS，No new upgrade operations detected |
| `docker build -t novel-os:novel010-acceptance backend` | PASS |
| 隔离 Docker API startup | PASS，Application startup complete |
| 容器内 `GET /api/v1/health` | HTTP 200，`{"status":"ok"}` |
| 容器内 `GET /api/v1/health/db` | HTTP 200，`{"status":"ok","database":"ok"}` |
| 容器内 `alembic current` | 0012_targeted_revision (head) |
| Mock worker `--once`（空测试队列） | exit 0 |

Docker QA 配置只有测试库与 mock-default，不读取真实 credential；未对现有开发库执行迁移，未重启现有真实 Provider worker。Colima 未提供可用的宿主机 QA 端口转发，因此 HTTP 健康检查在隔离 API 容器内执行；浏览器 E2E 另经 native 测试 API/Vite 完成，未把宿主机映射宣称为已验证。

本机原始日志：`/tmp/novel010-migration-final.log`、`/tmp/novel010-docker-build-final.log`、`/tmp/novel010-docker-health-final.log`。测试固定配置和临时运行产物未提交。

验证后已删除本次独立 QA 容器及其专用 schema；开发数据库、既有 worker 和前端进程保持原样。

## 22. Independent Review

按 code-review-and-quality 由独立只读子任务审查，审查者未参与文件编辑。审查覆盖权限、版本、lease/transaction、Context、Prompt、数据库 bypass、自动循环和 UI。

已处理的 Required：

1. 强化数据库 successor guard，验证 AGENT/A7/DRAFT、current/parent/supersedes/version、未批准未锁定及 hash。
2. 分离业务 BLOCKED 与技术重试，补显式重审出口，避免重复 immutable artifact 或输入变化后的恢复死路。
3. exact Review/Draft 版本标签，历史按当前选中 Draft 显示。
4. Revision history 批量 join，消除逐条 N+1。
5. 恢复测试正文原本只有一个短段落，Mock 证据等于整章被合法拒绝；修正为多段样本，保留 WAITING_HUMAN 与无后续任务断言，未弱化产品 evidence 规则。
6. 严格实施本 Ticket 的 approved WritingProfile 前置要求，修复原先沿用 009 optional-profile 的缺口，覆盖 Service/DB/Context/UI。

另修正 result 空 blocked_reasons 时遮蔽 plan 原因的显示问题。最终复核：Required 已闭环，未发现新的实现 Required；恢复测试 2 passed、缺失 Profile 的 Service/DB 测试 1 passed、前端 Revision 16 passed。完整工程门禁见第 20～21 节。

2026-09-28 Review 修复：已绑定 Profile 的审阅在 Profile 更新后变为 STALE，原 UI 隐藏了修改按钮，但仅为缺失 Profile 或阻塞中的 Revision 提供重审入口，导致正常等待人工操作的流程无法继续。现在当前正文的失效审阅（包括原 verdict 为 PASS）会显示显式重审入口，复用已有 API、版本绑定和执行权限校验；历史正文和执行中流程不显示该入口，失效审阅仍不能触发 Revision。重审请求的审计原因改为“人工请求重新审阅当前正文”，不再错误描述为修改阻塞。

本次新增 6 个组件回归用例，其中 3 个在修复前准确复现入口缺失。修复后前端 7 files / **95 tests PASS**（Revision 专项 22 tests），lint、build（含 `vue-tsc --noEmit`）及 `git diff --check` 均通过。本次仅调整前端和本地测试，未重复执行后端全量、迁移或真实 Provider 测试，未产生模型调用。

## 23. Known Limitations

- Mock 只验证工程控制面，不能证明文字变好、strength 真保留或局部事实无语义越界；真实 A05 与人工比较仍必须完成。
- Context Engine 只能提供当前已有的结构化依赖、approved 前章及知识 policy；完整 Character/Event/Canon Memory 尚未实现。
- Legacy profile-less Review 仍可阅读，但不能进入 Revision；必须批准 Profile 后重新审阅。
- 本次迁移/容器验收在隔离测试环境完成，现有开发运行实例尚未部署本分支与 0012。不能把构建通过误认为浏览器当前真实服务已更新。
- 测试留在本地，未提交；没有新增付费调用或自动运行 Case 04/05。

## 24. Deferred to NOVEL-011

自然语言 Revision instruction、用户反馈解析/归因、改变故事方向的反馈/Replanning 协调均未实现。

## 25. Deferred to NOVEL-012

Memory / Canon Commit、Character/Event Memory 持久化与授权写入未实现。新 Draft 即使 Review PASS 也不自动成为 Canon；不自动修改 Profile、Preference、Prompt 或进行学习。

## 26. Acceptance Result

**NOVEL-010 = CONDITIONAL PASS。**

| 验收层次 | 结果 | 依据 |
| --- | --- | --- |
| Engineering Acceptance | **PASS** | 后端 1201 passed、前端 89 passed、浏览器 E2E、迁移往返/check、Docker health、lint/build、独立 Required 全部闭环 |
| AI Behavior Acceptance | **NOT_RUN** | Case 04/05 真实 Provider 未获本次显式触发，未自动调用 |
| Human Prose Evaluation | **NOT_RUN** | 未把 Mock 输出视为文字改善；人工模板已准备 |

条件是完成用户 opt-in 的 Case 04/05 比较，验证核心问题改善、Strength 保留、无新增重大问题；不要求 Review v2 必须 PASS。Case 04 先补正式 Review，Case 05 先批准本项目 Profile 并重审。不存在已知未解决的工程 Blocking / Required；不能据工程通过声明“Draft v2 文学质量已改善”。

验收依据分组如下，语义项不以 schema 通过替代：

| Ticket 验收项 | 工程证据 | 人工/模型边界 |
| --- | --- | --- |
| 1～9 Domain / immutable version | PASS：Revision contract、完整 slice、DB/rollback tests | 不证明文字质量 |
| 10～16 Authority / 保留方向 | PASS（工程约束）：能力拒绝、锁/批准输入、KEEP/边界引用校验 | Major Direction/Strength 的 prose 保留需人工核对 |
| 17～21 Freshness | PASS：两阶段源变化与 approved/current 隔离 | 无 latest 替换 |
| 22～28 Runtime | PASS：registry、双阶段、retry、business block、lease/concurrency | Mock 不消费 API |
| 29～36 Workflow | PASS：显式启动、自动一次 A05、FAIL 后 STOP | 无自动 v3 |
| 37～44 Context | PASS：exact source/Review/strengths/Profile/Plan/locks、bounded selector | 未创造 Memory Domain |
| 45～54 Frontend | PASS：组件测试与真实浏览器 Mock E2E | 无复杂 diff/质量数值 |

未开始 NOVEL-011。真实 Case 04/05 需用户明确触发后才能完成产品文字效果验收。
