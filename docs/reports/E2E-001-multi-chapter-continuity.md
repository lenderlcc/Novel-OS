# E2E-001 — Multi-Chapter Continuity Acceptance

## 1. Executive Summary

**Engineering Acceptance = PASS_WITH_BLOCKERS_RESOLVED。** 同一独立测试 Project 的五章均通过正式 API → Workflow → Agent Runtime → Context → 人工 Gate → Memory Commit，完成 C16。第4章实际生成 Draft v2，Review、Finalization 和 Memory 绑定该版本。

**E2E-001 完整 Product Acceptance = FAIL（尚缺真实模型与人工验收证据）。** 这里的 FAIL 表示完整产品验收尚未完成，并非已发现未修复的产品阻塞。Recorded Provider 输出验证持久化、版本、Authority、知识筛选和事务；它不能证明真实 A07 能正确提取、真实 Planner/Writer 能遵守知识边界，或人工认为正文合格。用户要求显式启动真实模型，本轮未自动调用。

| Dimension | Result | Evidence |
|---|---|---|
| Five-chapter engineering | PASS_WITH_BLOCKERS_RESOLVED | 正式链路，41 AgentRuns，5 Completed Chapters |
| 26 automated targets | PASS | coverage.json 与正式 Context / 负向回归映射 |
| AI Behavior Acceptance | NOT RUN | 真实 Provider 调用0次 |
| Human Continuity / Prose Evaluation | NOT RUN | 模板与逐阶段入口已建立，未伪造人工决定 |

前置 BP-01 对象状态和 BP-02 同一 Thread 更新已修复。恢复 E2E 仅新增夹具、测试、CLI/导出与文档；没有新产品架构、Agent、存储或 Phase 2 功能。

## 2. Test Environment

- 2026-10-05，Asia/Shanghai。
- 仓库 `/Users/agiuser/novel-os/Novel-OS`；分支 `wfg/novel-012-memory-commit`；基线 `1cb275d2439af3e9c5e2982002ca9c1d4fc9e107` 加当前未提交修复。没有切回缺少012的旧 main，也没有提交、推送或合并。
- Python3.13.12，已有 backend/.venv、PostgreSQL16、pytest、Ruff；配置只读本机 TOML，无环境变量、无新依赖。
- 每个集成测试使用已有独立 `_test` 数据库中的临时 schema，正式 Alembic 迁移到0017，测试结束清理；未改 Case01～05。
- 本轮无真实 Provider 调用，无测试脚本直接插入 Canon 或修改人物状态。
- 首次工程验收时，用户开发库/API/旧 Worker 尚未部署本次代码和0017。用户随后授权“更新然后验证一下”，已完成本机0017升级和前后端重启，独立复核通过，详见第32节；真实模型 Worker 保持停止，使用人工逐阶段入口。

| Regression | Result |
|---|---|
| Backend full pytest | 最终1495项：1491 PASS / 4付费opt-in SKIP / 0 FAIL（全量1493项 + 2项后补保护用例） |
| Continuity focused regression | 133 PASS，214.51秒 |
| Formal five-chapter test | PASS，最终单项27.78秒；全量最终证据见日志 |
| Additional real Context builds | 3 PASS，25.72秒 |
| Manual runner API/guard tests | 5 formal API PASS（最终6.69秒）+ 11额外guard PASS |
| Frontend npm test | 149 PASS，11 files |
| Frontend lint / typecheck / build | PASS |
| Ruff / format / diff | PASS；Backend398 files + Runner1 file |
| Alembic upgrade → downgrade -1 → upgrade / check | PASS，临时隔离 schema，无 metadata drift |
| Docker backend / worker build | PASS，使用本次前置修复镜像 |
| Docker startup / health / health-db | PASS，容器内部；宿主经临时显式 SSH forwarding 两接口200 |
| Automatic Colima published-port forwarding | FAIL，自动forward建立失败；没有伪称环境全通过 |

日志位于忽略的 `backend/.runtime/e2e001-acceptance-full-0.log`～`3.log`、`e2e001-continuity-regression.log`、`e2e001-final-migration.log`，以及根 `.runtime/e2e001-frontend-*.log`、`.runtime/e2e001-acceptance-docker-build.log` / `e2e001-acceptance-docker-health.json`。完整回归用 nodeid SHA256 modulo4互斥分片，四片覆盖1493项同一收集集合；之后新增2项Runner保护参数用例。最终5项Runner测试重新执行，nodeid并集与当前1495项collection完全一致，无遗漏、无重复分片或失败。各分片395/379/372/343 PASS，skip分别0/1/2/1，耗时424.70/401.39/388.62/330.31秒。验收manifest在 `.runtime/e2e001-final-verification.json`。没有为通过而删测试。测试代码按用户要求仅保留本地，不提交。

## 3. Project Fixture

夹具目录：[evals/e2e/multi-chapter](../../evals/e2e/multi-chapter/README.md)。复用 JSON eval 结构，没有 YAML DSL、QA数据库或管理UI。

- scenario.json：独立 Project、Approved Writing Profile、抽象实体与 failure tags。
- chapter-01～05.json：逐章输入、Recorded prose、第四章修订目标。
- expected-memory.json / expected-context.json：当前与历史预期。
- coverage.json：26项自动覆盖映射。
- run.py：显式人工命令与只读trace导出。
- manual-prose-evaluation.md：每章三个人工Gate及AI/Continuity/Prose记录。

冻结完整离线 trace：`.runtime/e2e001-acceptance-trace.json`，避免后续pytest覆盖本报告UUID。最近完整离线 trace Project ID：`1dac0f39-ee9e-415a-868e-e11dae95c4a5`；Profile v1 APPROVED，A5，record ID `17332b8e-ebbc-4178-9b26-28f007aa7c13`。**该 Project 属于已清理的测试 schema，不能拿这些 UUID 在当前 Workspace 操作。** 人工 runner 会新建独立、持久 Project。

