# CHECKPOINT-001 — Phase 2 Integration & Acceptance Readiness

日期：2026-10-07。工作区：`wfg/checkpoint-001-phase2-integration`。初始 latest local main `1cb275d2439af3e9c5e2982002ca9c1d4fc9e107`；`origin/main` 为 `8199173d9accf5b5154481c92faa3c900f6907ec`，本地包含其全部提交并领先6个提交。此前012修复、013/014与测试/evals均在未提交工作区中，本轮完整保留。本报告区别 checkpoint 改动与已有工作，不声称远端已发布。

## 1. Executive Summary

**PASS_WITH_BLOCKERS_RESOLVED（Engineering）**。本轮仅做001～014集成、明确契约缺口修复、验收准备和冻结。已完成实际仓库审计；Required Fix 是014人物描述解释缺持久 AgentRun / PromptLineage / ContextPackage。复用既有运行链补齐，未增加创作能力。

Engineering Acceptance、Real Provider Acceptance、Human Prose/Character/Creative Evaluation 是三种不同结论。本轮 paid calls=0，真实模型和人工行为验收仍 PENDING。

后续整体 Review 发现并修复两个验收工具问题，见37。31～34保留初次 checkpoint 的完整验证记录；其中全量测试与Docker源码指纹属于本次修复前基线，本次补丁的验证结果单独列出，不沿用旧源码指纹证明新代码。

## 2. Phase Status

001～012 ENGINEERING COMPLETE，E2E-001 历史工程 PASS_WITH_BLOCKERS_RESOLVED；013、014 ENGINEERING COMPLETE。E2E-001R、013R、014R REAL ACCEPTANCE PENDING。工程最终回归见31～34；[PROJECT-STATUS](../PROJECT-STATUS.md) 是持续状态入口。

## 3. Repository Audit

编码前完整读ticket1929行，并在实际代码检查Domain/ORM/Repository/Service/API/Task/Prompt/Context/Workflow/Frontend/tests，不把旧报告当实现证据。初始head=0019；本轮新增0020。当前目录 `/Users/agiuser/Documents/ChatGPT/Novel-os` 是空的不同仓库，实际工程位于 `/Users/agiuser/novel-os/Novel-OS`。

只读审计工件（本机 ignored）：`.runtime/checkpoint001/{persistence-workflow-audit,context-prompt-audit,acceptance-ui-audit}.md`，baseline883文件哈希与`before.patch`保存原工作区。审计发现 D1–D5，见28；未发现新的Authority/Knowledge/Candidate/Memory污染实证。

## 4. 001~014 Capability Map

| Ticket | 实际Domain / Persistence | Service / API / Task / Workflow | Frontend / Tests |
| --- | --- | --- | --- |
| 001 | core/config、db/session；0001 | create_app、health/db、JSON logging/requestID/error middleware | frontend连接错误；health/config/request/database tests |
| 002 | domain/models/repositories/core；0002 | core_base / versioning / locks / core routes；用户事务 | Project/Chapter/versions；negative/rollback/concurrency |
| 003 | domain/models/workflow；0003/4 | versioned YAML、WorkflowRuntime、events/gates/recovery | WorkflowProgress/HumanGate；paths/guards/races |
| 004 | domain/models/agents；0005 | AgentQueue/AgentResultHandler、standard Worker、lease fenced；agent routes | Debug Task/Run；authority/lease/recovery |
| 005 | PromptLineage；0006 | registry/compiler/PydanticOutput/Provider、PromptLineageService | Debug exact modules/hash/model；prompt/provider tests |
| 006 | ContextPackage；0007 | ContextService/MemoryQuery/ContextFilter、read-only Inspector | Debug source/inclusion/exclusion；context/version tests |
| 007 | CreativeBrief/PlanGeneration/PlanReview；0008 | A02 Requirement → A03 Plan → A05 PlanReview → C06 human | brief/plan/gate；verticalslice/semantics/coverage |
| 008 | WritingGeneration；0009；ProjectWritingProfile0010 | A04 Writer，C07→C08→C09，exactapprovedPlan | Draft/history/Profile；writing verticalslice/current-approved |
| 009/9A | Quality bindings/pass/report；0011 | A05 compliance+narrative，C09→C10/C11；quality routes | QualityReview/Debug；dialogue/evidence/recovery |
| 010/A/B | revision request/plan/candidate/result；0012/13 | A06 plan+execute → A05 Fidelity → successor Draft → Review | Revision Workspace；locality/fidelity/contract/rereview |
| 011 | HumanFeedback/interpretation；0014/15 | A02 feedback→existing Revision or clarification/replan/profile gate | HumanFeedback；scope/correction/rollback |
| 012 | MemoryRequest/Proposal/Batch/Subject/Entry；0016/17 | human finalization→A07→human candidate confirmation→commit C16 | MemoryCompletion/Debug；fivechapter/isolation/atomiccommit |
| 013 | CreativeExploration、selected pair on PlanGeneration；0018 | A03 Explore→Plan，v4 C04内部阶段，原Plan approval | Workspace正常Plan；Debug候选；selection/authority/pollution tests |
| 014 | immutable CharacterBehaviorProfile、manual identity provenance；0019 | ProfileService/current/approved/versions，A02 interpretation，task-aware Context | CharacterProfile/Debug；sparse/version/pair/freshness/POV tests |

