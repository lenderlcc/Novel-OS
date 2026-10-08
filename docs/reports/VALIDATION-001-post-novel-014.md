# VALIDATION-001 — Post-NOVEL-014 Engineering Acceptance

日期：2026-10-07。基线：`38de644b835ae06eed82b39a9959a11f5b0d6d9b`，分支 `wfg/checkpoint-001-phase2-integration`，加本次局部正确性修复。验收对象是当前本地工作区，尚未提交或发布；不是 fresh HEAD 的绿色测试声明。

**REAL PROVIDER CALLS = 0；Real AI Behavior = NOT RUN。** 仅使用隔离 `_test` 数据库、Mock / Recorded / deterministic fixtures。没有修改开发配置、迁移开发库、启动开发后台 Worker 或调用 Lingzhi。下述 PASS 仅表示工程行为。

## 1. Executive Summary

最终结果：PASS_WITH_BLOCKERS_RESOLVED。四项正确性问题已记录根因并修复：当前输出操作数组契约不一致、当前 Schema 被旧 Prompt 路由覆盖、Writer v2 被数据库 v1 校验拒绝、姓名子串误匹配导致不相关 Profile 进入 Context。没有新增业务功能、Agent、Workflow、Memory 层或检索框架。

全量后端：1,799 PASS / 4 opt-in SKIP / 0 FAIL / 0 ERROR；标准收集与最终完成集合均为 1,803 节点，无重复或遗漏。前端：177 tests / 13 files PASS，lint/typecheck/build PASS；修复后的浏览器串联 13/13 PASS。迁移和 Docker：PASS；0001～0021 upgrade / 0021→0020 downgrade / upgrade / check、两个 health 200。独立 Review：PASS_WITH_BLOCKERS_RESOLVED / APPROVE_ENGINEERING_BASELINE，19 项核对，无未解决产品正确性阻塞。

## 2. Validation Scope

覆盖附件 §1～63：001～014 实现审计、七 Agent / 八 Authority、013/014 Context、版本与 freshness、知识防火墙、关系过滤、输出契约、完整双 Revision 单章链路、既有五章 E2E、只读 export、前端、真实验收工具、迁移及 Docker。

没有启动 NOVEL-015/016/017，没有质量调优或真实写作/人物/创意评分。测试中的人工审批、finalization、Memory confirmation 都是显式 fixture 操作，不代替真实人工验收。完整 pytest 的既有独立进程恢复与 scoped CLI 测试共执行 4 次显式 Mock `--once` 子进程，均使用专属无 Key 的 `_test` 配置；浏览器 fixture 使用隔离库内注入 Mock 的执行线程。这些是明确的隔离测试，不是本机开发 Worker 或付费后台任务。

## 3. Repository Audit

实际代码、注册表、AST、迁移、API、前端和测试均参与审计，未仅依据 Ticket 判定。

产品各层为 IMPLEMENTED（基础 Ticket 使用后续模块共用的已存在层）；测试交付存在 IMPLEMENTATION_DRIFT：HEAD 后端 66 个 test/support 文件与初始本地 127 个不同，本地 frontend tests/e2e 未跟踪。此前用户要求“不提交测试代码”，本次保持这一约束。

独立 `git archive HEAD` 对三组已跟踪旧测试的实际结果为 **14 FAIL / 63 PASS**；同组修复前本地版本 **78 PASS**。失败涉及旧 Schema/CP/migration 断言。不能将当前本地完整绿色基线表述为 fresh clone 完整绿色。完整源码路径、共享实现说明、13 Task 和 source SHA 见 `backend/.runtime/validation001/capability-map001-014.json` / `repository-test-provenance.json`。

## 4. Capability Map 001~014

