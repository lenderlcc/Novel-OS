# NOVEL-010A — Revision Fidelity / Locality Fix

日期：2026-09-28。分支：`wfg/novel-010a-revision-fidelity`，基于 main `8199173`。

本报告区分工程验证、真实模型行为和人工文字评价。**NOVEL-010A = CONDITIONAL PASS**：工程验证完成，未留未解决测试失败；真实 Case 05 因缺少与指定原稿绑定的原 Review 而阻塞，不以其他故事或 Mock 结果代替。全量测试与修复复测分别记录于第 19 节。

## 1. Background

010 已提供 Review → RevisionPlan → Revised Draft → Re-Review。本补丁只约束修改的忠诚度、必要范围及原稿保留，不增加创作能力、重做 Writer 或进入 NOVEL-011。

保留 API → Service → Repository → Database，Domain 不依赖 FastAPI/ORM，事务由既有 application service 管理，Repository 不 commit。无新增依赖。保留本次开始前已有的“查看 AI 审阅”链接及本地测试等未提交修改。

## 2. Case 05 Failure

用户报告的失败是：两张车票、愿意同行的人、真实动摇与签字动作，被替换成文件和方案比较；Requirement 仍满足，但原场景装置及关系功能丢失。这是 `REGENERATION_DISGUISED_AS_REVISION`。

这段失败描述来自本次 Ticket。本机找到了符合描述的原稿，但未找到它对应的正式 Review 或历史 Revision artifact，因此无法独立重放旧失败。没有把用户描述冒充本次模型运行结果。

## 3. Root Cause

检查旧 A06 Prompt → typed output → validator → persistence 后确认三个工程缺口：

- v1 Prompt 已提到 retain/local repair，并非完全缺少相关要求；但 Plan 只有泛化的 KEEP/DO_NOT_CHANGE ID，没有具体场景证据、关系功能、修改区域、预算及扩大全章范围的依据。
- 原 Validator 验证 ID、Authority、版本和 declared changes，不能证明正文确实保留了 ID 对应的故事功能。A06 的“已保留/已解决”声明可能通过这些结构检查。
- A06 结果会立即创建 current ChapterVersion，随后才正式重审；没有在更新 current 前独立检查 Fidelity，也没有供拒绝结果停留的 immutable candidate。

因此修复同时落在 Plan/Prompt、独立语义检查和持久化门禁，不靠相似度阈值或 Case 05 特判。

## 4. Revision Fidelity Principles

正式加入 SOURCE FIDELITY、MINIMUM NECESSARY CHANGE、STORY DEVICE PRESERVATION。Source Draft 是完整、确切的 `EDIT_BASE`。没有 Review/Authority 要求变更的材料默认保留，显式 KEEP 列表不是唯一保护来源。

允许必要的整段对白、节奏、动作、连接句和代词修改；不要求全文字面一致。Authority 回答能否修改，Fidelity 进一步检查这次修改是否必要。

## 5. RevisionPlan Changes

新增 `FidelityRevisionPlan`，输出 schema v2，兼容读取历史 v1：

| 字段 | 约束 |
| --- | --- |
| preserve_scene_elements | 非空；唯一 element_id、描述及原稿短引文证据 |
| preserve_relationship_elements | 关系功能及证据；无关系时可空 |
| preserve_effective_details | 非空；有效动作/意象/细节及证据 |
| strength_preservation | 完整覆盖原 Review 每个 strength；DIRECT/FUNCTIONAL |
| strength_regression_risks | 引用已有 strength，包含 risk/mitigation |
| revision_zones | 精确覆盖 actionable issue IDs；semantic_range，可选成对段落范围 |
| allowed_structural_change | NONE / LOCAL / CHAPTER_WIDE；默认 LOCAL |
| change_budget | MINIMAL / MODERATE / BROAD；默认 MINIMAL |
| structural_authorization | 扩大全章范围时必填；绑定实际 Review Issue 根因 |

原 target、blocked、KEEP、DO_NOT_CHANGE、source refs 与 Authority 校验继续有效。Schema 拒绝重复/保留 ID、越界段落、遗漏 target、无依据的 BROAD/FULL_PASS。

