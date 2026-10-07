# Phase 2 Contract Freeze — CHECKPOINT-001

2026-10-07。冻结对象是已实现的 001～014 工程边界；工程 PASS 不等于创意、人物自然度或连续章质量已通过真实人工验收。

Frozen means **change only with a correctness bug, real acceptance evidence, or an explicit architecture decision**。它不是永远不可修改。变更应记录触发证据、影响、兼容性和相应回归；没有真实证据时不做猜测性重构。

## Frozen contracts

| Contract | 固定边界与代码来源 |
| --- | --- |
| Authority | A0 System Rule → A1 User Locked → A2 User Approved → A3 Canon → A4 Approved Plan → A5 User Preference → A6 Derived Memory → A7 AI Inference；不新增级别。`backend/novel_os/domain/enums.py` |
| Agent roster | 仅 A01 Orchestrator、A02 Requirement、A03 Planning、A04 Writing、A05 Review、A06 Revision、A07 Memory。Explore 归 A03，Profile/Feedback 解释归 A02，Fidelity 归 A05。Agent 不具备 approve/lock/commit/direct DB write。`domain/agents.py`、`agents/registry.py` |
| Chapter workflow | 复用现有 versioned Chapter workflow；v1/v2/v3 保留历史语义，v4 在 C04 内先 Explore 后 Plan，不新增状态或新的审批 channel。旧 definition/hash 不覆盖。`workflow/definitions/` |
| Core versions | Approved 数据不原地改；正文 append-only；current 与 approved 分离；审批 exact expected_version；Project/Chapter/User locks 每次 mutation 重查；Service 控制事务，Repository flush-only。 |
| Memory layers | CanonFact / CharacterState / CharacterKnowledge / RelationshipState / OpenThread / DerivedChapterSummary 六类；静态 identity、动态 state、知识与 behavior tendency 独立。`domain/memory.py`、`memory/schemas.py` |
| Memory commit | 人工绑定 exact current Draft → accepted source → A07 proposal → 人工显式选中（或显式确认空集）→ 单事务 batch/identity/entries/completed/audit。Proposal ≠ CommittedMemory；不使用 rejected/superseded Draft、探索候选或 Profile 作为新事实证据。`services/memory_commit.py`、`memory_workflow.py` |
| Knowledge firewall | Global Canon ≠ Character Knowledge。owner、epistemic、KNOWS fact link、before_sequence、task allowlist 共同限制输入。Profile 不增加任何知识授权；倾向不得压过 Lock/Canon/State/Knowledge/ApprovedPlan。`context/policies.py`、`services/canon_context.py` |
| CreativeExploration | A7，现有 count/mode/selection/unsafe candidate 规则保持。只有 exact selected concept 交给 A03 Plan；所有候选保留为诊断证据，不进入 Writer/Memory。人工批准的是正式 Plan。`agents/exploration_schemas.py`、`services/exploration_context.py` |
| CharacterBehaviorProfile | sparse tendency，Draft A7 / user-approved A3；immutable body、logical_id/version/hash、独立 current/approved，counterpart 同项目。仅任务相关 approved profiles 与相关 pair modifiers 入 Context；可缺省，非固定行为脚本。`characters/schemas.py`、`domain/character_profile.py` |
| Revision | exact Draft/Review/feedback/source binding；A06 仅 prose/local elaboration；mutation arrays 空、超出范围用 unresolved/blocked；candidate 必须通过独立 Fidelity 才产生正式下一 Draft；保留旧 Draft，下一 Review 绑定新 Draft。`revision/schemas.py`、`services/revision_results.py` |
| Human Feedback | 单次反馈绑定 exact source Draft；A02 解释→既有定向 Revision 或澄清/replan/profile-change gate；不自动更新持久 WritingProfile/CharacterProfile/Canon。`feedback/schemas.py`、`services/feedback_results.py` |
| Prompt and Context | Pydantic 是唯一 output schema source of truth；Prompt 放方法与规则，故事/人物/知识放 Context；Provider request、parser、semantic validator 使用同一契约。Prompt/Context/ModelProfile exact pins/hash 保存到 actual AgentRun，旧版本不覆盖。 |
| Freshness | Task schedule/pre-IO/result completion 检查 approved Profile/WritingProfile 与 authority/version/scope fingerprints，包括空 selector；新增 Draft 不改变批准输入。新任务可使用创建前已批准的新版本，不强迫旧 Plan 永久重规划。 |
| Acceptance | 新 Phase 2 真实模型运行只经现有 runner 的显式 `--allow-real-provider`，标准 Worker 单步执行；prepare/status/export 不调用模型；Plan、Profile、Draft finalization、Memory confirmation 都是独立真实人工操作。不得自动跑完五章或替人批准。 |