上述路径相对 `backend/novel_os/`，每项均有实际router注册、repository与tests；不新增替代路径。014解释持久化缺口由0020与原执行service修复，见20。

## 5. End-to-End Integration Map

UserRequirement → A02 CreativeBrief → A03 Explore（仅v4且政策允许）→ exact selected concept → A03 ChapterPlan → A05 PlanReview → **human Plan Approval** → A04 Draft → A05 QualityReview → **human Review/Revision decision** → A06 plan/candidate → A05 Fidelity → Draft v2 → A05 Review v2 → **human feedback** → A02 interpretation → 同一DirectedRevision → **human finalization** → A07 proposal → **human selected Memory confirmation** → atomic commit → next Chapter Context。

三类A旧项目/B013/C013+014使用同一RecordedProvider主链回归；人工动作在测试中显式逐步提交。测试不评价创意或文学效果，不自动批准真实项目。

## 6. Agent Responsibility Audit

AgentId与Registry均7个。Explore复用A03；Profile/Feedback解释复用A02；独立Fidelity复用A05。批准、锁、Workflow状态写入与Canon提交由Service应用用例控制，Agent没有这些capabilities。Runtime独立于Repository/SQLAlchemy/FastAPI。

## 7. Authority Audit

A0～A7仍八层，未漂移。探索/Review/Revision/Feedback诊断是A7，不升级用户hard constraint；ApprovedPlan A4、偏好A5、批准Profile A3保留其既有语义，behavior tendency不是事实/知识许可。Lock/State/Knowledge/Plan胜过倾向。模型不可提交approved/status/version/system actor等服务器字段。

## 8. Context Contract Matrix

由当前Registry实际生成。Required是该profile声明；optional也需authority/status/version/scope和fingerprint，空集同样参与freshness。