## 6. Preserve Scene Elements

Planner 提取位置、关键物件、互动前提、重要动作和事件机制，并提供 exact source paragraph evidence。执行 Prompt 消费这些结构；Fidelity 对每个 element 单独返回检查和新旧证据。

此外始终检查 `SCENE_PREMISE` 和 `UNAFFECTED_MATERIAL`，避免 Planner 漏列某个物件时该物件便失去保护。正式 Prompt 无车票、确认单等 Case 05 专属答案。

## 7. Preserve Relationship Elements

Plan 明确关系承担的吸引力、压力、同行或选择功能。A05 独立检查 `RELATIONSHIP_FUNCTION`，不能仅因替代稿满足主题/结局就认可把人与人的作用降级成抽象选项比较。

证据验证只证明引用确实存在；关系功能是否相同由语义任务及人工评价判断，不能宣称已由 Python 确定性识别。

## 8. Revision Zones

每个可处理问题必须被 zone 覆盖，阻塞问题不生成 zone。可用语义区域或 1-based、按空行分段的 paragraph_start/end，禁止反向及越界范围。

Zone 外隐式保留，允许为衔接做少量邻接调整；不用字符 offset、patch engine 或百分比限制。A05 检查实际必要范围，不能由 Planner 随便声明“全章”获得授权。

## 9. Change Budget

默认 MINIMAL；多个相关局部修复可 MODERATE。BROAD 必须伴随 CHAPTER_WIDE 及有效结构变更依据。没有编辑距离、字符重合率、段落比例或机械“最多改多少”门禁。

## 10. Structural Change Rules

CHAPTER_WIDE 要求实际 target issue、原 Review description 的精确引用、reason、why_local_insufficient。FULL_PASS/BROAD 不能在 LOCAL/NONE 下使用。

确定性检查保证依据来源及字段存在；A05 再判断该根因是否真的需要全章修改。仅填写一段理由不等于授权。全章 POV 调整可以合法通过，仍须保留原故事。

## 11. Prompt Changes

新增版本，历史模块未原地修改：

| 模块 | 新版本 |
| --- | --- |
| task_template / plan-chapter-revision | v2 |
| task_template / revise-chapter | v2 |
| skill / targeted-revision | v2 |
| agent_role / revision-fidelity-reviewer | v1（仍属于 A05_REVIEW） |
| task_template / validate-revision-fidelity | v1 |
| skill / revision-fidelity | v1 |
| quality_profile / fidelity-quality | v1 |

要求 Edit the existing draft、完整 EDIT_BASE、隐式保护非修改范围、禁止替换场景来更容易满足 Review。完整正文输出只是存储格式。每阶段继续保存 PromptLineage、ContextPackage、AgentTask/Run 和 ModelProfile provenance。

009 原有 detector、QualityIssueCode、Character/Audience 判断及正式 Review Prompt 未修改。新的 Fidelity codes 只属于 Revision Validation。

## 12. Context Changes

当前工程中 CP-006 属于 Quality Review，Revision 已使用 CP-007；因此新增 **CP-007 v4**，不占用 CP-006，也不改历史 profile。

完整 exact source `target-version`、Review、Brief、approved Plan/Profile、preservation contract 为 P0。`revision-contract.edit_base.role=EDIT_BASE` 明确编辑角色，避免重构 Context item schema。执行阶段携带 exact Plan，Fidelity 阶段额外携带完整 immutable candidate。

继续使用原 source binding/freshness 校验，不能换 latest，Draft Plan/Profile 不污染批准输入。Source 变化会拒绝迟到结果。未引入新 Memory Domain、Vector RAG 或上下文检索架构。

## 13. Fidelity Validation

`RevisionFidelityValidator` 组合确定性结构验证与 A05 `VALIDATE_REVISION_FIDELITY`：

