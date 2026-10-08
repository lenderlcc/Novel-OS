# Novel OS Project Status

更新：2026-10-08。工程状态依据实际代码与 VALIDATION-001 回归；真实模型调用和人工文学评价单独记录。

| 阶段 | Engineering | Real Provider / Human Acceptance |
| --- | --- | --- |
| Phase 1 / NOVEL-001～012（含 009A / 010A / 010B 等修复） | COMPLETE | E2E-001R PENDING |
| E2E-001 | PASS_WITH_BLOCKERS_RESOLVED（历史工程验收） | E2E-001R PENDING |
| NOVEL-013 Creative Exploration | COMPLETE | NOVEL-013R PENDING |
| NOVEL-014 Character Depth & Voice | COMPLETE；解释执行 lineage 已保存 | NOVEL-014R PENDING |
| CHECKPOINT Engineering / VALIDATION-001 | PASS_WITH_BLOCKERS_RESOLVED；backend 1,799 PASS / 4 opt-in SKIP / 0 FAIL / 0 ERROR，frontend 177 PASS、browser 13/13 PASS | REAL PROVIDER CALLS = 0；Real AI Behavior = NOT RUN |

VALIDATION-001 基于 `wfg/checkpoint-001-phase2-integration` 的已提交 001～014 / CHECKPOINT 实现开展验证，验收时基线 HEAD 为 `38de644b835ae06eed82b39a9959a11f5b0d6d9b`。2026-10-08 按用户要求，将此前实现、本次局部正确性修复、正式报告与验收材料整合到 main；不提交测试代码、本机配置或原始运行日志。验收报告及其证据哈希保留 2026-10-07 的验证时快照，当前发布提交以 main 的 Git 记录为准。

[Phase 2 Contract Freeze](specs/13-Phase2-Contract-Freeze.md) 固定 Authority、七个 Agent、章节工作流、Memory/Knowledge、Exploration、CharacterProfile、Revision 和 HumanFeedback 边界。

[E2E runner](../evals/e2e/multi-chapter/README.md) 是 Phase 2 验收主入口；[013 人工模板](../evals/creative-exploration/manual-evaluation.md) 与 [014 人工模板](../evals/character-depth/manual-evaluation.md) 保留定性比较，不计算自动创意/声线评分。真实运行要显式授权，人工 Gate 不被 runner 代签。

[CHECKPOINT-001报告](reports/CHECKPOINT-001-phase2-integration.md)记录36项工程审计、已修复阻塞、迁移/Docker/交叉Review证据与仍待真实验收的限制。

后续整体 Review 的两个验收工具问题已修复：Worker 只领取本次审计任务，历史 A/B 每次启动与模型执行前复核 Writing Profile 批准版本。补丁针对性回归131项通过，见报告37；原全量测试和Docker记录保留为修复前基线。开发服务仍需另行更新、迁移并重启，本次没有调用真实模型。

NOVEL-015 / 016 / 017 均为 **DEFERRED_PENDING_REAL_ACCEPTANCE**，未排序，未实现。完成 VALIDATION-001 后停止，等待 Review 与真实验收。

[VALIDATION-001 工程报告](reports/VALIDATION-001-post-novel-014.md) 重新验证 001～014，包括双 Revision 单章、原五章 Recorded E2E、Context/Authority/freshness、13 Task 的实际 Prompt lineage、只读 export、隔离 migration roundtrip/check、Docker 两个 role build / health，以及验证完成后的独立 Review。四项正确性契约修复保持既有架构；不做创意、人物、写作质量 tuning。

发布限制：测试按此前用户要求不提交，HEAD 的旧测试与当前本地测试存在 IMPLEMENTATION_DRIFT，不能宣称 fresh clone 能重现本地完整绿色。0021 尚未应用到开发库，当前开发服务未更新、未重启。验收用的测试 schema/容器均已清理。本轮没有调用 Lingzhi，也没有启动真实模型后台 Worker。