| Ticket | Capability | Domain | Service | API | Workflow | Agent Task | Prompt | Context Profile | Persistence | Frontend | Tests |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOVEL-001 | Backend bootstrap | I | I | I | I shared | I shared | I shared | I shared | I | I shared | I (local I / HEAD IMPLEMENTED) |
| NOVEL-002 | Core domain and persistence | I | I | I | I shared | I shared | I shared | I shared | I | I | I (local I / HEAD IMPLEMENTED) |
| NOVEL-003 | Chapter workflow | I | I | I | I | I shared | I shared | I shared | I | I | I (local I / HEAD IMPLEMENTED) |
| NOVEL-004 | Agent runtime | I | I | I | I shared | I shared | I shared | I shared | I | I shared | D (local I / HEAD DRIFT) |
| NOVEL-005 | Prompt runtime and Provider | I | I | I | I shared | I shared | I shared | I shared | I | I shared | D (local I / HEAD DRIFT) |
| NOVEL-006 | Context engine | I | I | I | I shared | I shared | I shared | I shared | I | I shared | D (local I / HEAD DRIFT) |
| NOVEL-007 | Requirement and Planning | I | I | I | I shared | I shared | I shared | I shared | I | I | D (local I / HEAD DRIFT) |
| NOVEL-008 | Writing and Writing Profile | I | I | I | I shared | I shared | I shared | I shared | I | I | D (local I / HEAD DRIFT) |
| NOVEL-009 | Quality Review | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |
| NOVEL-010 | Targeted Revision and Fidelity | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |
| NOVEL-011 | Human Feedback | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |
| NOVEL-012 | Memory Confirmation and Canon Commit | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |
| NOVEL-013 | Creative Exploration | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |
| NOVEL-014 | Character Depth and Voice | I | I | I | I shared | I shared | I shared | I shared | I | I | P (local I / HEAD MISSING) |

`I` = IMPLEMENTED；`shared` = 复用实际共用层；`D` = 当前本地测试已实现、HEAD 测试陈旧；`P` = 当前本地测试已实现、HEAD 交付部分缺失。该表是代码能力映射，动态正确性由下列测试验证。没有为了让每张 Ticket 有独立目录而新增平行实现。

## 5. Agent Audit

正式 Agent 恰为七个：A01 Orchestrator、A02 Requirement、A03 Planning、A04 Writing、A05 Review、A06 Revision、A07 Memory。Explore 属 A03；Character Profile Interpretation 和 Feedback Interpretation 属 A02；Fidelity 属 A05。没有 A08/CreativeAgent/CharacterAgent/FeedbackAgent。正式业务 Task 13 种，多 Task 不等于新增 Agent；独立 smoke/simulation 保持测试用途。

## 6. Authority Audit

恰为 A0 SYSTEM_RULE、A1 USER_LOCKED、A2 USER_APPROVED、A3 CANON、A4 APPROVED_PLAN、A5 USER_PREFERENCE、A6 DERIVED_MEMORY、A7 AI_INFERENCE。Formal tests 验证 A7 不覆盖 A1～A6，A6 不覆盖 Canon，Agent 无 approve/lock/commit/direct-write Canon 能力。

Profile 是 tendency 输入，不能产生 CharacterKnowledge、修改 Lock/Canon/State；Review 是 diagnosis、Feedback 是当前 Draft 意图、Candidate 是 A7 推断，不成为故事 Authority。当前 Task 的非法 envelope 在 Output Parser 失败；实际越权仍由现有 Authority Validator 拒绝。

## 7. NOVEL-013 Engineering Validation

Recorded fixture 实际执行 Brief → 多 Candidate → 合法 exact selected_candidate_id → 正式 ChapterPlan；合法/unsafe/blocked selection 均有回归。Candidate A7 与 Approved Plan 分离，人工审批仍绑定具体 ChapterPlan。Rejected sentinel 不进入 Plan/Writing/Memory。

候选 schema 可分别表达 core_event、conflict_engine、character_pressure、similarity_risk；repetition fixture 的近期 handoff/verification/procedure-like 信息进入 Explore Context。证明表达和传递能力，不证明模型产生更好的创意：Behavior PENDING。

## 8. NOVEL-014 Engineering Validation

Profile 版本生命周期、只读历史、source lineage、批准指针、相关人物筛选、关系投影、六类 Task 接入、同步 A02 解释的持久 Task/Run/Context/Prompt 链路均验证。历史无 Profile 的 Requirement → Plan → Write → Review → Revision → Memory 主链保持可运行。

Voice / 人物自然度 / OOC 判断是否准确均需要 014R；Recorded 输出不作为这些行为的 PASS。

## 9. Character Profile Versioning

DRAFT / APPROVED / SUPERSEDED、logical_id/version/supersedes/hash/authority 保留。批准 v1 后创建 v2 Draft：current 与 approved 分离，Agent 继续精确取 approved v1；批准 v2 后的新 Task 才读取 v2。完整单章还覆盖 approved v2/current Draft v3。历史 body 与 source hash 不原地改变。

## 10. Character / Knowledge Boundary

正反两个 POV 均测试：A KNOWS X 可取 X；B 不知道 X，B Context 不把 X 作为 B 知识，同时 B 自己 KNOWS Y 可取 Y。敏锐/主动调查的 Profile 不增加知识授权，避免“两者均未取到”被误判通过。

