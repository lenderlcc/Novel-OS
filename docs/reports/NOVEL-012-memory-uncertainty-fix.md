# NOVEL-012 — OPEN_THREAD uncertainty 误分类修复

日期：2026-10-09。范围：Memory Normalization / Conflict Detection；不修改 Writer、Review、数据库结构或 Authority 边界。

## Root Cause

`novel_os/memory/policy.py` 中两处把 `candidate.uncertainty` 当成通用阻断条件：

1. `resolve_batch_subjects()` 因 uncertainty 跳过实体解析，使 `subject_id` 和 `normalized_subject` 为 null。
2. `normalize_candidates()` 再因 uncertainty 把候选标记为 `AMBIGUOUS`。

这混淆了 OPEN_THREAD 的故事认知不确定性与实体身份不明确。原模型输出本身通过 Schema；直接调用原有 `resolve_subject()` 能唯一解析“折起的纸条”和 Missing Courier。相同 Missing Courier 的另一条 OPEN_THREAD 没有 uncertainty，因而解析成功。OPEN / PLANNED 没有受到状态限制；两条原候选的 Authority 检查均为 COMPATIBLE，项目没有已提交 Canon 或 Memory。

## Fix

复用现有规范化链路，在这两处使用同一个 `blocking_uncertainty()` 判定：仅 OPEN_THREAD 不因通用 uncertainty 文本阻断身份解析；原文本、state_after 和 value 均不改写，Authority 仍为 A6_DERIVED_MEMORY。

所有其他候选的 uncertainty 保护不变。实体 resolution=AMBIGUOUS、多个匹配、跨类型重名、未知或不一致 logical ID、正文中不存在的新名称或别名、低置信度，以及 Authority UNCERTAIN / CONFLICT、Canon 冲突、所选候选的身份重验均保留。没有增加名称猜测、自然语言特判、Case ID 特判或自动晋升 Canon。

修改文件：

- `backend/novel_os/memory/policy.py`
- `docs/specs/10-Memory-Canon-Commit.md`
- `backend/tests/test_memory_story_uncertainty.py`（新增）
- `backend/tests/core/quality/test_memory_commit.py`（两个参数化集成用例）

不改 Prompt：当前 extract-chapter-memory v3 已要求新实体名明确出现在已接受正文中。没有覆盖历史 Prompt Version。

## Regression Result

- 新增 19 项单元用例在旧代码上为 7 FAIL / 12 PASS；修复后 19 PASS。
- Memory 单元组：110 PASS。
- Proposal / Commit / Transition / Context Isolation 集成组：40 PASS。
- 总计 150 PASS；两条已有第三方弃用警告，没有测试失败。
- 新增 OPEN / PLANNED 集成用例通过正常 Proposal 和独立测试数据库中的人工确认操作，验证 uncertainty 保留、主体可解析、A6 Derived 不晋升 Canon。真实验收项目没有执行确认。
- 真正的身份歧义、未知 ID、正文名称缺失、低置信度、阻断候选的别名污染、Canon / Authority 冲突负向回归通过。
- 针对修改 Python 文件的 `ruff check`、`ruff format --check` 及 `git diff --check` 通过。
- 无数据库结构变更，无新 migration 或依赖。

### 原始 Provider 输出的精确回放

未修改原 Proposal，使用其原始 JSON、相同 Draft v4 和 Authority Snapshot 离线回放：

| 原 Candidate ID | state_after | 修复后 conflict_status | subject_id | Authority |
| --- | --- | --- | --- | --- |
| note_claim_unverified | OPEN | NONE | b7d3e7fb-0829-5852-940a-f42a22252055 | A6_DERIVED_MEMORY |
| courier_recheck_planned | PLANNED | NONE | 631477c0-a6d2-5022-adf2-21756e441d03 | A6_DERIVED_MEMORY |

两条 uncertainty 原文均保留；Missing Courier 的两条 thread 解析为同一主体。OPEN / PLANNED 没有被转成已发生事实。

## 正常流程真实重提取

执行对象：

- Project：688d6d8a-e6ae-4197-a320-c3cc1b81bf32
- Chapter 1：f20ff918-9967-4406-ba48-62cf1dac2956
- Accepted Draft v4：11454080-c744-4aeb-9296-a872d365e32f
- Workflow：e7702687-c339-4d3c-a74f-faa9a46ecdd5