1. 原稿/Review/Plan/candidate ID、candidate hash、Context 实际内容完全绑定。
2. Plan 完整保护所有 Review strengths；原稿证据、段落及结构授权有效。
3. A05 必须逐项检查全部保留元素/strengths，并覆盖 SCENE_PREMISE、RELATIONSHIP_FUNCTION、UNAFFECTED_MATERIAL、STRUCTURAL_SCOPE。
4. 每项包含原因和 exact 新旧证据；PASS 必须有 revised evidence。verdict、failed checks、violations 必须一致，禁止自相矛盾。
5. `REVISION_SCOPE_VIOLATION`、`REVISION_STRENGTH_REGRESSION`、`UNAUTHORIZED_SCENE_REPLACEMENT` 独立于 009 taxonomy。

保留现有置信度及 escalation 门禁。语义模型的误判不能由引文校验完全消除，真实模型与人工比较仍是验收要求。

## 14. Failure Handling

新增 migration `0013_revision_fidelity` 和 immutable `revision_candidates`。顺序为：

```text
A06 Plan → A06 candidate（不创建 ChapterVersion）
  → A05 Fidelity
      FAIL → 保存 rejected result + candidate + lineage → BLOCK / STOP
      PASS → 新 immutable Draft / current → 原 A05 Quality Review → 等待人工
```

失败 result 的 chapter_version_id 为 null、accepted=false，source/current/approved 均不因失败修改。失败后不能 RESUME 自动再调 A06；技术失败仍沿用原有有界恢复机制。成功只改变 current，approved 分离保持。

候选、结果、版本、事件/Audit 同既有事务边界；DB trigger 验证 candidate/source/hash、A06/A05 task ownership、active workflow、lineage 及 successor，拒绝把 FAIL 关联到新 Draft。候选 UPDATE/DELETE 被 DB 阻止。

正常 UI 显示“这次修改范围过大，未替换当前正文。”；可展开“查看未采用的修改稿”，与 current 正文分开。成功体验仍是新 Draft + 重审。Debug 展示 KEEP/CHANGE/DO_NOT_CHANGE、zones、预算、授权、strengths、violations 和证据。前端发起修改前同时校验新增 task 的执行权限。

旧未完成的 010 RevisionRequest 缺少 fidelity contract 时 fail closed（CONTEXT_STALE），避免按新链路错误继续；历史 artifact 保持可读，需用户基于有效 Review 显式创建新请求。

## 15. Strength Regression

所有 Review strengths 必须逐项映射 DIRECT/FUNCTIONAL，并在语义结果中逐项检查。风险声明包含 mitigation，例如删解释后以动作保留犹豫。

strength 检查失败必须使用专用 `REVISION_STRENGTH_REGRESSION`，不能用 A06 的 preserved_items 声明消除它。严重功能丢失不会成为 current。

## 16. Unresolved Issue Handling

ABSTRACT_STAKES 优先使用 Source Draft → authorized Context → approved Plan/Brief → safe local elaboration。仍无支撑时保留 unresolved，说明 `Insufficient authorized context for stronger concretization.`，不得为清空问题而制造新故事事实。

addressed 仅是 A06 声明。允许安全局部修改与 unresolved 同时存在；没有 addressed 项也不自动等同于无效候选，但仍需实际修改并通过 Fidelity。成功后的正式 A05 重审决定质量问题是否解决，不继承旧 verdict，也不自动开启第二次 Revision。

## 17. Case 04 Regression

本地 fixture：`evals/revision/010a/case-04/`，源 Draft `86c02b4b-7117-4ee0-9528-77870b30fc08`，SHA-256 `4ed3c41579cd11b3dca885ceb521af32ab230141ec69bd261139a328c9fb6f49`。

测试使用同一搭棚原文，手工替换中段对称论证对白，保留院落/雨势/搭棚/纸箱、合作及未解决分歧，验证允许明显局部改写与其他段落稳定共存。

性质明确为 **OFFLINE_HAND_AUTHORED_REGRESSION**，语义 verdict 为注入的 Mock；它验证契约不强制字面相同，不证明真实 A06 已改善人物感或真实 A05 判断正确。未调用真实 Case 04 Provider。

## 18. Case 05 Before / After

数据库只读核对找到符合 Ticket 描述的原稿：