Explore/Plan 可读取带 owner/epistemic 标签的相关 continuity；Writer 用 exact bound POV 的 KNOWS fact links。Global Canon 可供规划并不表示所有角色知情。未来 scope、superseded state、未批准 Profile、其他 POV Knowledge 都受现有策略限制。

## 11. Relationship Modifier

A+B 场景只投影 AB；A+C 场景只投影 AC。五人物压力测试不会 dump 所有 modifier，存储的完整 Profile 保持不变。这里只验证 Context 输入确实不同，不声称真实对白已产生不同声线。

## 12. Creative Exploration Integration

Explore Task 是 C04 内现有 A03 分支，不新建 Workflow/state/approval channel。Selected Concept 作为 Context 的 A7 推断进入 Planner；未选候选保留诊断证据，普通 UI 不展示，Debug 可查。Writer/Revision/Memory 不接收候选正文或 rejected facts。

## 13. Planning Integration

按相关性接入 CreativeBrief、selected concept、approved CharacterProfile、角色 State/owner-labeled Knowledge、参与者 pair modifiers、approved WritingProfile。Draft/Profile/candidate 不自动形成 hard constraint；Review revision target 与用户 Authority 分离。

C04 修复现有人物名称/alias 的单词内部误匹配，并保留 NFKC 和 normalized 多词别名兼容，保留 project、before_sequence、explicit IDs、limit 等边界。检索仍为精确 ID/关系/版本/状态加现有字面名称 fallback，没有 Vector RAG。

## 14. Writing Integration

exact Approved Plan、approved WritingProfile、相关 approved BehaviorProfile/pair modifier、相关当前 State、POV Knowledge 均有精确 source 元数据验证；新 Draft Plan/Profile 不污染批准输入。排除 rejected candidates、无关 Profile、future-only 信息、superseded State 和全量历史正文。

当前 Writer v2 的 operations arrays 与 Schema/Prompt/Service 一致；新数据库 guard 精确匹配 Task 输出版本。Body 内容、Writer 质量策略和既有 deterministic writing check 没有调优。

## 15. Review Integration

A05 读取存在的 approved Profile，不能修改 Profile；不存在 Profile 时不能凭空形成 OOC hard authority。Review source ChapterVersion、Plan、Context、Run、Prompt 和 ModelProfile 精确绑定。Narrative issue 不获 P0/故事裁决能力；模型是否正确诊断仍 PENDING。

## 16. Revision Integration

WEAK_CHARACTER_VOICE Recorded diagnosis 对应局部 Revision，保留 Source Draft、Approved Plan、Preserve Constraints、相关 Profile。A06 只改 prose/local elaboration，操作数组空，超出范围使用 unresolved/blocked。

完整单章实际得到 v1 → review-driven v2 → feedback-directed v3，两次独立 Fidelity PASS 才生成正式下一 Draft。旧版本及首尾保留约束不变；下一 Review 的 chapter_version_id 绑定新版本，不重新审旧 Draft。

## 17. Human Feedback Integration

人物相关反馈 Context 包含 exact approved Profile，输出绑定当前 Draft 的 Targeted Revision Intent。反馈“不像他、其他地方不要动”进入局部 preserve/target boundary；不能自动学习 CharacterProfile/WritingProfile 或持久 Preference。语义路由覆盖 Revision、replan、profile-change、澄清和 no-change；这些是 Recorded 工程路由验证。

## 18. Memory Boundary

Final accepted Draft → A07 extraction proposal → 人工显式选择（或显式空确认）→ 单事务 Commit。Draft/Plan/Candidate 不等于 Canon，Proposal 不等于 CommittedMemory。

Rejected Candidate、未接受 Draft、一次性情绪行为、BehaviorProfile 不成为新事实来源或 Profile 学习通道。Full slice 的 committed evidence 绑定 accepted v3；五章测试另验证七种事实/状态/知识/信念/关系/线索/摘要样本与状态转换。

## 19. Context Contract Matrix

正式矩阵：[14-Validation-Context-Contract-Matrix.md](../specs/14-Validation-Context-Contract-Matrix.md)。包含 EXPLORE、PLAN、WRITE、PLAN_REVIEW、QUALITY_REVIEW、REVISION、FEEDBACK_INTERPRET、MEMORY_EXTRACT 的 Must Include / Conditional / Must Exclude。

每个 Profile 来源验证 source_type、record/source ID、logical_id、version、authority、selected_reason；不以“非空”作为通过依据。正文角色知识与规划的 owner-labeled global 信息分别说明，未来项的 REQUIRED_ONLY/NONE 等现有政策也不混写成一刀切。

## 20. Context Overload / Token Audit

