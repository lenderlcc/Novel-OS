# E2E-001R 第二章 — Writing / Quality Review

日期：2026-10-09，Asia/Shanghai。最后一次模型任务完成于 20:42:59。

用户取消本轮“最多 3 次调用、到 Plan 人工审批关卡停止”的执行限制后，第二章已继续生成 **Draft v1** 并完成合规、叙事两项质量审阅。流程停在 **C11_INTERNAL_PASS / WAITING_HUMAN**，等待用户评估正文。第一章、已提交 Memory 和 Writing Profile 未修改。

本报告接续 `E2E-001R-chapter02-plan-gate.md`。前一报告记录此前的 Plan Gate 快照，不能作为当前运行状态。

## 授权及人工边界

- 用户已在产品 UI 人工批准 Plan v1；Gate `647be624-b116-4a7a-9e16-9f72743d0f96` 的决策为 APPROVE，actor 为 local-user，时间为 20:31:35。
- 本轮继续执行的授权来自用户“取消这个限制”，沿用第二章要求、Lingzhi / `gpt-5.6-sol` 和既有外发范围。
- 调用总数不再以原 3 次配额为上限。本次实际继续执行 3 个任务：Writer、Compliance Review、Narrative Review，各一次尝试；没有重试。
- 人工 Plan 审批未被绕过。Draft 接受、Memory 提交的人工确认仍保留。
- 没有执行修订、接受 Draft、准备或提交第二章 Memory，也没有创建第三章。
- 执行复用既有 runner `one-task` 和 Worker `--once --task-id`，限定为该第二章的实际任务，没有启动无范围限制的连续 Worker。

## 产物与绑定

| 对象 | 实际值 |
| --- | --- |
| Project | `688d6d8a-e6ae-4197-a320-c3cc1b81bf32` |
| 第二章 | `749f1271-6897-4797-9e58-e2d1da271a7b`，《没有证据的怀疑》 |
| Workflow | `333a12fe-4bca-44c9-9852-2854a9eba424` |
| 已批准 Plan | `300683ff-7506-4c2f-979e-8c79644903d5`，v1 |
| 实际 Writing Profile | `2c20019e-3e5c-421f-9545-303d354f3291`，APPROVED v3 |
| Profile hash | `ea711d16a708b30fb53c3e09e9b284c3dff0dd754b90184611769c34706e77e2` |
| Draft | `8d7a9b11-f48f-4594-99ef-13219d0f2e26`，v1，DRAFT / A7_AI_INFERENCE |
| current / approved prose version | `1 / null` |
| WritingResult | `b8b2dca5-3100-47b3-8936-e0ca8b23167f` |
| 正文 SHA-256 | `27386da91a3e2434f4ef0f05aee943668805fdcc16b84b8fda4e263c6536089c` |
| Writing deterministic check | PASS，check_codes 为空 |
| Quality Review | `0bcff9aa-a878-48e0-ba5e-ff3c4eb5f93a`，v1，准确绑定 Draft v1 |
| Review binding | `4de5cd7e-90ef-48ec-ad72-1c9f9d392cd8`，Draft / Plan / Brief / Profile 精确版本绑定 |
| Review freshness | CURRENT |
| 停止状态 | C11_INTERNAL_PASS / WAITING_HUMAN，state_version 11 |

## 审阅结论与人工复核

| 审阅维度 | 模型结果 |
| --- | --- |
| Compliance | PASS，无 hard gate issue |
| Narrative | PASS_WITH_WARNINGS |
| Audience fit | PASS_WITH_WARNINGS |
| Overall | PASS_WITH_WARNINGS |

模型列出三项 P2 问题，均 `requires_revision=false`：

1. `OVER_STRUCTURED_DIALOGUE`：对白过于完整地执行论证、定义和任务拆分，人物防御方式与个人声音的差异被削弱。
2. `REQUIREMENT_VISIBILITY_BIAS`：直接说明“不猜测”“不开盒、不验证”，章末集中汇总状态，显露验收清单式表达。
3. `AUDIENCE_STYLE_MISMATCH`：程序化对白和状态总结局部不符合 Profile v3 的高自然度偏好。

保留项包括：早入冲突、Gu Che 有限视角、怀疑与证据的区分、双方带条件的合作、铜盒完好以及警报责任未揭晓。人工初读与上述边界检查一致，未见 Gu Che 自动获得第一章纸条、窥读 Lin Lan 内心、确认警报责任或验证午夜机制。

### 字数偏差单独记录

Profile v3 要求 2000–2500 字。模型审阅没有列出字数问题，工程链路成功不能替代这项验收。