| Task | Context | Required selectors | Optional selectors |
| --- | --- | --- | --- |
| PARSE_CHAPTER_REQUIREMENT | CP-003A.v1 | task-input, target-chapter | effective-requirements, effective-decisions, project-metadata |
| EXPLORE_CHAPTER_CONCEPTS | CP-004E.v2 | task-input, target-chapter, planning-brief-with-policy | effective-requirements, effective-decisions, project-metadata, dependency-chapter_plan, dependency-requirement, dependency-decision, approved-project-writing-profile, committed-memory, memory-subjects, recent-approved-plans, recent-final-summaries, approved-character-behavior-profiles |
| PLAN_CHAPTER | CP-004.v8 | task-input, target-chapter, planning-brief-with-policy | effective-requirements, effective-decisions, previous-approved-chapter, project-metadata, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, previous-iteration-plan, review-revision-targets, approved-project-writing-profile, committed-memory, memory-subjects, approved-character-behavior-profiles |
| PLAN_CHAPTER | CP-004.v9 | task-input, target-chapter, planning-brief-with-policy | effective-requirements, effective-decisions, project-metadata, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, previous-iteration-plan, review-revision-targets, approved-project-writing-profile, committed-memory, memory-subjects, selected-creative-concept, recent-approved-plans, recent-final-summaries, approved-character-behavior-profiles |
| REVIEW_CHAPTER_PLAN | CP-004R.v4 | task-input, target-chapter, planning-brief-with-policy, target-plan | effective-requirements, effective-decisions, project-metadata, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, approved-project-writing-profile, approved-character-behavior-profiles, memory-subjects |
| WRITE_CHAPTER | CP-005.v7 | task-input, target-chapter, approved-plan | effective-requirements, locked-decisions, supporting-requirements, effective-decisions, dependency-chapter_plan, dependency-requirement, dependency-decision, approved-project-writing-profile, committed-memory, approved-character-behavior-profiles, memory-subjects |
| REVIEW_CHAPTER_COMPLIANCE | CP-006.v4 | task-input, target-chapter, target-version, approved-plan, review-creative-brief | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, approved-project-writing-profile, recent-approved-chapters, approved-character-behavior-profiles, memory-subjects |
| REVIEW_CHAPTER_NARRATIVE | CP-006.v4 | task-input, target-chapter, target-version, approved-plan, review-creative-brief | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, approved-project-writing-profile, recent-approved-chapters, approved-character-behavior-profiles, memory-subjects |
| PLAN_CHAPTER_REVISION | CP-007.v8 | task-input, target-chapter, target-version, approved-plan, approved-project-writing-profile, review-creative-brief, revision-contract | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, recent-approved-chapters, source-quality-review, revision-plan, revision-candidate, revision-human-feedback, approved-character-behavior-profiles, memory-subjects |
| REVISE_CHAPTER | CP-007.v8 | task-input, target-chapter, target-version, approved-plan, approved-project-writing-profile, review-creative-brief, revision-contract | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, recent-approved-chapters, source-quality-review, revision-plan, revision-candidate, revision-human-feedback, approved-character-behavior-profiles, memory-subjects |
| VALIDATE_REVISION_FIDELITY | CP-007.v8 | task-input, target-chapter, target-version, approved-plan, approved-project-writing-profile, review-creative-brief, revision-contract | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, recent-approved-chapters, source-quality-review, revision-plan, revision-candidate, revision-human-feedback, approved-character-behavior-profiles, memory-subjects |
| INTERPRET_CHAPTER_FEEDBACK | CP-008.v2 | task-input, target-chapter, target-version, approved-plan, approved-project-writing-profile, review-creative-brief, human-feedback | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, recent-approved-chapters, feedback-review, approved-character-behavior-profiles, memory-subjects |
| EXTRACT_CHAPTER_MEMORY | CP-009.v1 | task-input, target-chapter, target-version, approved-plan, review-creative-brief | effective-requirements, effective-decisions, dependency-chapter_plan, dependency-chapter_version, dependency-requirement, dependency-decision, committed-memory, memory-subjects |
| INTERPRET_CHARACTER_PROFILE | CP-010.v1 | task-input |  |

统一Forbidden：cross-project、非法status/authority、未绑定版本、未批准Profile/Memory、rejected/superseded source、无授权未来源、无关Profile/全N×Npair。Planner可读取归属明确的Knowledge；Writer只按POV owner+KNOWS grant；Review/Revision/Feedback保持GLOBAL_ONLY，POV relevance不增加知识权限。Writer不接全部exploration/rawrecentchapters。A07不接Profile或候选当Memory证据。CP010仅显式用户描述与服务端identity mapping。

## 9. Prompt Contract Audit

Pydantic OutputContract.json_schema生成StructuredOutput，parser与Prompt同源；Service补exactsource/authority/evidence语义校验。未修改历史Prompt版本，未用case特判。所有Profile/Revision/Feedback/Memory mutation arrays保持空；非法Schema输出在Contract validation阶段失败，不把内部格式错误冒充用户授权问题。

| Task | Latest TaskTemplate（审计实际值） | Output schema |
| --- | --- | --- |
| PARSE_CHAPTER_REQUIREMENT | parse-chapter-requirement.v3 | chapter-requirement-result.v1 |
| EXPLORE_CHAPTER_CONCEPTS | explore-chapter-concepts.v2 | creative-exploration-result.v1 |
| PLAN_CHAPTER | plan-chapter.v8 | chapter-planning-result.v2 |
| PLAN_CHAPTER | plan-chapter.v9 | chapter-planning-result.v2 |
| REVIEW_CHAPTER_PLAN | review-chapter-plan.v5 | chapter-plan-review-result.v2 |
| WRITE_CHAPTER | write-chapter.v5 | chapter-writing-result.v1 |
| REVIEW_CHAPTER_COMPLIANCE | review-chapter-compliance.v2 | chapter-compliance-review.v1 |
| REVIEW_CHAPTER_NARRATIVE | review-chapter-narrative.v3 | chapter-narrative-review.v2 |
| PLAN_CHAPTER_REVISION | plan-chapter-revision.v7 | chapter-revision-plan.v4 |
| REVISE_CHAPTER | revise-chapter.v8 | chapter-revision-result.v3 |
| VALIDATE_REVISION_FIDELITY | validate-revision-fidelity.v5 | revision-fidelity-result.v3 |
| INTERPRET_CHAPTER_FEEDBACK | interpret-chapter-feedback.v3 | chapter-feedback-result.v1 |
| EXTRACT_CHAPTER_MEMORY | extract-chapter-memory.v3 | chapter-memory-result.v2 |
| INTERPRET_CHARACTER_PROFILE | interpret-character-profile.v1 | character-profile-draft.v1 |