五人物、多 Profile/current Draft、多个 modifier、Memory、三个 Concept 的实际 Writer Context：仅两个相关 approved Profiles、一组 AB、三个 POV 相关 Memory items，零 Candidate、零历史 prose。AB/AC 和两个 POV 都有正反断言。

| Task | Items | Existing estimator |
| --- | ---: | ---: |
| EXPLORE | 8 | 11044 |
| PLAN | 9 | 13374 |
| WRITE | 7 | 11201 |
| QUALITY_REVIEW (before / after revision) | 9 / 9 | 14510 / 14699 |
| REVISION_PLAN | 11 | 27009 |
| REVISE | 12 | 30106 |
| Five-character WRITE, A POV | 11 | 16560 |
| Five-character WRITE, B POV | 11 | 16557 |

使用现有保守 UTF-8 estimator，重算与 sealed package estimated_tokens 相等；不是 Provider billing tokens，不设任意评分阈值。Revision 较大是已有 source Draft、indexed evidence、preservation/fidelity contract 的结果，没有 all-project dump。

名称 fallback 继续使用既有 normalized identity。当前 Latin/alnum 范围内，空格/标点等价形式（如 Red Fox / redfox、AB / A B / a_b）可在完整词边界匹配，不能跨结构化文本行拼接；accented、decomposed、fullwidth 与数字名字都有实际 DB 正反回归。CJK、explicit IDs、project/temporal scope 保留。normalized alias 不保存原拼写，完全相同的词/name（如 article `a` 与人物 A）及规范化后同名不做语义消歧；明确身份时复用 existing explicit ID。该范围不是全部 Unicode 或自然语言身份解析已正确的声明。

## 21. Prompt Contract Audit

| Task | Output schema | Compiled Task Template |
| --- | --- | --- |
| PARSE_CHAPTER_REQUIREMENT | chapter-requirement-result.v2 | parse-chapter-requirement v4 |
| EXPLORE_CHAPTER_CONCEPTS | creative-exploration-result.v1 | explore-chapter-concepts v2 |
| PLAN_CHAPTER | chapter-planning-result.v3 | plan-chapter v10 |
| REVIEW_CHAPTER_PLAN | chapter-plan-review-result.v3 | review-chapter-plan v6 |
| WRITE_CHAPTER | chapter-writing-result.v2 | write-chapter v6 |
| REVIEW_CHAPTER_COMPLIANCE | chapter-compliance-review.v2 | review-chapter-compliance v3 |
| REVIEW_CHAPTER_NARRATIVE | chapter-narrative-review.v3 | review-chapter-narrative v4 |
| PLAN_CHAPTER_REVISION | chapter-revision-plan.v4 | plan-chapter-revision v7 |
| REVISE_CHAPTER | chapter-revision-result.v3 | revise-chapter v8 |
| VALIDATE_REVISION_FIDELITY | revision-fidelity-result.v3 | validate-revision-fidelity v5 |
| INTERPRET_CHAPTER_FEEDBACK | chapter-feedback-result.v1 | interpret-chapter-feedback v3 |
| EXTRACT_CHAPTER_MEMORY | chapter-memory-result.v2 | extract-chapter-memory v3 |
| INTERPRET_CHARACTER_PROFILE | character-profile-draft.v1 | interpret-character-profile v1 |

当前 13 Task 的 AgentRegistry expected schema、生成 Pydantic OutputContract、Service parser model 和实际 compiled Task Prompt 核对一致。文档里的 interpret-requirement / review-plan / review-chapter-quality 对应实际 PARSE_CHAPTER_REQUIREMENT / REVIEW_CHAPTER_PLAN / REVIEW_CHAPTER_NARRATIVE；没有隐藏新增 Task。

六个新 envelope 仅关闭原 Runtime 已禁止的 arrays；Planning 合法 task-scoped proposed_changes / proposed_major_changes 保留。新增六个 Task Prompt 版本只追加操作契约规则，旧 body 逐字保留；无创意/写作质量调优。非法非空数组以 SCHEMA_PARSE_ERROR 在 Parser 拒绝，真正的越权仍 AUTHORITY_DENIED。

## 22. Prompt Lineage

完整单章含 12 类 Chapter Task，加独立 A02 Profile Interpretation 共 13 类；全部成功 Run 有 exact module version/pin/hash、PromptLineage、compiled hash、ContextPackage ID/hash、ModelProfile/hash、AgentTask/AgentRun。故事、人物、Memory、Concept 来自 ContextPackage，不写死到 Prompt Library。新 Task 的证据链不缺省。

