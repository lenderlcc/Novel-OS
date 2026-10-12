# NOVEL-011 — Feedback Prompt Selection Fix

日期：2026-10-08。

## 问题和根因

第一章反馈诊断返回的 `feedback_evidence` 额外包含中文展示引号，违反必须取自用户原文连续子串的规则。原始输出结构通过 Pydantic，但现有 semantic validator 正确拒绝了引用。`interpret-chapter-feedback` v4 已补充精确复制规则，真实 Run 却仍使用 v3。

原因在 `PromptRuntime.prepare()`：`profile_prompts` 将 `INTERPRET_CHAPTER_FEEDBACK` 固定映射为 CP-008 v1 → Prompt v2、CP-008 v2 / 预算预估 → Prompt v3。这样覆盖了默认 TaskDefinition 的无版本引用，使已有 Registry 的 latest STABLE 解析路径无法选择修复版。

## 最小修复

删除 Runtime 中这一条过时反馈映射，直接复用现有 TaskDefinition → PromptRegistry.resolve → PromptCompiler 链路。新执行使用当前 STABLE v4；未来发布稳定版本沿用同一解析器。显式历史 ModuleRef.version 仍精确选择原版本，不重写旧 Prompt、Run、Context 或 Lineage。

v4 追加规则要求每条反馈证据是用户消息的原样连续子串，禁止额外中文引号、Markdown 包装、前后缀、省略号及改写；用户原文实际包含的引号仍保留。Clarification 只允许引用相应用户消息，不允许引用 AI 决策问题。

不加入 strip/normalize fallback，不放宽 Authority 或原文校验。Pydantic 输出形状、Service 验证、Repository、数据库、Workflow、Writer 和 Quality Review 均不变。没有新依赖或 migration。

## 回归与证据

- 修前真实 AgentRuntime.prepare：旧/新/无 Context 三种路径都未选 v4；临时后续 STABLE v5 也被固定映射绕过。6 个选版回归失败，历史 pin 与 evidence 边界 8 个通过。
- 修前完整 Recorded Worker / API / persistence 链在实际 PromptLineage 断言处失败：3 != 4。
- 修后 72 个单元及 Prompt 测试通过。加强原始输出不变断言后，14 个反馈专项回归再次通过（包含在前述 72 项中，不重复计数）。
- 集成回归：126 PASS（812.98 秒）。覆盖反馈、clarification、修订、authority/freshness、fidelity、人物上下文隔离；完整 Recorded Worker / API / persistence 链生成 Draft v2，Fidelity PASS，后续 Review 绑定 Draft v2。与前述单元测试合计 198 项通过。
- 使用本次真实失败 Task 和不可变 ContextPackage 进行 READ ONLY 编译，CP-008 v2 已选择 v4/hash `7ffe9cf96ad2e647d341e115cab7e94e6a5950f23ee4ed083b6c9499a942d075`。未调用 Provider.generate，也未重新保存历史 Lineage。
- Ruff check / format --check 通过；git diff --check 通过。
- 独立五轴 Review 未发现必修问题：复用既有解析器、减少分支、保留历史 pin 和 Authority；没有新增封装。

证据位于本机 `backend/.runtime/e2e001r-20261008/`：`feedback-runtime-full-slice-before-fix.log`、`feedback-runtime-unit-before-fix.json`、`feedback-runtime-fix-unit.log`、`feedback-runtime-fix-final-evidence-tests.log`、`feedback-runtime-fix-integration.log`、`feedback-runtime-fix-actual-context-preview.json`、`feedback-runtime-fix-live-state-check.json`、`feedback-runtime-fix-result.json`、`feedback-runtime-fix-api-restart.json`、`feedback-runtime-fix-independent-review.json`。

## 运行状态与验收边界

本机 Backend 已重载修复代码，GET health / health/db 均 PASS；没有启动 Worker。修复源文件在验证期间无漂移。

本轮真实模型调用为 0，已有真实 Run 总数保持 8。第一章仍为 Draft v1，未批准，没有 Revision 产物或 Memory 提交；Workflow 仍停在 C90_BLOCKED / version 17，没有自动恢复或后台 Worker。

离线完整修订工程链的 PASS 只能证明 Prompt 选版、validation、事务与版本/审阅绑定；不能声称修复后的真实模型已产出新稿，也不能冒充 Human Prose Acceptance。真实重跑未执行。