Prompt中仅方法/规则，故事、角色、知识与反馈作为UNTRUSTED Context data。历史module/profile/schema版本继续resolve。

## 10. Creative Exploration Integration

只在v4 C04按policy启用；A03持久candidate与selection/rejection diagnostics。selected concept作为A7显式source交Plan，Plan仍需原Review/人工approval。未调整候选count/schema/selectionpolicy/main逻辑。rejected sentinel在下游package/Memory中必须缺席；selected source与PlanGeneration exact pair校验。

## 11. CharacterBehaviorProfile Integration

Profile是可选、sparse倾向；manualidentity只创建user-provenance Character，不制造Canon state/knowledge。current Draft v2与approved v1分离，各任务只选择exact approved v1。匿名POV/实际Plan story字段参与角色识别，currentPlan不能替换workflow-bound Plan。旧无Profile项目继续工作。

## 12. Relationship Modifier Integration

仅同项目、非自身counterpart，one counterpart one modifier；Context只保留双方task-involved的pair，绑定enclosing Profile version/hash。无关Atlas及其pair、DraftProfile在回归输入中排除。不是全项目人物关系dump或行为脚本。

## 13. Knowledge Firewall

Canon与角色Knowledge独立；KNOWS/BELIEVES/SUSPECTS/DOUBTS不互相提升。Profile不会制造know_fact或授予秘密。future filtering、ownership、epistemic、explicit task relevance继续由原MemoryQuery/ContextFilter enforce。现有真正已提交双角色知识测试与POV回归纳入全量suite；不以Prompt提醒代替工程边界。

## 14. Writing Integration

Writer依据exactapprovedPlan/批准偏好/相关Profile与合法memory；不拿latest/current DraftPlan。Draft创建不改变approved_version。既有Lineage与Authority snapshots保持，checkpoint未改Writer算法/Prompt。三类项目生成Draft v1，随后Revision产生同章v2。

## 15. Review Integration

Review只是诊断，不自动批准，不产生Canon。两pass绑定同一Draft和Authority/profile snapshot；v2审阅必须指向新Draft UUID。Profile相关诊断可通过现有WEAK_CHARACTER_VOICE等taxonomy表达，不新增CharacterEngine。非法cross-field requirement coverage与missing-MUST、推荐不升级约束的回归继续保留。

## 16. Revision Integration

A06 result contract与Structured schema/Prompt/Service一致，proposed_changes必须空；major change unresolved/blocked。独立Fidelity之前candidate不当正式Draft；保留strengths/scene spine/semantic locality。根集成回归确认sourceDraft仍不可改、newDraft UUID不同、Fidelity PASS后才Review新版本。

## 17. Human Feedback Integration

“Mira不像她，请局部改对白”通过现有反馈解释路由REVISION，sourceDraft/ref准确；currentProfileDraft2/approved1保持、WritingProfile不被自动学习修改。长期偏好/重大方向/矛盾反馈继续停对应人工gate。该Recorded案例检验路由/persistence，非模型诊断效果。

## 18. Memory Boundary

Draft/Plan/Exploration ≠ Canon；MemoryProposal ≠ committed entry。只有accepted finalDraft、A07 evidenced proposal与人工selected IDs进入commit。测试在finalization、proposal阶段均无entry，确认后A6 summary只绑定Draft v2，下一章Planning读取该entry。原五章fixture检验supersededDraft和秘密隔离，未改变012 core semantics。

## 19. Freshness

Explore/Plan/Review scheduling，Writer/Review/Revision/Feedback Authority binding与completion transaction持续核对profile/source指纹。新增批准或批准版本漂移包括空selector→首次批准均使旧任务失效；单存Draft不改变输入。新显式任务可使用其创建前批准的新Profile，不强制旧ApprovedPlan永久重规划。解释报告preflight与post-IO expected_version/Lock均检查，stale不落Profile。

## 20. Lineage

Required Fix：014解释从临时execute_report补为真实standalone A02 AgentTask/Run，并复用现有ContextPackage/PromptLineage/ModelProfile pins持久化。IO前短事务固化同一个prepared request；Provider外部IO不持锁；成功ProfileDraft/Run/Task/audit同事务；Provider/schema/低置信/stale/Lock失败保留实际trace，无autoapprove。