Export 执行 91 次 GET。前后 39 表 row counts、全行 hash、current pointers、workflow state/version、audit、调用者 state 字典均相同。不是只比较业务表数量。证据见 `runtime-full-slice.json`、`runtime-export-immutability.json` 和最终 evidence manifest。

## 23. Freshness

覆盖 Explore、Plan、Writing、Revision 的 queued/inflight v1→v2批准变化；新增未批准 Draft 不触发批准输入变更。现有 source_versions / approved binding 机制在执行前与结果应用时检查。

现有 Task enum **没有 STALE**：旧 pending task 执行前被 CONTEXT_STALE 阻断，Context freshness=STALE，Task 终态 FAILED、workflow C90_BLOCKED；未调用模型、未持久化结果，原 snapshot 保留。没有新增状态，也不虚称批准 API 立即写 TaskStatus.STALE。

## 24. Historical Compatibility

原六个 Schema hash、所有旧 Task 输出定义/Prompt 模块和 CP 路由保留。v1/v2/v3 Workflow 定义及 hash 不覆盖，v4继续现有 Explore 内部分支。Writer saved-v1/current-v2 都经真实服务保存 lineage；空 Profile 历史项目、populated Memory、旧 approval/current 指针均回归。

更新本地测试只涉及 current model/schema/prompt 绑定、migration head、非法输出提早 Schema 拒绝的 error code，或显式指定原历史 schema；没有修改 E2E semantic Expected / recorded prose。新增测试的错误 fixture、运行中 source 变化引起的旧 head 断言、被停止的中间 run 都不计入最终 PASS。

## 25. Full Single-Chapter Slice

Recorded 实际流程：A02 Profile interpretation evidence；Requirement → Creative Exploration → Planning → Plan Review → 显式人工 Plan Approval fixture → Draft v1 → Quality Review → Revision Plan / A06 → Fidelity → Draft v2 / Review v2 → 人工当前-Draft Feedback → Directed Revision / Fidelity → Draft v3 / Review → Finalization → Memory Extraction → explicit human confirmation → Commit → next-chapter Planning Context。

检查三份不可变 Draft、两次 Fidelity、exact accepted-v3 Memory provenance、下一章获取 committed entry、approved/current Profile 分离及 rejected sentinel 排除。该串联确实包含两轮 Revision，不用“一轮主链测试”代替附件要求。

## 26. E2E-001 Regression

原 Chapter 01～05 Recorded fixture 和 expected-context / expected-memory / scenario 文件未变。Knowledge Firewall、State Transition、Belief vs Truth、Open Thread、Revision Pollution、Context Retrieval、Memory Commit 全通过。实际 trace `runtime-five-chapter-trace.json`。

C01～C04 第一版源上的 focused 48 tests PASS / 231 deselected（126.32 秒），同时包含上述双 Revision 和历史/013/014 切片；最终 C04 补齐后，完整全量再次执行这些测试，runtime manifest 以最后一次结果封存。deselected 是 focused 选择，不能冒充全量。

## 27. Frontend Smoke

修复后 Playwright：13/13 checks PASS，1 串联测试、0 retry，19 Mock calls、0 paid/forbidden/external calls、0 JS errors。验证 Project/Chapter/WritingProfile/Character/Profile view、approved v1/current Draft v2、普通 UI 不暴露 Candidate、Debug 候选和 exact Profile Used、Revision v1/v2 selector、Human Feedback v3、Memory explicit confirmation。

9 张截图保存，最终版本的 Profile/Debug/Revision/Memory 四张已视觉复核，trace 保存；隔离 8011/5174 已关闭，开发 8000/5173 未修改。浏览器 Mock 的 empty Memory confirmation 只验证 UI gate，非空提交由后端 Recorded slice 验证，不混称真实 AI 提取正确。四项 frontend gates：177 tests / 13 files、lint、typecheck、build 全 PASS。

## 28. Acceptance Readiness

E2E-001R、013R、014R 复用已有 `evals/e2e/multi-chapter/run.py`、manifest、cases、manual templates、report/export。真实调用默认 OFF，必须双显式 flag / paid-call gate；prepare/status/export 不消费模型，人工 gate 不被 runner 代签。已有 pytest live tests 缺显式 opt-in 默认 skip。

Readiness focused 59 PASS：36 pure Mock / 23 isolated API；D7 实际 Worker DB task set 与审计 API set 匹配并使用 task_ids claim，D8 approved WritingProfile pin 每次付费步骤前复核。四种 opt-in flag 组合仅 true/true越过 flags gate，验证过程中仍零 dispatch。