| 绑定 | 值 |
| --- | --- |
| Project | 23c028ee-cd94-4965-af85-731e560c9633 |
| Chapter | c0eed078-fdd9-48b5-b4c5-62e83f6d98ec（第 5 章，继续） |
| Source Draft | b31057fa-44df-44fd-acbc-11e6f8598940 / v1 |
| Source SHA-256 | 699cfb5b4d98d789bf5c45170bf71885c55bd3bb4c917db2f0ae49d0354c333f |
| 对应正式 Review | 未找到 |
| 本次 Revised Draft / Fidelity / Re-Review | 未运行 |

旧目录 `evals/revision/010/case-05/` 指向另一个 Draft `e3e88aaf-ae0b-48fe-a230-9893b79761cb` 和 Review `55bad299-a861-4a62-89db-f7003d310ea3`，内容不是“两张车票”原稿；旧报告也将真实验收记为 NOT_RUN。本机 RevisionRequest 为空，不能恢复 Ticket 描述的旧失败 artifact。

已保存新 manifest 与确切原稿至 `evals/revision/010a/case-05/`，状态 `BLOCKED_SOURCE_REVIEW_MISSING`。已向用户请求本次实测的原 Review/项目/导出路径。没有借用别篇 Review、新建 Case、修改当前正文或自行补造 Review。

因此目前只有“用户报告的 Before”和“已验证的工程机制”，没有可诚实填写的真实 After。人工模板见该目录 `evaluation.md`。

## 19. Test Results

| 检查 | 结果 |
| --- | --- |
| Backend full pytest | 1,240 passed / 6 failed / 4 skipped，1,369.95s；六处失败均为下述已修复历史快照测试 |
| 全量结束后的 `pytest --lf` 修复复测 | 6 passed / 121 deselected，8.71s；六处失败全部关闭 |
| 新增 Fidelity 用例 | 45 项，全部包含在全量通过集；覆盖新增 Case 04 离线回归 |
| Pure / Context / Config 回归 | 117 passed，包含 Case 04 |
| 技术耗尽后源变化恢复 | 2 passed |
| 历史迁移快照修复复测 | 7 passed / 55 deselected；仅选迁移/往返用例 |
| Ruff check / format check | PASS / PASS，324 files |
| Frontend npm test | PASS，99 tests / 7 files |
| Frontend lint / typecheck / build | PASS |
| Playwright Revision E2E | PASS，2 tests，成功与 Fidelity 拒绝两条链路 |
| git diff --check | PASS |
| Alembic upgrade → downgrade -1 → upgrade | PASS，0013 → 0012 → 0013 |
| Alembic check | PASS，No new upgrade operations detected |
| Docker build / startup | PASS，novel-os-010a-acceptance:latest |
| Docker /health 与 /health/db | 容器内均 HTTP 200；Colima VM 的发布端口 health/db 也通过 |

专项涵盖：范围与预算默认值、字段完整性、伪造根因、局部对白可改、场景/物件/关系/strength 失败映射、未授权 BROAD、合法全章修复、unresolved、版本/内容/hash 绑定、候选不可变、失败保留原稿、transaction rollback、重复投递、源变化、DB 拒绝 FAIL、迁移往返、成功一次重审并停止。语义案例使用注入的判定，不能替代真实模型分类准确率。

全量与专项测试复用隔离 PostgreSQL schema，未迁移开发数据库。测试及 eval 产物保留本地；本次没有提交或推送。

全量运行发现历史迁移快照测试仍用最新 ORM 读取降级后的旧 schema，导致查询当时尚不存在的 `revision_candidates`。仅调整六处测试的历史表过滤范围，保留原有数据保留、往返迁移和 Alembic check 断言；产品代码无需修改。覆盖这些历史迁移的专项复测为 7 passed，日志 `legacy-migration-retest.log`。

全量进程在启动时已加载旧测试，因此仍记录这六处失败。全量结束后再用 `pytest --lf -q --disable-warnings --tb=short` 验证实际失败集合：6 passed，没有未解决失败。结果应理解为“全量执行 + 六处测试修复复测”，**不宣称修复后又完成一次退出码为 0 的完整全量运行**。累计当前 1,250 项中，1,246 项已验证通过、4 项 live-model 测试未启用。四个 skip 是付费 Requirement、Planning、Writing 和 Provider smoke；两个 warning 为既有 TestClient 依赖的 deprecation。