fixture semantic IDs 只用于测试；通过已提交 candidate IDs 建立实际 identity映射，断言比对 UUID / logical_id / source version，不以名字决定身份。

| Semantic ID | Actual subject UUID in trace |
|---|---|
| A | `a7fcaf59-493f-5508-bbfd-f4fba9a6abab` |
| B | `0bc42542-990a-51f9-a1ea-35d03d5c24e7` |
| X | `04e0cf45-41b6-5732-838c-46e45ee0cdbd` |
| K | `09417903-5cb7-5819-b5c9-5533da428db3` |
| T | `a83b7210-7f00-5659-b31c-370e783132eb` |

L1/L2 为地点值；Y 为事件属性；Z 只存在于被放弃的 Draft v1，不创建正式 Memory Subject。

## 4. Chapter 01 Flow

正式 Requirement → Planning → Review → **显式 Plan Approval** → Writing → 两类 Quality Review → **显式 Draft Acceptance** → A07 → **显式选择候选确认** → Commit / C16。

得到 X Canon、A KNOWS X、B 无X；A在L1，B在L2，K INTACT，T OPEN，合作关系/任务PENDING及忠实 Derived Summary。9候选、9提交。Profile approval保持A5，不提升Authority。

## 5. Chapter 02 Flow

B POV：实际 Writing CP的完整payload不含A独享X；B当前状态的source UUID正确。A L1→L2生成location v2，旧v1仍可历史查询。A对Y产生SUSPECTS，未生成“B负责Y”的Canon。

K未变化的候选DUPLICATE，4候选显式选择后只提交3条，skip1。人工excluded=0，未把duplicate误计为人工排除。

## 6. Chapter 03 Flow

正式Canon确认B不是Y责任方；K INTACT→DESTROYED追加v2、supersede旧v1。T本章未处理，当前T仍是第1章OPEN条目。

A亲眼读取真相，所以其knowledge:Y由SUSPECTS/B_RESPONSIBLE v1更新为KNOWS/NOT_RESPONSIBLE v2；旧怀疑作为历史认知保留。没有把已经读到真相的A继续当作当前仍怀疑B。

## 7. Chapter 04 Revision Pollution Test

真实工程路径：Writing Draft v1包含Z → Human Feedback → interpretation → RevisionPlan → A06 → Fidelity Validation → **Draft v2** → A05 Review v2。

Finalized ChapterVersion：`0e85f47d-a0fa-4327-a1b5-9b6abc860208`，version2。同一Chapter，UUID改变，supersedes指向v1；v1内容保持不变。Quality Review的chapter_version_id绑定v2。

A07的target-version source UUID/content与accepted v2完全一致；CP无v1 source。Z不进入任何Memory类型、Summary、Thread或下一章Writer CP。

AI Review-directed Revision另由既有正式 `test_revision_full_slice_stops_after_rereview` 回归覆盖；本章用Human Feedback路径确保人工定向修订也接入同一Runtime/Fidelity链路。未把Fidelity Recorded PASS冒充真实模型判断。

## 8. Chapter 05 Retrieval Test

Raw Requirement没有重述全部历史状态。实际A03 Planning CP包含A当前L2、K当前DESTROYED、T更新后仍OPEN、A当前KNOWS与B否定责任Canon、合作关系与任务。

旧L1、旧INTACT、旧Thread描述、旧SUSPECTS条目不在current CP，历史API仍能查询。A的过去怀疑属于历史，不能在当前上下文伪装成仍有效判断。

A04 B POV取得B当前状态，整个WriterCP没有A独享X。对象/Thread连续性由A03读取真实CP后写入Plan information_release，再由**exact approved Plan**传递给Writer；校验DESTROYED、OPEN、L2，以及无INTACT/X。没有声称Writer直接读取了本来被知识策略排除的非POV记忆。

## 9. Canon Continuity

X保持正式Canon；B负责Y的SUSPECTS没有晋升Canon，真相单独为Canon。对象状态追加版本，不静默改写旧Canon行；staticCanon矛盾仍阻断。正式冲突负向测试返回409，Chapter不Completed。

## 10. Character State

A location、K condition各有稳定logical_id/version/supersedes链；当前查询排除前驱，历史查询保留。K用OBJECT + CANON_FACT的明确state_after标记，未伪装成CharacterState，也未让所有staticCanon可修改。

## 11. Character Knowledge

五章确认A KNOWS X、B没有X。补充正式Context测试建立两个真实owner及各自KNOWS→known_fact_id关联，正向验证Canon仅随正确owner进入Writer，双向私有信息均不泄漏。

KNOWS/BELIEVES/SUSPECTS保持owner和epistemic_status，不能当成同一种GlobalCanon。A读到纠正后的证据创建认知后继，保留过去SUSPECTS。

## 12. Knowledge Firewall

Writer CP按exact approved Plan的POV UUID查人物state/knowledge/relationship；私有Canon只通过显式KNOWS关联。未知owner不放开权限。隔离测试同时验证正向可见与反向不可见，避免“都不返回”冒充firewall正确。

五章中的B整包secret排除、补充双owner用例工程PASS。真实Planner是否错误把A秘密写进B Plan/真实Writer是否违背边界仍需人工检查；Recorded fixture不证明该行为。

## 13. Belief vs Truth

Ch2SUSPECTS是人物状态；Ch3Canon真相为B NOT_RESPONSIBLE，A自身认知转KNOWS。过去怀疑记录仍存，当前CP排除它。BELIEVES同样由参数化Contract测试验证不升Canon。

独立审查纠正了原fixture把“历史怀疑”误当“当前怀疑”的断言。这是验收夹具错误，未因此改产品业务规则。

## 14. Open Threads