013R 的 Case03/repetition fixture、六项人工问题具备；缺合法历史时 fail closed，不伪造历史 Canon。014R 的不同人物/关系/OOC/知识/盲评 case 具备。既有盲评模板补齐隐名 Sample A/B、Clearly Different/Somewhat Different/Interchangeable、Notes，未新增自动 Voice Score。

## 29. Contract Freeze Status

| Contract | Status | Evidence |
| --- | --- | --- |
| Authority A0～A7 | FROZEN | 191 Context/Authority focused + formal negative invariants |
| Seven Agent roster | FROZEN | 13 Task owners / Agent count==7 |
| Chapter Workflow / Core Versions | FROZEN | 历史 definition hash、current/approved、两轮 Revision、原五章 E2E |
| Memory Layers / Commit Pipeline | FROZEN | 六层隔离、accepted-v3证据、人工确认、单事务Commit与回滚 |
| Character Knowledge Firewall | FROZEN | A KNOWS X正向、B反向排除、两个POV及未来scope |
| CreativeExploration Core Schema | FROZEN | 多candidate/selected/A7/未选隔离、旧Schema/hash/pins |
| CharacterBehaviorProfile Core Schema | FROZEN | immutable version/source/hash、approved/current、modifier scope、optional |
| Revision Contract | FROZEN | exact Draft/Review、局部保留、两次Fidelity、Draft-v2/v3与新Review |
| HumanFeedback Contract | FROZEN | 当前Draft解释/定向修订、Profile/Preference不自动学习 |
| Prompt / Context / Freshness | FROZEN | 13实际编译Task契约、Context来源、pre-IO/result freshness |
| Acceptance | FROZEN | 默认OFF、显式paid-call gate、只读export、独立人工Gate |

正式状态同步至 [13-Phase2-Contract-Freeze.md](../specs/13-Phase2-Contract-Freeze.md)。FROZEN 表示本次当前工作区的工程边界通过；正确性证据或明确架构决定仍允许最小修改。它不表示真实 AI/人工质量已通过，也不表示远端版本已更新。

## 30. Bugs Found

| ID | Failure / Root Cause | Affected Contract | Minimal Fix / Regression |
| --- | --- | --- | --- |
| C01 | 六类当前 typed结果继承 generic max20 operations；Runtime 禁止 memory，Writer/Review也禁止 changes | Schema / Prompt / Service | 新 versioned closed envelopes、六个 additive Task Prompt；13当前契约、非法 raw envelope、合法 Planning proposal、旧 hash/pins |
| C02 | PromptRuntime 根据 CP 选择旧 template，覆盖 current Schema 对应的新 Prompt | 当前实际编译与历史路由 | 当前 closed contract 固定实际新 template，historical schema保留原CP路由；13 compiled pins回归 |
| C03 | C01 新 Writer v2 被 frozen DB function 的 v1-only条件拒绝 | Task / PromptLineage / WritingGeneration | additive 0021只更新 guard，支持1/2且exact Task schema；v1/v2实际写入、row/function roundtrip |
| C04 | normalized substring匹配 E→meets/leaves、Mira→miracle，以及 accented Latin 词内匹配，无关Profile进入Context；第一版token修复另漏取normalized多词alias | relevant-only Profile / Modifier | 复用现有 SQL，Latin完整边界/NFKC、既有normalized空格/标点等价形式、CJK/explicit ID保留；实际DB正反tests、overload/全量 |

C04 后续 actual DB before 补查另得到 10 个 accented/decomposed/fullwidth 失败和 2 个多词 alias 失败；针对同一边界补齐，不新增检索层。新 local fixture 曾假设 AB 与 A B 不等价，已依据既有 normalized identity 契约纠正并记录；不是更改原 E2E Expected。

四项均在修改前记录 Failure / Root Cause / Affected Contract / Minimal Fix / Regression。C03 是 versioned修复集成时发现的兼容阻塞，不伪称初始旧 Writer 已不能写入。

## 31. Bugs Fixed

C01～C04 已闭环；无新 Agent/Workflow/Table/Column/Memory layer。0021只替换既有函数，不修改历史 migration。无 Writer/Quality tuning、无权限放宽、无 Vector/Graph/Redis/Kafka/Microservice。

非产品工程问题也明确记录：盲评表单缺具体 Sample/choices 已补；初次 Docker role-build比较 manifest ID相等的断言错误（BuildKit attestation可改变manifest）改为比较实际 RootFS/runtime config；节点审计脚本对参数中 `::jsonb` 的误拆分改为仅拆分参数前的节点路径。后者只修忽略目录内 QA helper，不改产品或测试用例。被终止的运行和错误测试 fixture 均保留/说明，未把它们算为成功。

## 32. Regression Results