## ADR CHECKPOINT-001-01 — standalone A02 report 的真实 lineage

问题：014 的同步人物描述解释有真实 Provider/Prompt/Context，但旧实现只保存 Profile source_text，未保存 AgentRun。CHECKPOINT §19 要求持久追溯，因此属于明确 Contract Alignment，不能标为普通 Known Limitation。

决定：扩展**现有** AgentTask scope，仅 `INTERPRET_CHARACTER_PROFILE` / A02 / REPORT_RESULT / max_attempts=1 可以是 standalone Project/Character report。该 scope 没有 Chapter 或 Workflow，使用 `report_character_id`；正式章节任务的原 FK/版本/租约边界保留。Migration `0020_character_report_lineage` 以 strict scope CHECK 与同 Project Character FK 保证区别。`memory_subjects(id, project_id)` 的冗余唯一键只服务于此 FK，不改变 Memory 数据或语义。

复用原 Runtime、Compiler、Provider、parser、Task/Run、ContextPackage 与 PromptLineage repositories。Provider IO 前固化真实 attempt 与 exact配置，IO 后再次检查权限/版本；Profile Draft、成功 Run/Task 和 Audit 原子完成。失败/stale 尝试仍留真实 trace，不批准 Profile、不推进章节。后台 Worker 排除 standalone reports，避免自动付费重试。内部 smoke demo 保持独立无持久化、非产品执行任务。

不新增 Agent、Workflow、Report 表族、Memory 层、执行框架或 Profile payload/schema/hash。`proposed_changes`/`memory_proposals` 仍必须空。存在报告执行证据时 downgrade 应明确阻止并要求先导出；不能为了恢复旧 schema 删除证据。

## Baseline schema fingerprints

以下由初始只读审计直接生成，checkpoint 后复核相同，不依赖报告口述。hash 是 canonical Pydantic JSON Schema 的 SHA-256。

| Schema | SHA-256 |
| --- | --- |
| MemoryCandidate | `df32cc195d9ee0d1c2567709e34b7b3060cfe12b1371f613824ec923f89981c6` |
| MemoryExtractionOutput | `e0744f3dad4e5da7dd5405d8c339186bd35249ac2d8d2bf9e7355737ead8813c` |
| MemoryAgentResult | `b1001ee06f434664d90c0fb480d1b68e385ca00e4ef38280b337d6f0503d6092` |
| StoryConceptCandidate | `e703739903c04dc8f35e0bbcdb90eeffb821a2c3f0d2cb58b627c797216df822` |
| CreativeExplorationOutput | `5bbdbedabebded35defcb562f5434d49ea17d2a9a34fc95f2d2f842c26a4dfbb` |
| ExplorationAgentResult | `f66c12e5d3dd6c4c682832a6dd1ef30135e26f8f587e76b000f127264baad7f5` |
| CharacterBehaviorProfileBody | `3c5b855e89880722941a2107c63b3248b8647d41361fb88478a06c8fa9341367` |
| RelationshipModifier | `c8e4ea3873c1d21a5558b9e6c8eea0ecbfec60047c81e9fbf6617a36f8ca9308` |
| CharacterProfileAgentResult | `f343bfc7b95223c517c8196ed35681582ca309c05b4f6710144bd2e4942da613` |
| MemoryRequest | `1c20c5c9aac36389b3ec8c93e3effaba6430b4469a4f56895cf50d37b49b91eb` |
| MemoryCommitBatch | `50c8c9486faedafd732a25925ec4748e6d32127a6d4d7a790a7b0054eba7f842` |
| CommittedMemory | `171f16260df62aa1a407fbedc3dddafb29e2ac8ba8ff6fcc40ea8ed11dfe7449` |

## Deferred candidates

| Candidate | Status | 需要的真实证据 / 风险 |
| --- | --- | --- |
| NOVEL-015 Long-range Story Planning | DEFERRED_PENDING_REAL_ACCEPTANCE | 连续章目标和远期方向缺口；避免把局部质量问题误做长程架构。 |
| NOVEL-016 Retrieval Improvement | DEFERRED_PENDING_REAL_ACCEPTANCE | 现有精确 ID/关系/版本/Authority 检索的实证缺口；向量召回不能替代正确性。 |
| NOVEL-017 Arc / Story Management | DEFERRED_PENDING_REAL_ACCEPTANCE | 真实人物/故事 arc 维护缺口；避免新增平行 Story/Canon source of truth。 |

当前没有排序或实现。后续依据 E2E-001R、013R、014R 的实际 evidence 与人工评价确定优先级。