只读新增端点：`GET /api/v1/projects/{project_id}/characters/{character_id}/behavior-profile/interpretations`（分页）。report_character_id真实绑定Character；无Chapter/Workflow，后台Worker排除。GET interpretations→既有Task runs/prompt-lineage/context可查；成功metadata.profile_record_id精确关联草稿。只读Context inspection支持report，无latest重建。内部smoke仍是非产品临时诊断。

## 21. Historical Compatibility

旧v1/2/3 Workflow definitions、旧Prompt/Context版本保留；013 PlanGeneration pair nullable，旧记录不补造exploration；Profile可缺省。Migration populated兼容验证见32，空表upgrade不当历史回填证据。存在新standalone report时0020 downgrade明确阻止；仅先导出不能让原约束容纳report，应保留证据并另行决定人工回滚方案，不能删除历史execution；manualCharacter的0019 downgrade既有保护保留。

## 22. Context / Token Audit

实际Mock ModelRequest采样（本机`.runtime/checkpoint001/context-token-lineage-samples.json`）与三类compatibility样本包含task/selector/source_type/logical_id/version/authority/selected_reason、hash与items/tokens。估算使用现有保守estimator，非Provider真实计费，也非production benchmark。

| Task | Items | Estimated Context tokens | Prompt/schema overhead |
| --- | --- | --- | --- |
| PARSE_CHAPTER_REQUIREMENT | 3 | 3082–3110 | 18577 |
| PLAN_CHAPTER | 5–7 | 7181–9141 | 21595 |
| REVIEW_CHAPTER_PLAN | 5–8 | 9106–11975 | 15735 |
| WRITE_CHAPTER | 3–6 | 6020–9553 | 23967 |
| REVIEW_CHAPTER_COMPLIANCE | 6–8 | 12508–12972 | 16048 |
| REVIEW_CHAPTER_NARRATIVE | 6–8 | 12508–12972 | 23311 |
| INTERPRET_CHAPTER_FEEDBACK | 10 | 15385 | 15172 |
| PLAN_CHAPTER_REVISION | 10 | 23451 | 24602 |
| REVISE_CHAPTER | 11 | 26605 | 18443 |
| VALIDATE_REVISION_FIDELITY | 12 | 28811 | 16672 |
| EXPLORE_CHAPTER_CONCEPTS | 4 | 5591 | 15132 |
| EXTRACT_CHAPTER_MEMORY | 5 | 11311 | 14647 |

Writer只选relevantprofiles/pairs、effectiveMemory和批准Plan，不灌全部候选/全部Profiles/全量Memory/最近原文。上限来自现有profiles，无新增猜测性hard limit。Schema/Prompt overhead相对高，当前fixtures仍在原budget/window内；是否优化等待真实context/latency evidence。

## 23. Acceptance Readiness Tooling

复用 `evals/e2e/multi-chapter/run.py`、标准Worker--once、既有scope/DB/migration/oneattempt preflight。`check-prerequisites`只读核对专属Project marker、批准Profile及真实已完成/人工commit来源；记录精确source证据与chapter_sequence_base，不写API、不给Canon seed，起始实际sequence为旧历史max+1。轻量manifest声明capabilities/provider/human/prereq/status；prepare只合法API创建dedicated Project/identity/ProfileDRAFT，fixedfixtureUUID映射真实ID。不注入evaluator_only/secretanswer/baseline或伪造approved memory。run-to-next-gate有明确预算并停WAITING_HUMAN/failure/escalation，continue需真实人工transition；不会代approve/finalize/confirm或自动五章。

GET-only export补run/test/project/provider/model_profile/time/human_gates/status，characters/current/approved/versions/interpretation traces；原Plan/Draft/Review/Revision/Feedback/Memory/Run/Prompt/Context证据保持。Name-hidden prose aid供人工盲读，原完整evidence保留，不算自动声线评分。Debug复用既有折叠/GET，不新Dashboard。

## 24. E2E-001R Readiness

保留原独立五章场景与v3路线；之前明确批准的WritingProfile不等于批准任意后续Plan/Draft/Memory，更不授权013/014真实调用。状态PENDING，逐gate执行/导出路径准备好；真实连续章与人工质量尚未验证。本轮不推进既有真实项目。

## 25. NOVEL-013R Readiness

保留Case03/repetition/authority fixtures与A BETTER / B BETTER / TIE定性模板，记录autonomy/diversity/character specificity/repetition/authority/plan差异。新流程显式v4；真实历史profile/history/authority不满足则BLOCKED prerequisite，不复制eval JSON成Canon。未宣称创意更好；REAL_ACCEPTANCE_REQUIRED。