| Gate | Final Result | Evidence |
| --- | --- | --- |
| Full backend pytest | 1,799 PASS / 4 opt-in SKIP / 0 FAIL / 0 ERROR；1,803 节点，无重复/遗漏 | `backend-final-results.json`、`node-coverage.json`、六份 JUnit / exit guard |
| Shard 0 / 1 / 2 / 3 | 480 PASS + 1 SKIP / 431 PASS / 454 PASS + 2 SKIP / 396 PASS + 1 SKIP | `pytest-shard-{0,1,2,3}.xml` |
| Acceptance runner pure / API | 31 PASS / 7 PASS | `pytest-runner-pure.xml`、`pytest-runner-api.xml` |
| Context / Authority focused | 191 PASS / 0 FAIL / 0 ERROR；C04 targeted actual DB 18 PASS | `context-final-focused.xml`、`context-scope-result.json` |
| Schema / Prompt focused | 194 PASS；current typed contracts 40 PASS | `runtime-schema-focused-after.log`、`runtime-contract-after.log`；对应最终全量再次执行 |
| Recorded slice / E2E focused | 48 PASS / 231 deselected；双 Revision 与原五章 | `runtime-final-slices-after-c04.log`；最终全量再次执行，final JSON/hash 封存 |
| Readiness focused | 59 PASS：36 pure Mock / 23 isolated API | `acceptance-repository.md`；最终全量包含 runner / gate tests |
| Migration focused | 38 PASS；Writer v1/v2 populated roundtrip 2 PASS | `pytest-focused-migration.xml`、`pytest-focused-writing-migration.xml`；最终全量再次执行 |
| Frontend | 177 PASS / 13 files；lint / typecheck / build PASS | `frontend-gates.json` |
| Browser smoke | 13/13 PASS；19 Mock / 0 real / 0 JS errors | `frontend-smoke.json`、9 screenshots、trace |
| Ruff / diff | `ruff check` / `ruff format --check` / `git diff --check` PASS | `ruff-check.log`、`ruff-format.log`、`diff-check.log` |
| Docker / health / migration | backend & worker builds PASS；health / health-db 200；upgrade / downgrade / upgrade / check PASS | `docker-evidence.json`、build / migration logs |

各 focused 组与全量重叠，不相加。四项 skip 均为显式 `--live-model` 才允许执行的真实 Provider/Requirement/Planning/Writing 测试；不是工程失败被跳过。

最终源 snapshot SHA-256：`3ba2d55893e3982370401c5d75e476ef6e71cb7820b6a947352c8b945872e33b`，包含 688 个产品/测试/前端/fixture 文件；不含真实配置。

全量采用 pytest 标准 `tests/` 收集，按文件 SHA 四分片，再分别执行两个 acceptance-runner 模块；最终检查 disjoint selected node union 与标准收集完全相同、每个 node在最终结果集合中恰出现一次。未删测试、未用 focused deselection 冒充全量。网络 guard 对 actual HTTPTransport/AsyncHTTPTransport/socket拒绝外部访问，MockTransport单元测试保持可用；专属恢复 CLI 仅允许无Key `_test` / mock-default / --once。

冻结产品后的第一轮全量有 8 个旧断言失败：7 个 Writer 非法 proposed_changes 已在 Schema 阶段拒绝（旧断言仍预期 AUTHORITY_DENIED）；1 个 current Requirement Task Prompt 已升级到 v4（旧断言仍固定 v3）。仅更新两个本地测试的契约断言，正文不可写入断言和所有 E2E Expected 保持不变。原始 JUnit 保存为 `pytest-shard-2/3-before-assertion-alignment.xml`。随后补查同一 C04 的 accented Latin 与 normalized 多词别名，旧分片存档为 pre-accent；最终全部四个完整分片以最终源码重跑。最终统计选择每节点最后一次完整分片结果，不把多个尝试相加。

HEAD旧测试14 FAIL仅作为交付漂移证据，不是当前结果；focused组有重叠，不能相加当总数。中间75PASS/12FAIL、旧head单FAIL、fixture失败/被停止run不作为最终基线。Warnings 为既有 Starlette/httpx/AnyIO deprecation，不因本轮引入。

## 33. Migration

当前 head：`0021_writing_output_contract`。隔离 Docker/test schema 运行 upgrade head → downgrade -1（0020）→ upgrade head → alembic check：PASS。新 migration 无 table/column变化，Writer guard历史 Workflow 2/3/4保留，schema1/2 与 Task exact一致。

额外迁移/历史约束 focused 38 PASS（114.861 秒）；saved Writer v1/current v2实际写入及0021 populated函数/行 roundtrip 2 PASS。两组与全量存在重叠，不相加计数。