排除首行章名后，正文包含 **1692 个汉字、149 个英文单词**。按“汉字各计 1、英文单词各计 1，不计标点和空白”的本轮人工复核口径，共 **1841**，比下限少 **159**。

原始字符串长度为 2897，包含章名、空白、标点和英文逐字母计数；不能以这个数字宣称满足字数要求。现有 WritingMetadata 没有统一的 `word_count` 验收字段，Profile 也未定义混合语言计数口径，本报告明确列出复核方法，没有修改产品计数规则或直接补写正文。

因此：工程执行成功；AI Review 有提醒；正文人工验收仍待用户决定，字数问题未解决。

## 实际 Writer Context

Writer Context `1f472ab8-1924-4fbd-9d23-37ba0d52b6a4` 构建为 READY，CP-005 v7，无 missing required item 或 Authority conflict。

实际选入 7 项：批准 Plan v1、完整第二章 Task 输入、本章、批准 Profile v3，以及三项 Memory Subject 身份资料。Writer **没有直接收到第一章 Draft v4 全文或五条已提交 Memory 的状态/私有知识 payload**；前章连续性由已批准 Plan 承接。实际 Writer 上下文没有第一章午夜纸条的完整文字。

Plan 的 `pov_character_id=null` 仍存在，因此本人结构化 Memory 检索为空；现有 Policy 不会因此放行 Lin Lan 的私有知识。本轮未添加实体身份、伪造 Memory 或放宽知识权限。当前正文未观察到泄漏，但这个身份绑定缺口仍是后续连续性验收需要记录的限制。

## 任务证据

| 阶段 | Task ID | Run ID | Context ID | PromptLineage ID |
| --- | --- | --- | --- | --- |
| Writer | `207ef257-2bfa-46f8-86c5-b21a9aa08fb2` | `f1b4e862-67a0-4400-8299-5790a452408a` | `1f472ab8-1924-4fbd-9d23-37ba0d52b6a4` | `cd145f03-dd21-4e90-97ee-be2c98f3b05b` |
| Compliance | `0a4b894b-7974-4d84-b9ae-685d3f8228a1` | `a41db596-46de-4e6a-8287-9c4930307681` | `91c3c536-9f72-4e66-9a49-f3bbea764d58` | `4f05b15a-9fe4-4af4-872b-4b65a5119044` |
| Narrative | `06d5c991-c034-44fe-95fd-4461a1e8461a` | `14ead76e-3903-435a-8b5a-6fe08412b634` | `2200e6a0-e7ad-4ee9-8ef5-05afb676d963` | `1d91120e-e1fc-48ef-9721-3844966c789c` |

全部为 Lingzhi / gpt-5.6-sol，attempt 1，SUCCEEDED / APPLIED；三个 Context 构建均 READY，使用批准 Profile v3，无 future item。完整 runner trace 的 lineage_errors 为空。

两项质量审阅实际因 TOKEN_BUDGET 排除了第一章已接受 Draft v4 全文，因此其跨章判断依赖本章 Plan / Brief，未完成对两章全文的逐字连续性检查。29 条审阅 excerpt 已独立核对，均与 Draft v1 原文和段号一致。执行完成后旧 Context 的 freshness 可因 Workflow v10 → v11 变为 STALE，不表示模型执行时使用了过期 Context。

API 与只读数据库核对通过：第一章 Chapter / Workflow / 正式 Memory 和 Profile 与执行前相同；全局 AgentRun 155 → 158，恰好新增三次；活动任务数 0。第二章 Memory history 为空，第三章不存在。

## 本地证据与交付

证据位于 `backend/.runtime/e2e001r-20261009-chapter02/`，运行目录被 Git 忽略：

- `continuation-authorization.json`：取消旧限制的用户指令及本次实际执行记录。
- `before-writing.json`、`04-writing.json`、`05-compliance-review.json`、`06-narrative-review.json`：执行前后产品状态。
- `05-compliance-pass.json`：通过只读事务获取的合规结果。
- 各 `*-context.json` 和 `*-prompt-lineage.json`：真实上下文及 Prompt 版本证据。
- `chapter02-draft-v1.txt`：持久化正文的只读导出。
- `final-writing-verification.json`：最终绑定、数据不变、计数和停止边界。
- `full-writing-trace.json`：既有 runner 完整导出；Human Prose Evaluation 为 PENDING。
- `writing-review.jpg`、`review-result.jpg`：页面草稿和审阅结果。

本轮没有产品代码、配置、Prompt 或数据库结构修改，没有新迁移或自动测试变更。正文未自动修订或接受，等待用户人工评估。