## 26. NOVEL-014R Readiness

same situation/different character、same character/different relationship、motivatedOOC压力、knowledge boundary与noProfile对照均有输入与人工模板。prepare只创建实际identity+所选ProfileDRAFT；人工批准保持独立。knowledge case需要真正committed owner证据，不seed syntheticsecret当验收PASS。Human评action/logic/voice/POV/relationship/knowledge/naturalness，盲读只辅助，不自动评分。REAL_ACCEPTANCE_REQUIRED。

## 27. Contract Freeze

[13-Phase2-Contract-Freeze](../specs/13-Phase2-Contract-Freeze.md) 固定Authority/roster/Workflow/Memorycommit/Knowledge/Exploration/Profile/Revision/Feedback；只在correctness bug、real evidence或explicitADR时改变。初始12项Pydantic schema指纹与历史modules/profiles/migrations在本轮复核。ADR CHECKPOINT001-01仅扩展existingTask reportscope和冗余memory_subject uniqueFK，不改Memory/Profile核心contract。12项Schema、7个Agent与8层Authority复核全部相同；初始218个Prompt文件、40个Context Profile文件及19个已有migration逐文件SHA-256均未改变（本机historical-hash-verification.json）。

## 28. Bugs Found

| ID | Initial audit / Root cause | Disposition |
| --- | --- | --- |
| D1 | 014同步A02解释只复用compile/generate/parse，未持久真实run/context/prompt；§19 Required Fix | 修复真实Task/Run lineage与Inspector |
| D2 | acceptance runner固定chapter-quality v3，无法走013探索 | manifest-selected新case v4，旧默认不变 |
| D3 | run/test/time/humangates/status metadata与bounded stop/resume不齐 | 补原runner，不新executor |
| D4 | exporter缺完整CharacterProfile versions/approval pointers/report traces | 补原GET-only export与既有Debug折叠 |
| D5 | 三种历史paid flags易混淆新的Phase2调用授权 | Phase2主入口统一现有--allow-real-provider；历史诊断不自动参与 |
| D6 | 独立Review离线复现：E2E fixture_hash只覆盖scenario.json，修改chapter02～05输入仍保留原hash | 新run绑定scenario和全部五章输入；旧partial baseline只读导出，禁止静默继续付费 |

审计发现populated0019回填验证缺口，未复现前不宣称升级bug。新0020初稿revision ID超过Alembic32限制在局部测试中发现，已缩为28字符；这是本轮开发中修复，不是旧产品根因。旧migration tests hardcoded head维护也属于必要测试更新。

## 29. Bugs Fixed

D1～D6已修复，无遗留工程阻塞。014补齐真实持久Task/Run/CP/PromptLineage与现有Debug；验收工具复用旧runner补完整case/metadata/export/budget/human-boundary与全输入baseline，并以GET-only check-prerequisites解除合法来源已准备的BLOCKED状态。初稿0020长revision ID、旧migration head断言和旧test helper的collection import仅作局部修正。不调整Writer/Quality/Exploration/Profile payload，不扩大Authority，不fakeChapter/Workflow/Run，不把复杂模型行为判断硬编码。失败output/Provider/stale与成功路径均有工程证据；最终不保留未解决D1～D6。

## 30. Deferred Phase 2 Candidates

015 Long-range Story Planning、016 Retrieval Improvement、017 Arc/Story Management均DEFERRED_PENDING_REAL_ACCEPTANCE，只有依赖/风险记录，未排序未实现。没有VectorDB/Redis/Kafka/新Agent/新Memorylayer。

## 31. Regression

**Backend：1708 PASS / 4 opt-in SKIP / 0 FAIL**，标准collection共1712项；四个按文件hash分片与两个runner文件的nodeid集合严格等于标准完整collection，每项恰好执行一次。分片分别464/429/427/350 PASS（skip1/0/2/1），另runner31/7 PASS。本次最终suite包含001～014、013/014 focused、Memory/Context/Revision/Feedback/E2E工程。测试期间600个Backend源码/测试文件逐文件hash不变；完整证明在本机ignored `backend/.runtime/checkpoint001/full-suite-evidence.json`。此前的1634/168结果不替代本次验证。

4个跳过原因为显式`--live-model`未启用：OpenAI Provider smoke、真实Planning E2E、真实Writing smoke、Case01一次真实Requirement。未删除skip，未Mock后声称真实验收PASS。Backend仅有2种既有第三方deprecation warnings（Starlette/httpx、anyio BlockingPortal），无测试失败。

