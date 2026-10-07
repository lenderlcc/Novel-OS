# NOVEL-010 人工 Revision 验收

仅使用现有 Case 04 / Case 05。此目录是人工 opt-in 模板，不会发送 Provider 请求。NOT_RUN 不能解释为模型已经改善。

1. 核对 manifest 的 exact Draft ID/hash、原 Review 和实际 approved Profile；Context 已变化时先由用户明确重审，不能偷换原输入。
2. 用户明确点击“根据审阅修改”，运行 A06 两阶段及自动 A05 重审一次，然后停止。
3. 保存 source Draft / source Review / RevisionPlan / successor Draft / new Review，以及 request、Task、Run、PromptLineage、ContextPackage、ModelProfile 和 approved Plan/Brief/Profile IDs。
4. 填写 evaluation.md，不追求 Review 必须 PASS；检查核心问题是否改善、Strength 是否保留、新重大问题是否出现。

Case 04 的历史导出没有 AI Review，必须先由用户明确生成正式 Review。Case 05 的历史输入没有 approved WritingProfile，不能直接进入 Revision，也不能借用 Case 04 Profile。必须先为该项目批准 Profile，再明确重新审阅并记录新输入；不得用旧 Review 偷换新 Profile，不能声称与原历史输入完全相同。