通过现有 `memory/discard` 返回正文，再对已接受的同一版本执行 `completion`，由现有 A07 Worker 单次执行真实 Lingzhi gpt-5.6-sol 提取：

`C15 WAITING_HUMAN v45 → C11 WAITING_HUMAN v46 → C14 WAITING_AGENT v47 → C15 WAITING_HUMAN v48`。

新 lineage：

- MemoryRequest：8252ac7d-1d6f-4cda-ade2-f1ac41466297
- Proposal：9307f8ce-fb2e-4a66-8011-2f90f9ffd2b5
- AgentTask：cd9e5ef9-294c-4abe-bf48-779ed4b0f019
- AgentRun：69854353-5d79-4e66-b3e0-259ea74c73f4
- ContextPackage：72b99803-de2d-46d9-a4f4-30a2d9bb9206
- PromptLineage：4f414154-a629-4d10-bfbd-b1db1d9d8e3e
- Prompt：extract-chapter-memory v3；Schema：chapter-memory-result v2
- ModelProfile：lingzhi-structured；Provider / Model：lingzhi / gpt-5.6-sol
- AgentRun SUCCEEDED，1 次调用，40,805 ms；没有自动重试。

### 新 Proposal 的实际状态

真实模型重新生成了候选，ID、名称和状态并不保证与原提案相同；下面是实际输出，没有手工映射或修改：

| 对应内容 / 新 Candidate ID | state_after | conflict_status | normalized_subject / subject_id | Authority checks |
| --- | --- | --- | --- | --- |
| 纸条主张未证实 / midnight_note_validity | OPEN | AMBIGUOUS | null / null | COMPATIBLE |
| 后续调查约定 / planned_time_recheck | OPEN | NONE | Lin Lan / 9800cbdf-fb70-5bcc-99fe-14365920b746 | COMPATIBLE |
| 信使去向未明 / courier_whereabouts | OPEN | NONE | Missing Courier / 631477c0-a6d2-5022-adf2-21756e441d03 | COMPATIBLE |

三条均为 OPEN_THREAD / DERIVED / A6_DERIVED_MEMORY，uncertainty 保留。

**纸条的新 AMBIGUOUS 原因是正文名称证据缺失，已不是 uncertainty。** 新模型将 subject_ref.name 写成“来历不明的纸条”，该完整字符串不在已接受正文中；正文包含“折起的纸条”和“来历不明的纸”。现有 resolver 正确返回“新实体及别名必须在已确认正文中明确出现”。模型没有遵守当前 Prompt 的名称要求，因此保留该保护，不通过改名、猜测别名或再次调用模型来制造通过结果。

后续调查的新候选由模型输出为 OPEN，uncertainty 明确记录这是后续安排、不保证发生；Normalizer 原样保留，没有把 PLANNED 改成 OPEN。原 PLANNED 输入在精确回放和回归测试中均可通过。当前新提案不声称该行动已经发生。

## Persistence / Human Boundary 核对

- 原 Request 和 Proposal 全字段与修复前相同；旧提案通过正常工作流显示 CANCELLED 并保留历史，没有直接修改 Candidate。
- Draft v1–v4 及 Chapter 全字段与修复前相同；current_version = approved_version = 4。
- API 与 DB 中的新 Proposal raw_output / candidates 完全一致。
- 只读数据库查询：MemoryCommitBatch = 0、CommittedMemory = 0、MemorySubject = 0；项目 Chapter 数量仍为 1。
- 没有执行 `memory/confirm`，没有写 Commit Entry，没有创建或继续第二章。
- Backend、DB health、Frontend 均 HTTP 200。更新后的后台 Worker 已恢复，当前没有待执行任务；Workflow 停在 C15_MEMORY_COMMIT / WAITING_HUMAN v48。

## Evidence / Remaining Limitation

本机证据保存在 `backend/.runtime/memory-uncertainty-20261009/`：before.json、root-cause-replay.json、same-output-after-fix.json、after.json、verification.json、unit-before.log、unit-after.log、integration.log、discard-response.json、completion-response.json、reextract-task.json、reextract.log、waiting-human.jpg、candidates.jpg。

规范化误分类修复与工程回归通过；真实新提案中的纸条候选仍因不合法实体名阻断，不能把它报告为 NONE。是否接受其余候选、返回重新整理或修改正文，留给用户在 Human Confirmation 决定。本轮停止。