**Frontend：177 PASS / 13 files；lint、typecheck、production build PASS。** 最终Backend `ruff check .` / `ruff format --check .` PASS（448文件）；evals/scripts使用同一pyproject配置check/format PASS（25文件）；`git diff --check` PASS。最后两处Backend样式修正已记录AST完全相同；两个旧eval/导出utility只整理既有imports/格式，imports集合和其他AST不变，CLI --help及10个既有style-export测试补验PASS，无Quality或写作逻辑变化。新tests仅本地，不提交，沿用用户偏好。最终补跑runner纯fixtures31 PASS / API7 PASS，两个文件分别运行以避免已有pytest目录collection次序问题；新增人物旧项目/013/013+014集成、局部人物质量Revision、解释lineage错误/并发/rollback与populated migration均纳入全量。

## 32. Migration

PASS。隔离PostgreSQL `_test` schema实际执行 `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` → `alembic check`，head依次0020_character_report_lineage → 0019_character_behavior_profile → 0020 → 0020，check无新操作。另有populated回归：真实应用管线已人工确认七项Memory候选并完成C16，退到0017后升级0018→0019→0020；核对所有原table/columns/rows完全不变、Subject.created_at/by等于原commit provenance。新report历史降级拒绝并保留Task/Run/Context/Prompt证据。单独迁移组10 PASS，最终全量仍包含这些回归。

## 33. Docker

PASS。现有Dockerfile成功构建，Backend和独立Worker角色使用同一image；非root用户novel，无发布端口。测试config强制mock-default、独立_test schema，Worker `--once`退出0，没有付费任务。容器内health和health/db均200，迁移结果见32。原本机8000 health/db及5173在检查前后均200；测试容器、schema和private config已清理，原服务未重启。初次Worker启动失败来自本机ignored验收脚本的os.execv argv[0]：写成python导致解释器选择/usr/local，找不到虚拟环境pydantic。离线双路径复现后只修验收脚本为/app/.venv/bin/python，未改Dockerfile/产品Worker；保留失败证据后完整重跑PASS；格式修正后的最终源码再build/start/upgrade-downgrade-upgrade/check/health/Worker完整重验PASS，source_hashes_match=true，最终同一image为`sha256:a9d5386b9b37ccf93f4fce9984707e70eed46093ead8debad435907f355ce64c`。锁定依赖下载约5分钟，未因此改变Dockerfile或产品网络。

## 34. Independent Review

PASS，当前无未修P1/P2。采用两位作者交换其未编写部分的peer independent review；尝试fresh reviewer线程因thread limit失败，不把此审查称为无上下文盲审或把自审当独立批准。persistence/query/API/frontend由Runtime作者检查（独立6项持久化、25项UI PASS）；Runtime/Service/Context/PromptLineage/runner由persistence作者检查，最终纯Mock39 PASS。E2E输入hash P2离线复现后已独立关闭；5章逐章mutation均改变hash、legacy paid continuation在API前拒绝且只读证据可导出。两份本机ignored报告是independent-persistence-ui-review.md、independent-runtime-acceptance-review.md，源码指纹有记录。最终格式修正后peer再次只读核对：598/600文件指纹不变，两处既有审查文件的before/after哈希准确，独立逆转格式后完整AST相同，没有第三处Backend/source/test变化。检查15项：001～014主链、7Agent、Authority、Prompt/Schema/Service、Knowledge、候选隔离、Profile非脚本、Context预算、Prompt不污染、历史兼容、Freshness、Revision Fidelity、Feedback Scope、Memoryfreeze、无015。仅报告可复现actionable findings，不以artifact文案代替代码与检查。

## 35. Known Limitations

真实模型创造性/人物自然度/连续章质量、人工文学评价PENDING；旧E2E state仅绑定scenario的partial baseline只能只读导出，继续真实执行需人工核对完整输入后使用新的独立state/Project，不能自动重绑未知历史。Mock只证明工程边界。复杂fixture的真实历史Knowledge/authority先决条件必须人工通过合法管线准备。同步解释API process crash可能留下RUNNING诊断，但Worker不会自动付费重试；人工可读取已固化trace后显式再次请求，未新增全局recovery框架。既有本地single-user actor模型不改成多租户认证。实际开发部署需由用户另行授权更新/迁移/重启；本轮只验证隔离副本。

## 36. Final Acceptance Result

**CHECKPOINT-001 = PASS_WITH_BLOCKERS_RESOLVED**。