T第1章OPEN，第3章未处理仍存，第4章加投递单新证据、追加同一logical_id的v2，状态仍OPEN；不创建T2。第5章A03按相关subject获取v2，排除旧描述。

OPEN_THREAD仍A6_DERIVED_MEMORY；状态或描述合法更新必须精确state_before/state_after，同值同描述只是新出处仍跳过。

## 15. Duplicate Detection

Ch2K未变化，normalizer为DUPLICATE、Commit skipped，不产生新Canon Version。额外回归验证同值同claim仅换证据也跳过；同批去重不放宽Authority/身份检查。计数把人工未选、duplicate与skipped分开。

## 16. Conflict Detection

既有/新增正式负向用例覆盖明显矛盾、同批多条互斥state、staticCanon被假装对象transition、wrong/missing before和Normalizer误判但DB guard拒绝。

Conflict选择确认失败时无新batch/subject/entry，不Completed；排除冲突后仍可确认其他合法候选，不silent overwrite。

## 17. Authority

保持A1 USER_LOCKED → A2 USER_APPROVED → A3 CANON → A4 APPROVED_PLAN → A5 USER_PREFERENCE → A6 DERIVED_MEMORY → A7 AI_INFERENCE。Context冲突测试覆盖A6/A7不能覆盖高Authority；用户locked Decision阻断对象candidate，审批/确认仍由真实用户操作产生。

Repository只flush，Service控制Transaction。没有给A07直接COMMIT_CANON权限，也没有新增reopen。

## 18. Finalized Version Isolation

每章request.chapter_version_id、A07 target UUID、quote source version、Commit entry.chapter_version_id与human accepted Draft一致。Ch4为v2；不能因为latest或旧Review使用v1。最终章current_version与approved_version均等于acceptedversion。

| Chapter | Chapter ID | Final version | Accepted ChapterVersion ID | State |
|---|---|---|---|---|
| 01 | `df7b3d22-5e52-4b89-bffb-40d97d342ca8` | v1 | `bff25cc1-f956-4fb7-925a-4c66674a832e` | C16_COMPLETED |
| 02 | `cfd29ea5-c8ac-43a5-afff-ae59274ede00` | v1 | `b3546b2d-468c-4353-a467-f35bae8d2215` | C16_COMPLETED |
| 03 | `bd01f4f6-d898-4180-9008-3e3e95c05789` | v1 | `297dc227-adc3-4da2-a3de-e0746c2195a8` | C16_COMPLETED |
| 04 | `a3395721-874f-43d9-b5b3-563f343a6122` | v2 | `0e85f47d-a0fa-4327-a1b5-9b6abc860208` | C16_COMPLETED |
| 05 | `806264f2-24b0-4ff5-ba45-0e0a51dd087a` | v1 | `bdd0ac1e-277a-40cb-b66b-c234f31bf615` | C16_COMPLETED |

## 19. Rejected / Superseded Draft Isolation

当前Domain没有REJECTED enum，测试适用的是**未接受的、被后继版本替代的Draft**；未谎称建立了REJECTED生命周期。Ch4v1有Z但最终v2无Z，正式长期Memory及Ch5 CP无Z；旧v1仍能从版本history追溯。

不接受直接修改旧content。Writer当前profile排除旧章原始正文；Memory来源只认exact acceptedVersion；未确认proposal也不进入正式Planning CP。

## 20. Memory Signal / Noise

| Chapter | Candidate | Committed | Human excluded | Duplicate | Conflict |
|---|---|---|---|---|---|
| 01 | 9 | 9 | 0 | 0 | 0 |
| 02 | 4 | 3 | 0 | 1 | 0 |
| 03 | 4 | 4 | 0 | 0 | 0 |
| 04 | 2 | 2 | 0 | 0 | 0 |
| 05 | 1 | 1 | 0 | 0 | 0 |

这些是诊断数量，不是质量分数或固定每章配额。Recorded候选只包含场景连续性状态/知识/关系/任务/Thread/Summary，没有开门喝水之类装饰动作。

真实A07 Good/Missing/Wrong/Noise与authority/knowledge problems尚无人工结果；不能据9/4/4/2/1候选量宣称模型信噪比合格。

## 21. Context Retrieval

精确project、subject、sequence、current版本与POV查询，未引入Embedding/VectorRAG。A03取得相关Thread，同时正式补充用例排除无关Atlas Thread和其他owner状态；不是全项目Memory回填。

A04取得当前POV状态与知识owner；非POV对象/Thread交由批准Plan交接。Future REQUIRED_ONLY由已有显式futurePlan负向回归证明，不以profile属性字符串代替行为测试。

## 22. Context Package Analysis

每章实际Planning/Writing ContextPackage、Task/Run、PromptLineage/compiled hash、ModelProfile以及WritingResult已导出。41Run均SUCCEEDED且有对应CP/Lineage，无missing required或Authority conflicts。

| Chapter | Task | ContextPackage ID | Included | Policy excluded |
|---|---|---|---|---|
| 01 | PLAN_CHAPTER | `29a3170c-aec8-4963-9799-a398d8c6bee3` | 5 | 0 |
| 01 | WRITE_CHAPTER | `d4c3e59f-8da7-4dd9-a4bf-5def31260f41` | 4 | 0 |
| 02 | PLAN_CHAPTER | `03ab4f33-335b-4816-8a2c-a42e8323ecb2` | 18 | 0 |
| 02 | WRITE_CHAPTER | `811e8196-fbde-4406-bff6-5006273de83b` | 5 | 0 |
| 03 | PLAN_CHAPTER | `bbd61c78-b4ae-44d8-a2b9-08a2f7bada66` | 20 | 0 |
| 03 | WRITE_CHAPTER | `3f81c515-de63-4936-a983-5de3ed8e2d76` | 9 | 0 |
| 04 | PLAN_CHAPTER | `da86ee52-9b52-4c3c-968e-ab9e3e58ff68` | 20 | 0 |
| 04 | WRITE_CHAPTER | `93ca3bfe-4886-4eba-9b52-5d4ff402f4f4` | 9 | 0 |
| 05 | PLAN_CHAPTER | `4114cc02-5367-4baa-a690-c6246241f4bb` | 22 | 0 |
| 05 | WRITE_CHAPTER | `9f9990b9-e0ac-49d5-80c5-a02aeae77683` | 5 | 0 |