已提交真实历史 Memory 的测试比较所有已有列/行，0020/0021兼容；0019 identity created_at/by backfill保留真实 batch provenance；独立 report / state transition有历史时 downgrade export guard仍有效。开发库未迁移。

## 34. Docker

两次实际 role build 均 exit 0：backend image `sha256:56d68ff186048b2b2c1e8ace341f304ebcd1b955b490c079bdb19585c2cb9550`；worker image `sha256:21d927a052a273cf190cc6af87acf79010fd5ae5758f9c9aa96c6ee997344378`。RootFS和 runtime config相同；manifest因attestation不同可以不同。Source snapshot一致，worker `--help` exit0；health与health/db均200；迁移roundtrip/check PASS，隔离schema/容器/private TOML清理通过。证据 `docker-evidence.json` / build与migration logs。

backend/worker role使用原 Dockerfile构建，不增加镜像架构。Worker只运行离线 `--help` 检查，未启动 Docker Worker执行任务；pytest 中 4 次显式 Mock CLI 见§2。私有TOML无provider key；容器非root user novel、无published ports、test schema、容器/Schema/TOML均清理。health与health/db通过容器内请求，未为host forwarding改变产品。

## 35. Independent Review

独立 Reviewer `/root/validation_independent_review` 未参与 C01～C04 修复；收到全部最终验证完成后的 READY 才开始 Review。结论为 **PASS_WITH_BLOCKERS_RESOLVED / APPROVE_ENGINEERING_BASELINE**，未解决产品 correctness blocker = 0。Review 完成于 2026-10-07 09:44:48 UTC。

独立重算 688 文件源码快照、六份最终 JUnit 的 1,803 节点集合、20 个历史 migration 与 10 个 E2E fixture hash；修复前后、Review 前后均无最终源码 drift。另实际进行纯编译检查：13 个当前 Task、12 个历史 Schema/Prompt hash、10 条历史 CP 路由全部 PASS，不构造 Provider、不发请求。没有重复执行整套 pytest / browser / Docker；这些结论依据实际最终原始记录及源码逐项核对。

保留 FYI IR-FYI-01：HEAD 的测试交付漂移和当前工作区绿色结果不能混同；没有擅自提交测试。字面 identity fallback 的同名消歧限制、Mock 浏览器空 Memory proposal 等范围限制明确记录。

[独立 Review](../../backend/.runtime/validation001/independent-review.md) / `independent-review.json` / `independent-pure-contract.json`。Review Markdown SHA-256：`faab5ab3ace088cabc69b446bdfdabbc386bc0a915025676336d336603b16332`；JSON SHA-256：`1b80e13dd63fc365f42a620c5655f0fd4a4693e2c7560a6ebeaf6b2e21d1aa6a`。

覆盖附件19项：roster/Authority、013/014、版本/Draft leak、知识/关系/candidateMemory、overload/Prompt污染、Contract/freshness、历史兼容、Fidelity/Feedback/Memory、acceptance工具、零真实Provider、未提前015。检查结论基于实际代码与最新证据，独立于修复作者；未只复述前次报告。

## 36. Pending Real Acceptance

E2E-001R / NOVEL-013R / NOVEL-014R = **PENDING**。Real AI Behavior = **NOT RUN**；Human Prose / creativity / character voice evaluation = **NOT RUN**。没有从 Recorded成功推导创意更好、对白更自然或长章连续性质量已通过。

NOVEL-015 Long-range Planning、NOVEL-016 Retrieval Improvement、NOVEL-017 Arc / Story Management 均 **DEFERRED_PENDING_REAL_ACCEPTANCE**，未实现、未排序。

## 37. Final Result

**VALIDATION-001 = PASS_WITH_BLOCKERS_RESOLVED。** Novel OS 001～014 Engineering Integration 在当前本地工作区已形成稳定 Baseline。该结论仅限工程契约、持久化与 deterministic / Recorded 集成。

当前产品未解决阻塞：无（本次当前工作区工程范围）。交付限制：完整测试按用户要求保持本地，fresh HEAD不能完整复现本地绿色基线；报告不隐瞒此 IMPLEMENTATION_DRIFT。新增结果未提交/推送/合并/部署。

可复核证据位于 `backend/.runtime/validation001/`：最终源码 snapshot、全量 node-coverage、JUnits/logs、只读 export、Context source triples、截图/trace、migration/Docker、独立Review与 final evidence manifest。原五章 expected/prose 未改变。

完成后停止；不开始 NOVEL-015/016/017，不启动真实验收。