| Acceptance | Result | 依据 / 下一步 |
| --- | --- | --- |
| Engineering Integration | PASS_WITH_BLOCKERS_RESOLVED | D1～D6关闭；完整后端1708 PASS/4 paid SKIP、前端177 PASS、lint、migration历史兼容、Docker Backend/Worker与十五轴交叉Review通过。 |
| Real Provider / AI Behavior | PENDING | 本轮paid calls=0；manifest/合法prerequisite/逐gate opt-in执行和精确lineage已准备，不自动跑模型。 |
| Human Prose / Creative / Character Evaluation | PENDING | 人工比较模板与name-hidden aid准备好；尚未证明连续章、创意多样性或人物自然度改善。 |

当前没有未解决的工程阻塞。保持Phase 2 core contracts冻结；没有实现015/016/017，没有提交或推送任何代码，没有运行开发DB迁移/重启。测试代码保留本地。完成后停止，下一步由用户决定并显式授权真实验收。

## 37. Follow-up Review Fixes

后续独立整体 Review 确认两项可复现问题。本次仅修复验收范围与输入绑定，未调整 Writer、Quality、Prompt、Schema、Authority 或数据库模型。

| Finding | Root cause | Fix |
| --- | --- | --- |
| D7 / P1：Worker 可领取审计范围外任务 | API 与 Worker 数据库若保留相同目标 IDs，但 Worker DB 多出高优先级任务，目标记录核对仍通过；原全局 claim 可以消费额外任务，事后 attempt 检查才发现异常 | 在 Worker 实际 DB 检查全部活跃章节 Task IDs 与 API 审计集合完全一致；复用标准 Worker / AgentQueue / Repository，透传可选 task_ids SQL 过滤。runner 自动传 repeatable --task-id，仅允许 --once；预检后新增外部任务也无法被此次执行领取 |
| D8 / P2：历史 A/B 的 Writing Profile pin 未复核 | check-prerequisites 绑定批准 v1 后，批准 v2 新 POV；start 只检查批准记录存在，比较输入已不一致仍能开始 | start 与每次已绑定 run 的 one-task 都核对 approved record ID/version/hash；变化在 API mutation 或 Worker 启动前拒绝。未批准 Draft 不改变批准输入，不自动更新旧 pin |

无 task_ids 的普通 Worker 保持原有领取及 legacy backfill 行为；显式空 ID 集不领取、不 backfill。质量阶段可传多个已审计 IDs，--once 仍只处理一个。独立人物解释 report 没有 Workflow，不属于后台领取队列。批准 Profile 变化后，尚未 start 的 run 可重新核验先决条件；已经 start 的比较保留历史证据并重新准备未启动的独立 run。

本次针对性测试 **131 PASS / 0 FAIL / 0 SKIP**，分两组且测试节点不重叠：

- `runner-fixes-new.xml`：52 PASS，包含既有 runner 31项和新增 Profile 7项、CLI 5项、实际 Worker DB 队列9项。
- `runner-fixes-existing.xml`：79 PASS，涵盖既有手动 API runner、scoped Worker、lease、Authority、Agent review regression 与 standalone report runtime。

新增21项测试只保留本地。队列回归复用既有隔离 PostgreSQL `_test` schema、正式应用 API 和 Mock Provider：验证合法队列只读通过、同/跨 Project 额外 PENDING/CLAIMED/RUNNING 及过期 lease 拦截、预检后 high-priority foreign task 入队仍只执行目标，以及空 ID 不 backfill。Profile 测试先运行真实 check-prerequisites 逻辑绑定历史 v1，再分别改变批准 ID/version/hash/POV，确认零 POST/Worker；新增未批准 Draft 则继续通过。

Backend `ruff check .` / `ruff format --check .` PASS（451文件）；evals/scripts 同配置 check/format PASS（25文件）；Worker CLI --help 与 `git diff --check` PASS。只有两类既有第三方 deprecation warnings。未重跑全量 pytest、Docker 或 migration downgrade；本次没有模型/迁移变更，隔离数据库测试均升级至现有 head。未访问或更改开发 DB，未重启本地服务；paid calls=0。

独立 reviewer 仅根据本次4个产品文件与 before-fix 快照核对补丁，确认 SQL 过滤保持原锁顺序、默认行为与多 Task 单次消费，未发现新的确定 P1/P2。报告级别仍为 Engineering PASS_WITH_BLOCKERS_RESOLVED；真实模型及人工验收继续 PENDING。D7/D8已关闭，本次源码指纹及 JUnit 证据保存在本机 ignored `.runtime/checkpoint001/runner-fixes-evidence.json`。
