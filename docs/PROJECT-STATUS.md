# Novel OS Project Status

更新：2026-10-18。当前按用户要求进入工程收敛验收，停止新增功能和反复修改特定章节。

当前测试目标、代办授权、第二章收尾与运行修复见 [收敛验收记录](reports/CONVERGENCE-20261018.md)。
测试阶段的界面操作与版本确认由助手按用户授权通过既有产品接口代办，保留 Gate、
精确版本、冲突检查和审计；不把代理测试确认写成人工文学评价通过。
最新推进见 [顺序收敛修复报告](reports/ORDERED-REPAIR-20261018.md)。第一至五章已走完测试工作流，
第五章为 C16_COMPLETED / state_version 19；本轮恢复 6 个任务均一次成功，原失败记录保留。
修复了规划身份被预算裁掉及人物怀疑被误判身份歧义的问题，验收输入也已对齐。
第五章 Draft v1 未反复修改，双审阅为 Compliance PASS / Narrative FAIL / Audience Fit FAIL；
仅按委托接受为连续性测试样本，随后通过正常接口提交 4 条有依据的 Memory 新记录/版本。
前四章、原 18 条 Memory、已批准 Profile v3 均未改写，无残留任务。

**整体五章验收仍未通过**：人物亲历知识等 Memory 漏项尚未完整解决，首稿仍有程序化对白、
重复论证和解释性旁白。第四章输出容量修复已取得有效诊断结果；第三章最新成功调用仍漏提见证知识。
后续只收敛提取完整性与上游 Plan 的剧情容量，不新增功能、不继续打磨第二章。2026-10-18 按用户要求将已有产品修复与报告提交到 main；
测试代码、本机配置和原始运行日志仍不提交，发布版本以 Git 记录为准。
[五章原运行记录](reports/FIVE-CHAPTER-20261018.md)保留此前失败快照，其中错误定位已更正。

已有产品修复已推送 main（`047e46f`）；容量根因与实验见
[Memory 容量与 Planning 对照](reports/CONTINUITY-CAPACITY-20261018.md)。Planning v13
仍为 EXPERIMENTAL，默认保持 v12。

最新执行见 [见证知识与 v4 探索复验](reports/CONTINUITY-VERIFY-20261018.md)：第三章
v7 / 16384 调用完整返回，但 Gu Che 亲见铜盒损坏的知识仍未提取，不能标修复。
第五章冻结来源的 v4 探索组件诊断格式通过，却漏引 2 条 Canon 和 6 个实体身份，
现有来源校验不能接受，已停止且没有推进 Planning/Writer。167 项相关回归通过。
现有五章全是 v3，正式 Memory 无章节摘要；完整 013R repetition 先决条件未满足。
这轮未修改产品代码、正式章节、Profile 或 Memory，也未创建新项目；没有新首稿质量结论。

后续[探索合同收敛](reports/EXPLORATION-CONTRACT-20261018.md)已完成最小修复：共用必需引用清单，
明确 Brief 版本记录 ID 与逻辑引用 ID。最终 CP-004E / Prompt v4 的真实单次组件验证
17/17 必需引用、26 项精确引用和 Brief 绑定全部通过；264 项回归通过、1 项 opt-in 跳过。
前一次 v3 引用已齐但 Brief ID 错误的失败证据保留，未进入 Planner。
本轮未生成新 Plan/正文或提交 Memory；第三章 Gu Che 与 Lin Lan 亲见损坏的知识仍漏提，
下一步收敛 A07 覆盖，完整五章文学质量及 013R 验收仍未通过。

以下保留 2026-10-08 的历史工程验收快照；其中当时的部署、测试资产与等待授权状态
不代表当前运行状态，当前状态以上述收敛记录为准。

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