Reader先按relevance/POV/current范围查询，未查询的私有/无关条目不在policy excluded列表；excluded=0不表示装入全部项目。排除理由由query边界、source UUID对照及负向断言验证。Context保留priority、Authority、source、version和selected_reason。

Recent Derived Summary是A6提示，没有盖过Canon；未把Ch1～4全文都塞给Writer。Planning保留既有previous-approved-chapter的最多一章，未新增全部历史正文路径。原文quote通过ChapterVersion/paragraph可追溯。

## 23. Workflow / Versioning

五章显式三Gate，Completion之后仍未Completed，确认Memory事务成功才到C16。Completed mutation guard、stale Draft/Canon/lock、transaction rollback和exactapproval由正式负向测试覆盖。

AI/Human Revision复用existingRevision/Fidelity，不新建平行路径。唯一既有testhelper改动为QualityDriver的可选raw_requirement参数，默认行为不变。

手动Runner每次只执行standard Worker --once；执行前要求显式付费opt-in/Worker stopped、全局队列隔离，并只读核对配置DB的migration head、唯一Project标记、Workflow和exact Task。没有通过DB插入数据或自建claim执行。

## 24. Failure Matrix

Tags仅存在eval/report，不加入StoryQualityTaxonomy。

| Tag | Engineering result | Layer / Evidence | Real behavior |
|---|---|---|---|
| CANON_DRIFT | PASS | Commit/current query/无staticoverwrite | NOT RUN |
| STATE_DRIFT | PASS | A/K v2 + current/history | NOT RUN |
| KNOWLEDGE_LEAK | PASS | 两owner正反向CP、B完整CP | NOT RUN |
| BELIEF_PROMOTED_TO_TRUTH | PASS | 知识/Canon分离，历史怀疑保留 | NOT RUN |
| OPEN_THREAD_LOST | PASS | omission保留 + 同identityv2 | NOT RUN |
| DUPLICATE_MEMORY | PASS | unchangedK skipped1 | NOT RUN |
| MEMORY_NOISE | Fixture only | 候选预设高信号，不能证明真实提取 | NOT RUN |
| REJECTED_DRAFT_LEAK | PASS（未接受Draft） | Ch4v1 Z不入v2Memory/Ch5 | NOT RUN |
| STALE_MEMORY_COMMIT | PASS | draft/canon/lock freshness409 | NOT RUN |
| AUTHORITY_OVERRIDE | PASS | lockedDecision/ContextA1～A7 | NOT RUN |
| CONTEXT_OVERLOAD | PASS（fixture规模） | 有限priorContext，无全部正文dump | NOT RUN |
| CONTEXT_MISSING_REQUIRED | PASS（fixture） | Ch5当前facts/approvedPlanhandoff | NOT RUN |
| DERIVED_MEMORY_OVERRIDE | PASS | A6Summary与高Authority冲突策略 | NOT RUN |

Docker自动hostforward是Environment failure，不伪装成Memory/Model问题。

## 25. Bugs Found

| ID | Root cause | Scope |
|---|---|---|
| BP-01 | OBJECT Canon状态不属于合法版本转换条件 | 012 Schema/Normalizer/DB guard |
| BP-02 | Thread不可转换且duplicate忽略描述 | 012 Normalizer/DB guard |
| PR-01 | 默认Task升级但正式StageMapping仍旧Schema | 012调度，原修复独立Review已关闭 |
| ER-01 | 手动脚本误用candidate_id读取规范化proposal | eval CLI，独立审查发现 |
| ER-02 | API检查队列不能证明任意Worker config连接同一DB | eval CLI安全前置，独立审查发现 |
| EF-01 | fixture让A读到真相后仍要求current SUSPECTS | 测试数据/断言，独立审查发现 |
| ENV-01 | Colima host agent自动SSHforward命令失败 | 本机Docker端口转发环境 |

Ch4fixture初始漏写POV人物名，既有A03身份validator正确拒绝未知POV；补齐fixture明确输入，未放宽validator，也没有Case01～05特判。

## 26. Bugs Fixed

BP-01/BP-02：复用6类Memory、logical_id/version/supersedes、人工确认与现有事务，0017只扩充既有relation guard合法条件；明确OBJECT旧state_after和新before/after，静态Canon仍不可转换。同Thread新描述可追加版本，unchanged只跳过。

A07新增Promptv3，历史v1/v2未覆盖；最新Schema/正式StageMappingv2一致，既有Context透传state_after。详见012报告和spec10。

ER-01改proposal.id并通过actualMemory确认API；ER-02新增只读既有DB/service身份与migration preflight，失败在Worker subprocess之前；EF-01使A知识创建KNOWS后继并断言旧SUSPECTS历史保留。所有必修项都经过独立复核及受影响回归。

ENV-01未改Colima/项目基础设施。临时显式SSHforward验证同Docker容器host health/db200，验证后清理forward和临时容器；自动forward限制仍记录。

## 27. Phase 2 Candidates

仅记录，不实现：

- 真实A07语义提取/候选信噪比调优，须先积累实际错例。
- 更细的“未查询”排除解释与相关性诊断。
- 真正出现多POV或复杂objectknowledge需求后再评估检索扩展；当前不放开firewall。
- 已完成章节Reopen属于后续独立权限/版本设计。

没有Long-rangePlanning、VectorRetrieval、KnowledgeGraph或新框架。

## 28. Known Limitations