原始工程日志保存在本地 `evals/revision/010a/engineering/`：`backend-full-pytest.log`、`backend-failed-retest.log`、`legacy-migration-retest.log`、`frontend-tests.log`、`frontend-{lint,typecheck,build}.log`、`browser-e2e.log`、`docker-{build,startup}.log`、`docker-health.json`、`docker-vm-health.json`、`migration.log`、`fidelity-tests.log`、`pure-tests.log`、`recovery-tests.log`、`ruff-{check,format}.log`、`git-diff-check.log`；成功与失败页面截图为 `revision-workspace.png`、`fidelity-rejected.png`。

验证后已移除本次专用容器 `novel-010a-acceptance` 和 schema `novel010a_docker_acceptance`，保留镜像及日志；开发库、原 worker 与前端进程未改动。成功/失败截图均已查看，分别显示 Draft v2 + Review v2，以及 Fidelity FAIL + current v1。

## 20. Real Provider Evaluation

**BLOCKED_SOURCE_REVIEW_MISSING，真实调用 0 次。** 配置中的真实 Provider 可用不等于拥有与本次指定输入相配的原 Review。付费 Case 05 复测须先定位正确 Review，不能以生成新 Review 冒充“同一输入重跑”。

| 验收项 | 当前状态 |
| --- | --- |
| Source Fidelity | NOT_RUN |
| Same Story Revision：YES / PARTIAL / NO | PENDING HUMAN |
| Improved：YES / PARTIAL / NO | PENDING HUMAN |
| Strength Lost：YES / NO | PENDING HUMAN |

输入补齐后按一次 Plan → A06 Candidate → A05 Fidelity →（仅 PASS）Draft v2 → 原 A05 重审执行，FAIL 停止，不能自动再修一轮。

## 21. Known Limitations

- 确定性检查验证结构、引用和 lineage；语义 Fidelity 依赖 A05 的判断，Mock PASS 不代表真实语义准确。
- 保留项由 Planner 提取，可能遗漏；四个全局检查要求 A05 独立阅读完整原稿，仍需人工抽查。
- Case 04 目前仅离线允许局部修改回归；Case 05 缺原 Review，真实 After 与人工评价未完成。
- 新增一次 A05 语义调用，增加成功 Revision 的延迟/费用；失败后停止以避免循环消费。
- Colima 的 macOS 宿主机 8001 端口未转发成功。Docker 容器内和 VM 内健康端点通过；浏览器验证使用独立 native Mock API，不将其宣称为宿主机 Docker 转发通过。
- 当前开发数据库/既有 worker 仍使用已运行的旧版本。本分支只在隔离测试服务验收，未部署到真实写作流程。
- migration downgrade 删除新增 candidate 表，已有 ChapterVersion/Review 不改写；升级后的新请求不能在旧代码下继续处理，应在实际回滚前处理活动任务。

## 22. Acceptance Result

**NOVEL-010A = CONDITIONAL PASS**。

| 验收层 | 结论 |
| --- | --- |
| Engineering Acceptance | PASS：全量运行及失败修复复测、前端/E2E、lint/build、迁移与容器内部健康检查完成；宿主机 Docker 端口转发限制见第 21 节 |
| AI Behavior Acceptance | BLOCKED：指定 Case 05 的原 Review 缺失，真实链路未运行 |
| Human Prose Evaluation | PENDING：没有真实 After，不能评价是否仍为同一故事、是否改善或损失 strengths |

已按 Ticket 的 Independent Review 要求完成独立只读审查与复核：未发现未关闭的 Blocking / Required / Critical；审查者特别指出真实模型语义能力、Case 04 人工效果及 Case 05 缺输入不应由 Mock 结果替代。009 检测/Prompt/分类未修改，未实现 011。

收尾复核另确认六处历史快照修正合理，旧表逐行比较、迁移往返及 Alembic check 未削弱；报告没有将 Mock 或缺失的真实验收写成成功。

解除真实验收阻塞所需：提供与上述 Case 05 Source Draft 精确绑定的原 Review 或实际验收数据路径；随后完成一次有界真实调用并填写人工结果。在此之前，不声称 Case 05 已修好，不继续 NOVEL-011。
