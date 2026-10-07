# Novel OS Project Status

更新：2026-10-07。工程状态依据实际代码与 CHECKPOINT 回归；真实模型调用和人工文学评价单独记录。

| 阶段 | Engineering | Real Provider / Human Acceptance |
| --- | --- | --- |
| Phase 1 / NOVEL-001～012（含 009A / 010A / 010B 等修复） | ENGINEERING COMPLETE | REAL E2E PENDING |
| E2E-001 | PASS_WITH_BLOCKERS_RESOLVED（历史工程验收） | E2E-001R PENDING |
| NOVEL-013 Creative Exploration | ENGINEERING COMPLETE | REAL ACCEPTANCE PENDING |
| NOVEL-014 Character Depth & Voice | ENGINEERING COMPLETE；checkpoint 补齐解释执行 lineage | REAL ACCEPTANCE PENDING |
| CHECKPOINT-001 | PASS_WITH_BLOCKERS_RESOLVED；backend 1708 PASS / 4 opt-in SKIP、frontend 177 PASS | 不以真实/人工 PENDING 阻止工程验收；不把 Mock 结果当行为 PASS |

本轮以最新本地 main（包含 origin/main 的全部提交）为基线，在 `wfg/checkpoint-001-phase2-integration` 保留此前尚未提交的 013/014 工作。当前开发工作区不等于远端已发布基线。

[Phase 2 Contract Freeze](specs/13-Phase2-Contract-Freeze.md) 固定 Authority、七个 Agent、章节工作流、Memory/Knowledge、Exploration、CharacterProfile、Revision 和 HumanFeedback 边界。

[E2E runner](../evals/e2e/multi-chapter/README.md) 是 Phase 2 验收主入口；[013 人工模板](../evals/creative-exploration/manual-evaluation.md) 与 [014 人工模板](../evals/character-depth/manual-evaluation.md) 保留定性比较，不计算自动创意/声线评分。真实运行要显式授权，人工 Gate 不被 runner 代签。

[CHECKPOINT-001报告](reports/CHECKPOINT-001-phase2-integration.md)记录36项工程审计、已修复阻塞、迁移/Docker/交叉Review证据与仍待真实验收的限制。

后续整体 Review 的两个验收工具问题已修复：Worker 只领取本次审计任务，历史 A/B 每次启动与模型执行前复核 Writing Profile 批准版本。补丁针对性回归131项通过，见报告37；原全量测试和Docker记录保留为修复前基线。开发服务仍需另行更新、迁移并重启，本次没有调用真实模型。

NOVEL-015 / 016 / 017 均为 **DEFERRED_PENDING_REAL_ACCEPTANCE**，未排序，未实现。完成 checkpoint 后停止开发，等待真实验收。