- 真实模型/人工E2E未执行，Recorded输出是测试oracle，不代表模型语义理解、文学质量或真实Fidelity判断。
- 第4章真实provider若未生成Z，必须记录污染场景未构成，不能伪造v1/DB数据来标PASS。当前未验证另一种真实污染场景构造方式；不得绕过重大改变的Authority边界来制造通过结果。
- 自动Colima端口转发仍失败；NativeBackend8000、Frontend5173和测试DB可用，本轮不重启Colima或影响用户服务。
- 本机开发库/Backend已升级0017/本次代码并通过独立复核；自动Worker停止，人工测试仍须按README显式opt-in和逐阶段批准，不能把部署完成当作真实模型验收完成。
- 全局Worker没有project限定claim。Runner检查当前全局队列与同DB任务，再调用既有--once；`--worker-stopped`是操作者确认。人工期间不得并发提交其他任务/启动另一个Worker；不为eval新增queue架构。
- 现有生命周期没有REJECTED状态，已覆盖未接受/被后继替代Draft，不声称实现新状态。
- downgrade有对象/Thread转换历史时拒绝，保护不可变已确认数据；round-trip在无此历史的隔离schema验证。
- Test UUID随临时schema清理，trace是留存证据，人工项目须由Runner单独创建。

## 29. Acceptance Matrix

| Capability | Chapter | Expected | Actual | Engineering | Real/Human |
|---|---|---|---|---|---|
| Canon continuity | 1→5 | X不漂移；真相不取自怀疑 | Canon与知识分离 | PASS | NOT RUN |
| State transition | 2/3 | A L2/K DESTROYED，保留旧值 | v2/supersedes/current/history | PASS | NOT RUN |
| Knowledge firewall | 2/5 | B不知X，正确owner正向可见 | 完整B CP无X；双owner测试 | PASS | NOT RUN |
| Belief vs truth | 2/3 | suspicion历史保留，读到真相后当前更新 | SUSPECTS v1→KNOWS v2 | PASS | NOT RUN |
| Open Thread | 1→4→5 | omission仍OPEN，新证据同identity | T v2，same logical_id | PASS | NOT RUN |
| Revision pollution | 4 | v1Z删除，Memory只读finalv2 | 正式A06/Fidelity，exactv2 | PASS | NOT RUN |
| Current retrieval | 5 | 当前事实进入相关Context | Planning + exactapprovedPlanhandoff | PASS | NOT RUN |
| Duplicate/conflict/lock | negative | skip/block，无silentoverwrite | 正式API/DB负向PASS | PASS | NOT RUN |
| Freshness/atomicity | negative | stale/partialcommit不得Completed | 409/rollback/guards | PASS | NOT RUN |
| Signal/noise/Writer use | 1～5 | 自然高信号，不展示全部记忆 | 仅fixture可验证 | Fixture only | NOT RUN |

26项节点映射在coverage.json；1～18长期Memory/版本/authority，19～26正式Context/future/isolation。独立review按17项完成：正式Workflow、无DB捷径、exactversion、污染、firewall、truth、state、thread、duplicate、conflict、authority、overload、required、future、derived、noise、无Phase2。

## 30. Final Acceptance Result

**E2E-001 = FAIL（完整真实产品验收尚未完成）。**

工程五章组合与前置修复已达到 **PASS_WITH_BLOCKERS_RESOLVED**，不再停在012 prerequisite；本轮没有已知未关闭的产品 correctness blocker。剩余是用户显式启动真实模型、逐章批准Plan、接受Draft、确认Memory，并填写人工continuity记录和trace后才能给完整产品PASS。

人工入口：`evals/e2e/multi-chapter/README.md`。Runner不自动跑五章，export只读，严格保留三Gate。测试和eval代码本轮未提交。完成当前工程准备后停止，不开始NOVEL-013/Phase2。

## 31. Prerequisite Audit / Fix History

初次Audit发现BP-01/BP-02后按Ticket要求停止。当用户授权修复后，新增27项Unit Contract与9项formalMemoryAPI回归，原完整pytest1482PASS/4付费opt-inSKIP/0FAIL。独立审查补齐正式StageMapping；0017保护已有历史的downgrade。

本报告第1～30节是恢复E2E后的最新验收。初次Audit并未运行五章；后续Memory局部测试也没有冒充五章。本轮正式五章RecordedRuntime组合补齐工程证据，完整真实/人工证据仍未产生。初次报告备份保留在忽略的 `.runtime/e2e001-prerequisite-report.md`，未删除用户数据。

## 32. Local Update and Verification

2026-10-05，按用户“更新然后验证一下”部署当前工作树。没有切换到缺少012的旧main，没有提交、推送或调用真实Provider；配置继续只读取TOML。

- 先停止旧Docker Worker；更新前没有待领取/正在执行的模型任务。
- 备份开发库到忽略的 `.runtime/e2e001-local-update/development-before-0017.dump`（2,056,813 bytes），`pg_restore --list`确认归档可读。
- 开发库正式从0016升级0017；38张现有表的行数全部保持不变。实际 `novel_memory_relations` 函数包含OBJECT/OPEN_THREAD新状态约束，旧Character约束保留；`alembic check`无drift。没有对用户开发库做downgrade。
- Native Backend PID46236、Vite PID46240均已重启。8000和5173代理的health/db/config共6个请求全部200；Workspace实际加载、章节及Draft v1/v2/v3可见，浏览器error日志为空。404/422统一错误和request ID也通过。
- 对3个已有Project、11个Chapter及writing-profile（current state）/approved/versions、Memory current/history做只读API smoke。已有2个Approved Profile保留，没有重设用户偏好。
- Docker backend/worker镜像已更新，两个容器已重建且未启动，日常页面继续使用Native Backend。无网络的镜像检查确认0017已打包、latest Memory Schema v2、历史v1兼容、Prompt v3及hash有效。
- Worker保持停止，更新期间AgentRun数量不变，真实模型调用0次。Colima自动端口转发未在本次修复；Native API和现有55432/55433数据库连接正常。

本次受影响回归覆盖135个唯一用例：五章正式链路、Memory current/history/transition、知识隔离、Authority、冲突、并发、事务、schema和manual runner均PASS。首个组合命令得到130 PASS/5 fixture setup ERROR；5个runner用例单独运行得到5 PASS（7.11秒），无产品断言失败。诊断确认当前pytest 9.1.1混合路径收集产生两个同nodeid的Directory对象，fixture按对象身份匹配失败。README已拆成两条pytest命令，保留全部135项覆盖，不修改产品代码、fixture或依赖版本。原始错误和最终通过日志都保留，没有抹去首次错误。

前端149 PASS（11 files），lint/typecheck/build全部PASS。Backend398文件及Runner1文件Ruff check/format、git diff --check全部PASS。隔离测试schema的upgrade → downgrade -1 → upgrade / check全部PASS并清理；上轮全量1491 PASS/4付费opt-in SKIP/0 FAIL证据保留，本次无产品源码变更，未重复整套全量。

浏览器显示的第8章旧C14 Memory失败也已只读定位：Run结束于2026-09-30 09:20 UTC，使用历史Prompt v1；模型在第82段evidence末尾凭空补闭引号，违反连续原文引用规则，归为SCHEMA_PARSE_ERROR。当前Schema/source/boundary校验均通过，精确quote校验正确拒绝该历史输出。当前Prompt v2/v3已明确禁止补引号，但未实际调用模型验证新输出，也没有自动重试/改旧记录或放宽validator。

独立部署复核PASS。证据保存在根 `.runtime/e2e001-local-update/`（deployment-evidence、independent-live-verification、existing-project-api-smoke、historical-memory-failure、final-smoke及前端日志）和 `backend/.runtime/e2e001-local-update/`（focused-regression、manual-runner-isolated、migration-isolated、Ruff和collection诊断日志）。

**本机更新与工程验证 = PASS。** 完整E2E-001产品结果仍为第30节的FAIL（真实模型五章及人工验收未执行），不能以本次部署成功替代AI Behavior Acceptance或Human Prose Evaluation。

## Real Provider Acceptance

本节追加真实验收证据；前面的Recorded/工程证据原样保留。当前为逐Gate进行中的快照，不能以一个模型调用或工程测试替代五章真实产品验收。

### 1. Real Environment

2026-10-05：Native API8000 / Workspace5173，持久开发库head0017_memory_state_transitions。Provider为Lingzhi，Model为gpt-5.6-sol，Profile为lingzhi-structured；credentials已配置，只通过backend/config.toml读取，未写入报告。Raw capture开启。Polling Worker停止，每次使用现有manual runner及标准Worker --once，max_attempts=1；执行前检查全局queue和API/Worker同DB、Project/Workflow/Task身份。

用户E2E-001R指令已授权必要真实调用。用户另明确批准“原场景Profile v1，继续到第1章Plan Gate”，这不批准Plan、Draft或Memory。expected-memory/context/coverage只用于事后对照；独立审查确认runner没有将其送给Agent。

### 2. Real Project

Project：8684fb34-3600-44d8-9ed4-ef7e55fce36d，名称E2E-001R Real Provider & Human Acceptance；run marker a86d3747-3ea4-437f-b598-ddb7520666e1。使用原evals/e2e/multi-chapter/scenario.json，没有新增第二套场景。fixture SHA256 e7ac350f792ab51860939b79a14e5e6d070831981bacf679b85033e52704b8d0。

原场景Writing Profile v1已经真实用户批准，record cd553d3f-26fd-40ef-89f8-001e0e12bdd3，hash ff4d7dd00fac8a18b7c4b0c04db30abad5db6042be86922f3f77a30119936e31。其余3个用户Project保存只读baseline，未在本轮执行任务。

### 3. Chapter 01

Chapter 09a771da-113a-4603-9545-e74ab4671722“独享的暗号”；Workflow209f1ac7-c6cb-4a00-b26d-413408f87dff。

原文：Lin Lan 在 River Station 亲眼读到 Midnight Code：the box opens at midnight。Gu Che 不在现场、没有听说这条信息。Sealed Copper Box 完好。Missing Courier 尚未找到。两人合作调查，但不要扩写世界观。

A02真实attempt01：Run6423060e-96e7-4069-b75f-ad62c00eb4c5，Task2e8b89ae-7c58-425a-a2ad-80dcfcf94125；耗时约31.8秒，input6180/output3201/total9381tokens。Provider正常返回；schema与task authority校验通过，但来源quote校验拒绝模型把内部TASK_INPUT.constraints中的“Planning only; no chapter prose”加入用户FORBIDDEN。结果AUTHORITY_DENIED/C90_BLOCKED；CreativeBrief、Plan、Draft、Memory均未写入。历史失败保留，不认作Provider或用户权限失败。

ContextPackage79af85b1-e79e-42ca-93e8-c6c986f01692；PromptLineage0f2a2f20-294e-4cba-948f-5d078cea91f4；task-template v2；compiled hash 3ce26496ef94070d24347df9a0961a92576a84f3581b30d44d18bd05070de83f；schema hash 7adc291e7db586c97c0f8e89673794d687642fe5ff6f8055786d30ecd61c9bb5。

A02同原文正式重试成功：Task133d80dd-44b8-41e8-97ee-80eb5c158eba，Rune88855dd-4ade-4b27-8482-47d33089b78a，约113.8秒；input10705/output2117/total12822tokens。新CreativeBrief d0af7124-2ed5-40d7-9def-4c811f7479c4 v1 READY；CP776015d1-61b7-4001-be89-de2c5b21f36c；Lineagecae1e404-063d-45e3-b9b3-8bd513f3c76d精确绑定task-template v3与原schema v1。所有约束引用原始objective，内部规则未再出现。旧失败保留；状态正式推进C04/Planning iteration1。A03与A05已经成功；当前C06_PLAN_APPROVAL / WAITING_HUMAN，state_version9，Plan v1等待真实用户批准。Gate21826905-dcb2-4841-8e4a-36f2bc2130ca，artifact54935ff3-14ee-4aee-9549-275220c497fb，artifact_version1，decision=null。Chapter current_plan_version=1，approved_plan_version=null；正文current/approved均null。没有自动批准任何Plan。

轻微观察：Brief摘要使用“她”描述Lin Lan，原文未规定性别；没有写入Canon，记录为未经原文给定的低影响推断，后续Plan Gate向用户披露，不因此调整Writer/Prompt。

### 4. Chapter 02

NOT RUN。必须先完成Chapter01 Plan/Draft/Memory三个真实用户Gate和Commit。未来重点为B知识隔离、A suspicion不能成为Global Canon、A位置current/history切换。

### 5. Chapter 03

NOT RUN。未来重点为B不负责Y的truth、A的SUSPECTS历史到KNOWS当前、K INTACT到DESTROYED、T仍OPEN。

### 6. Chapter 04

NOT RUN。仅按原场景走正式Human Feedback/A06；如果真实Draft v1未生成False Fact Z，记录POLLUTION_SCENARIO_NOT_TRIGGERED/NOT TESTED，不注入Z或伪造Draft。

### 7. Chapter 05

NOT RUN。不把expected-state重新放进Requirement；事后语义检查Required/Forbidden/Private/Current/History/Authority，不做exact list equality。

### 8. A07 Memory Quality

NOT RUN。Candidate/Committed/Excluded/Duplicate/Conflict数量均未产生，不把零候选当GOOD。每章待用户逐项标Good/Missing/Wrong/Noise/Knowledge/Authority；严格保留exact evidence quote validator。

### 9. Planner Behavior

A03 iteration1真实成功，Task7b217de9-8f87-4b69-88c8-789aad4af205 / Run032ebfa0-6660-4f47-8185-c3868b64d482；约49.5秒。Plan version1记录54935ff3-14ee-4aee-9549-275220c497fb（planning artifact5a39a146-5aee-44e9-b5d6-3756dd7b246b）；Lineageeb604947-af8a-486d-9f36-a5db18764db3；CP1cde1507-e24e-413c-8379-323c240a7e75。

两场景：Lin Lan独自在River Station读到exact X，然后两人保持知识差合作调查；K完好/T未找到。6项coverage均covered=true；无proposed_major_changes，无Lock依赖。局部线索载体与调查分工位于Creative Freedom范围。A05真实Plan Review PASS：Task57094cbf-5ecd-44ab-a9a2-c32de506bd0b / Run53a8ad35-a657-49e8-9aa3-f64483217fd3，约65.9秒，input14852/output1089/total15941tokens。Reviewd6470b31-8880-4fdd-a51b-d10a8c689f9a精确绑定Plan v1；CPbe606565-e32f-4662-97a3-ffc69325f1b4；Lineage4f418d62-59e0-4893-a226-e136dde591df，task-template review-chapter-plan v4，schema v2。全部6项covered=true，missing_requirements/hard_gate_issues/violations/conflicts/over_specification/recommendations均为空，cross-field invariant无矛盾。只1次Planning，未触发迭代循环。

独立初审：Plan没有把X分配给Gu Che，也未提出重大设定；CP选中真实APPROVED Profile v1，exact record/hash/A5正确。本轮current=approved=1，不能把这次选择当作真实current/approved分离场景已经测完。机器pov_character_id=null，第一章尚无Memory subject，不宣称已建立后续B POV binding。角色性别“她”未在原文指定，线索载体/午夜压力为局部推演，均需用户在Plan Gate确认，未变成Canon。

### 10. Writer Behavior

NOT RUN。没有Plan Approval，所以没有Writing、Quality Review或Revision调用。

### 11. Knowledge Firewall

工程证据PASS；真实Chapter01 Plan明确Gu Che未获得X，人工独立审查未发现Plan知识泄漏。跨章Context/Planner/Writer验证NOT RUN；不能用首章Plan检查替代B POV Writer验收。A02数据中的X是本章原始用户要求，尚未进行Memory Commit。

### 12. Context Retrieval

两次A02 CP都只包含TASK_INPUT/CHAPTER/PROJECT三项；expected-memory/context未注入。A03实际CP-004 policy v6选中approved Profile v1与Brief v1；A05增加exact Plan v1。跨章Planning/Writer retrieval NOT RUN。失败后该CP显示STALE是workflow block后的状态变化，不是首次调用失败根因。

### 13. Human Prose Evaluation

NOT RUN。Profile批准不是Plan/Draft接受。backend/.runtime/e2e001r/human-evaluation/chapter-01.md至chapter-05.md保存原人工模板及Prose/Continuity/Memory/Knowledge/Notes字段，全部未填写，不代用户评分或接受正文。

### 14. Failures Found

DEBUG_EVIDENCE_WARNING：现有workflow/audit.py:41在TransitionAudit.after快照中硬覆盖simulation=True，即使真实Workflow为simulation=false。独立只读核对了7条transition audit：任务、实际Flow、Provider/Run均为正式真实路径。该元数据不能用来判断实际simulation；不改变本轮事实或Gate，不在真实验收中扩大修复范围。具体audit UUID与位置保留在backend/.runtime/e2e001r/independent-requirement-review.json。

R-01：Failure=A02执行规则混入用户创作约束；Layer=PROMPT_USE/INPUT_BOUNDARY；Root Cause=v2只要求读取objective，但未明确隔离constraints/capabilities/schema/workflow/Project metadata；Minimal Fix=仅新增task-template v3来源字段说明；Regression=内部规则quote拒绝，同文字实际出现在objective时允许。模型返回数据未经删改，现有严格source validator正确拦截。

Before证据：backend/.runtime/agent-output/2e8b89ae-7c58-425a-a2ad-80dcfcf94125-1.json，以及backend/.runtime/e2e001r/chapter01-requirement-attempt01.json。具体Prompt Fix Proposal先保存到backend/.runtime/e2e001r/proposals/R-01-requirement-input-boundary.md并向用户说明，再新增版本；没有默默调Prompt后覆盖失败。

### 15. Fixes Applied

只新增parse-chapter-requirement task-template v3，hash9d9608d83ea77d9f2620cdb6451af0021dd322886b7d482f42a33285cee5934d。历史v1/v2内容/manifest/hash未变；registry精确旧pin仍可解析，latest STABLE选择v3。Pydantic、Service/source validator、Writer/Quality/Memory、schema和架构未修改。不按Case01写特判，不把expected答案给模型。

通用source-boundary回归4 PASS，Ruff check/format PASS；允许相同文字确实来自用户原文，禁止因关键词误伤。Prompt/Compiler/Requirement回归54 PASS/1 paid opt-in SKIP；同原文正式新Task重试SUCCEEDED。首次命令路径错误(exit4)及更正后53PASS/1旧latest-version断言FAIL/1SKIP日志保留；只更新本地测试的task-template latest为3，角色/skill仍2，新增历史旧pin检查，最终全部通过。没有提交测试。修复按本轮Bug Fix/Prompt Tuning Policy进行，不额外批准任何用户Gate。

### 16. Engineering vs Real Matrix

| Capability | Engineering | Real Context | Real Agent/Human |
|---|---|---|---|
| Requirement evidence boundary | 4 generic regressions PASS | original input retained | attempt01 FAIL / same-input retry PASS; Chapter01 Plan/Review PASS |
| Knowledge Firewall | PASS | multi-chapter NOT RUN | Ch01 Plan preserves X boundary; cross-chapter Planner/Writer NOT RUN |
| Canon/State/Thread continuity | PASS | NOT RUN | A07/Human NOT RUN |
| Revision pollution isolation | PASS | NOT RUN | NOT RUN |
| Finalized source/atomicity/authority | PASS | NOT RUN | NOT RUN |

### 17. Real Acceptance Matrix

| Capability | Expected | Actual | Result | Failure Layer | Evidence |
|---|---|---|---|---|---|
| Requirement source isolation | Only user objective is task evidence | execution rule added to FORBIDDEN, correctly rejected | attempt01 FAIL; corrected retry PASS | PROMPT_USE/INPUT_BOUNDARY | R-01 raw/CP/Lineage |
| Canon Continuity | X stable | no committed memory | NOT RUN | — | pending |
| State Transition | one CURRENT plus historical | no committed memory | NOT RUN | — | pending |
| Knowledge Firewall | A-only X excluded from B knowledge | no B Planning/Writer | NOT RUN | — | pending |
| Belief vs Truth | suspicion not Canon | Chapter02 not started | NOT RUN | — | pending |
| Open Thread | T same identity/current | no committed thread | NOT RUN | — | pending |
| Revision Pollution | rejected Z absent from finalized source | Chapter04 not started | NOT RUN | — | pending |
| Memory Signal/Noise | human evaluation of actual proposals | A07 not run | NOT RUN | — | pending |
| Context Retrieval | current relevant facts, private exclusion | cross-chapter not run | NOT RUN | — | pending |
| Writer Use | natural, no knowledge drift | Writing not run | NOT RUN | — | pending |
| Planner Use | no invented directions/knowledge | Ch01 Plan v1 / Review PASS; 1 iteration, no major proposal | PASS for Ch01 only | — | real A03/A05/CP/Lineage |

### 18. Final Product Acceptance

本次到Plan Gate共4次真实Provider尝试：A02失败1次、修复后A02成功1次、A03成功1次、A05 Plan Review成功1次。全部Lingzhi/gpt-5.6-sol，未使用Recorded/Mock；total tokens53060（input44742/output8318），不推算价格。所有失败/成功Raw Output、CP、Lineage分别保留，final export lineage_errors=[]。独立最终复核PASS，证据independent-plan-gate-review.json：Schema/Authority/cross-field/source绑定正确，exact Plan v1/Gate v1匹配；未注入expected/recorded，未批准Gate，0 Writing/Draft/Revision/Memory。R-01同原文单次成功是本场景的Before/After证据，不代表对所有未来模型输出的统计保证；严格validator继续拒绝非法输出。

最终检查：待执行Task=0，单次Worker均已退出、Polling Worker停止；health/db均200；其他3个Project版本不变且本轮无新Audit。Plan Human Gate WAITING/no decision；没有Draft/Memory或它们的审批。Workspace已选中独立E2E Project/Chapter01，截图backend/.runtime/e2e001r/chapter01-plan-gate.png保留。完整trace为chapter01-plan-gate.json，final-plan-gate-check.json保存隔离/queue/health核对。用户下一步实际在Workspace检查“方案v1”，自行点击“批准并开始写作”，然后再授权/告知继续单次Writing到Draft Gate。

Engineering Acceptance仍为PASS_WITH_BLOCKERS_RESOLVED；Real AI Behavior尚在逐Gate验证。**E2E-001R目前=FAIL（真实五章和人工Gate未完整完成；这是中途快照，不是已完成验收）。** Chapter01来源边界R-01按本节保存Before/Proposal/新版本；同原文正式重试已通过，第1章Plan Gate已经到达，等待真实用户审批Plan v1。没有开始Writing/Chapter Review/Memory；没有开始第2章。

Phase2 Candidates：目前没有由真实五章证据支持的候选。R-01属于当前Phase1输入边界修复，不新增Phase2框架；不开始NOVEL-013。
