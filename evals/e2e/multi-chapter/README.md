# Phase 2 人工验收入口

CHECKPOINT-001 复用本目录的 `run.py`、现有 API、Context/Prompt Runtime 和标准 Worker。`acceptance-manifest.json` 列出 E2E-001R、013R、014R 的能力、付费需求、人工 Gate、先决条件与 PENDING 状态。没有新 runner、执行框架或评分服务。

Phase 2 的真实模型入口统一为 **`--allow-real-provider --worker-stopped`**。默认 prepare/status/export 不调用模型；Profile approval 只记录操作者明确选择。历史 `evals/quality/run.py --real` 和 pytest `--live-model` 保留作单独授权的诊断入口，不是 Phase 2 suite 的执行入口，也不能替代本脚本的隔离和 Gate 检查。开发启动、pytest/CI 不自动调用真实 Provider。

## CHECKPOINT selected case preparation

E2E-001R 沿用下面的 `init` 或 `prepare --test-id E2E-001R`，仍使用历史 v3 Workflow、独立五章项目和逐章人工操作。新 013/014 case 使用现有 v4 `/workflows/chapter-exploration`，不改变旧项目或历史定义。

014R 每个 case/variant 新建一个独立 Project、真实 Character 身份、固定 fixture ID 到实际 ID 的映射、Writing Profile Draft，以及仅所选人物的 Behavior Profile Draft。关系修饰引用先创建的实际 counterpart ID。只将所选 `raw_requirement` 作为章节输入；`evaluator_only`、Synthetic Knowledge、Secret X、预期答案或其他 variant 不作为模型输入。

```bash
cd /Users/agiuser/novel-os/Novel-OS/backend
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json prepare --test-id 014R --case CDV-01-same-pressure --variant A
```

查看返回的 Profile Draft、真实 ID 和 hash，通过 Workspace 或现有 API 明确批准，脚本也保留显式操作：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json approve-profile --expected-version 1
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json approve-character-profile --character-id <输出的实际-ID> --expected-version 1
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json --allow-real-provider --worker-stopped start --chapter 1
```

start 要求准确版本/hash 的所选 Character Profile 已批准。没有自动审批。B 使用另一个 state/project 的 `--variant B`；Relationship case 使用 JSON 中的完整 label `"A speaks to B"` 或 `"A speaks to C"`。无 variants 的 Case 03/04/05 不传 `--variant`。CDV-05 在单独的无 Profile 项目中准备，不会把已批准 Profile 偷偷排除以伪造兼容性。

以下情况先保持 **BLOCKED**，直到正式来源具备且只读检查通过；不创建假事实或直接 seed 数据库：

- 013R Case 03 需要可核对的历史 A Plan、原 Writing Profile v1/hash、可比 Authority Context；新的 Profile/POV 不能冒充原输入。`prepare --test-id 013R --case case-03-historical-small-setback` 保存具体先决条件与独立 run 标识，不自动复制历史 Canon。
- 013R repetition case 需要最近三个已完成章节、合法批准的 Plan history，以及真实提交的章节摘要。`prepare --test-id 013R --case recent-mechanism-repetition` 不把 eval 中的合成机制摘要塞入 Context。通过原 Plan 创建/审批、章节完成和人工 Memory confirmation 建立来源，再通过 `/planning/history`、Run `/context` 和 Memory APIs 核对。
- CDV-04 完整 Knowledge isolation 验收需要同一独立项目中正式提交、绑定正确 owner 的 Knowledge sources。现有 chapter completion → A07 proposal → 人工 Memory confirm 是合法准备路径；模型仅看到空盒/已移开等允许输入。准备该 case 会保存 Draft/身份和 BLOCKED 原因，不能把 evaluator 的 Secret X 落入 Canon。合法来源就绪后可以执行下面的只读检查。
- Review/Revision 弱正文 follow-up 需要真实 ChapterVersion、Review 与 Context 绑定。无法建立合法来源时记 NOT_RUN；不能伪造 Run、approved Chapter 或已提交 Memory。

### 只读检查与解除 BLOCKED

013R 的 prepare 不创建 Project。操作者先核对输出的 `scenario_id`、`run_id` 和 `fixture_hash`，通过现有 `POST /api/v1/projects` 人工创建独立 Project，将这三个值原样填入对应的 Project metadata。请求 body 结构如下，占位值必须来自本次 prepare 输出，不能使用其他 state/project 的值：

```json
{
  "name": "013R selected case",
  "description": "Isolated human creative exploration acceptance",
  "metadata": {
    "e2e_scenario": "013R",
    "e2e_run_id": "<本次 prepare 的 run_id>",
    "e2e_fixture_hash": "<本次 prepare 的 fixture_hash>"
  }
}
```

仍通过现有 Writing Profile Draft/approval API、Plan approval、章节 completion 和 Memory confirmation 准备合法来源；审批必须由操作者明确选择。来源不能靠复制 evaluator 内容、直接 DB seed 或更改旧来源的版本/hash 来补齐。

Case 03 的检查读取历史 A Plan、ContextPackage 和原 Writing Profile，核对 A 的精确 v1/hash，再逐项比较 B 的 canonical writing preferences；A/B 记录各自真实 record/hash，不能偷偷给 B 增加原输入没有的 POV。只有 A 没有额外 Authority source、B 也没有额外批准 Requirement/Decision、active Lock 或 Memory 时，检查才解除 BLOCKED。存在额外 Canon/Lock 等来源时仍明确阻断，要求人工核对可比性，不会自动复制或忽略来源。

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/013r-case03.json prepare --test-id 013R --case case-03-historical-small-setback
# 使用 prepare 输出的 metadata 经现有 API 创建 Project、准备并批准合法来源后：
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/013r-case03.json check-prerequisites --project-id <实际独立-Project-UUID>
```

014R CDV-04 已由 prepare 创建独立 Project；在该项目完成正式 Knowledge commit 后，使用相同命令和该 Project ID 检查。该 case 要求实际 POV owner 的 `KNOWS`，以及另一个 owner 对不同 Canon fact 的 `KNOWS`；来源必须来自已完成 Workflow、精确批准正文和人工确认的 COMMITTED batch，不读取 evaluator Secret X。

`check-prerequisites` 只执行 GET，检查 metadata ownership、批准的 Writing Profile、所选 Character Profile 的精确 version/hash 与 case 来源；只写本机 state 中的 `prerequisite_evidence`、`chapter_sequence_base` 和 readiness 状态，不调用模型、不写 API、不审批或提交 Memory。失败仍为 BLOCKED，并保留具体原因。013R repetition 的三个近期来源必须是 final approved Chapter 经正式 Memory commit 产生的 `DERIVED_CHAPTER_SUMMARY`，仅批准三个 Plan 不够。

检查通过时记录已批准 Writing Profile 的 record ID、version 和 hash。`start` 与此后每次 `one-task` 都重新核对这三项；批准版本变化会在创建章节或启动 Worker 前拒绝执行，新的未批准 Draft 不影响原批准版本。尚未 start 的 run 可重新执行 `check-prerequisites`；已 start 的比较须保留原证据、重新准备未启动的独立 run，不能覆盖 pin 继续使用混合输入。

检查通过后才可显式 start。`--chapter 1` 始终是本次 selected case 的本机索引；实际 Chapter sequence 使用已核对项目中 `max(existing sequence) + 1`，为准备来源的旧章节保留原序号。先决条件检查不是人工模型验收 PASS，也不会启动下一阶段。

### E2E-001R 输入 baseline

新的 E2E-001R `fixture_hash` 覆盖 `scenario.json` 与 `chapter-01.json`～`chapter-05.json` 全部文件内容。任何逐章输入变化都会使 baseline 不匹配，不能沿用旧 hash 继续付费执行。

历史 state 如果只绑定旧的 scenario hash，只允许 status/GET-only export，证据标为 `INPUT_BASELINE_PARTIAL`；付费续跑保持 BLOCKED。先人工复核当前完整输入，再使用新的 state 和独立 Project 执行 init/prepare，建立完整 baseline。不要修改旧 state、Project marker 或自动 pin 新 hash 来绕过复核；原始历史证据仍可只读导出。

## Bounded run to next gate

保留 `one-task` 的一次 attempt 操作。新增命令仅在单章中反复调用它，最多执行明确的 task budget（默认 6、允许 1–12），遇到人工 Gate、Draft/Review 验收、Memory Confirmation、失败、升级、暂停或 budget 耗尽立即停下。不会自动批准 Plan、接受 Draft、确认 Memory、重试技术失败或启动下一章。

每次执行同时检查 API 队列和配置文件指向的 Worker 实际数据库：迁移 head、Project/Workflow/Task 记录和全部活跃章节任务必须与审计范围一致。额外 PENDING/CLAIMED/RUNNING 任务会阻断执行；独立人物解释报告不在后台 Worker 队列中。runner 自动将本次审计的 Task IDs 通过可重复的 `--task-id` 传给原有 Worker `--once`，数据库领取查询仅在这些 IDs 内选择一个任务，因此预检后其他项目新入队的任务也不会被本次执行领取。普通 Worker 未传该参数时行为不变；`--task-id` 只允许与 `--once` 一起使用。

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json --allow-real-provider --worker-stopped run-to-next-gate --chapter 1 --max-tasks 6
```

到 C06 后，先人工读 Plan，再明确 `approve-plan` 或通过 Workspace 决定。接着：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json --allow-real-provider --worker-stopped continue-after-human --chapter 1 --max-tasks 6
```

continue 对比本机 stop 的 state version、实际 Workflow history 和关联 AuditRecord，必须存在属于此 Workflow 的 USER 审批/修订/反馈/接受/Memory 操作；仅改变页面、模型内部 transition 或重按按钮不能冒充 human gate。第二个 run-to-next-gate 不能绕过已记录的人工 stop。

Writing 和 Quality Review 结束后必须再次人工判断：明确 Revision / Feedback，或 `finalize` 精确 Draft ID。之后 continue 才能执行 A07，仍停在 C15，由人选择候选或显式空提交。第 1 章完成不等于五章 suite 完成；下一章仍必须显式 start。

## Evidence and optional blind reading

export 始终 GET-only，保留完整原始输入、全部版本、Audit/Human Gate、每次 Task/Run、ModelProfile、PromptLineage 和 ContextPackage。新增 Character directory、profile current/approved pointers、全版本及独立 Profile interpretation Tasks/Runs；不只导出当前或已选 Profile。metadata 记录 run/test/project、观测 provider/model profile、started/completed、human actions/gates 与 PENDING/BLOCKED 状态。Mock/Recorded 无法被标成真实验收 PASS。

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/014r-a.json export --output .runtime/014r-a-evidence.json --blind-reading-output .runtime/014r-a-blind.json
```

盲读选项只在独立 human reading aid 中把已知 Character identity 的明确姓名替换为同一 `[人物]`；不推断角色、不评分、不裁定 PASS。原始全文不改，样本 label → ChapterVersion ID / 原姓名映射只保存在完整 evidence，盲读评阅人先读 aid，评阅完成后再打开映射核对。主持人另行选择可比片段与展示顺序，姓名隐藏不代表完全消除场景线索。

使用 `evals/creative-exploration/manual-evaluation.md` 和 `evals/character-depth/manual-evaluation.md` 分开记录 Real Behavior / Human Prose；自动化只能提供 Engineering evidence。真实模型与人工评阅未完成时状态保持 NOT_RUN / NOT_EVALUATED / PENDING，不开始 NOVEL-015。

## E2E-001 五章连续性验收

这是验收夹具与手动运行入口，不是新的产品功能。`recorded_draft` / `revised_draft` 仅供离线 Recorded Provider 验证工程链路，不能当作真实模型创作或人工文笔验收证据。正式人工运行只把每章 `raw_requirement` 提交给现有 Workflow。

`scenario.json` 定义独立 Project、Writing Profile 和语义实体 A/B/L1/L2/X/K/T/Y/Z。`chapter-01.json`～`chapter-05.json` 定义逐章输入。`expected-memory.json`、`expected-context.json` 和 `coverage.json` 保存验收预期与测试映射。语义实体由证据中的实际 `subject_id` / `logical_id` 绑定，不把显示名称当成持久身份。

第五章 `B.X = ABSENT` 同时要求上下文隔离和本章不发生主动披露；`chapter-05.json`
现已明确携带“不告知暗号”的输入约束。仅有检索过滤不能禁止人物在故事中主动告知。
2026-10-18 之前已运行的输入和首次失败结果仍按原快照保留，不用新输入追认旧验收通过。

## 离线工程验收

在 `backend/` 使用现有 pytest/PostgreSQL 隔离测试库。按 `coverage.json` 的节点运行五章链路及已有负向测试。配置文件中的 `test_database_url` 必须指向 `_test` 数据库；不需要 Provider credential，不调用外部模型。

```bash
cd /Users/agiuser/novel-os/Novel-OS/backend
uv run --locked pytest tests/core/quality/test_multi_chapter_continuity.py tests/core/quality/test_memory_context_isolation.py tests/core/quality/test_memory_commit.py tests/core/quality/test_memory_transitions.py tests/test_memory_transition_contracts.py tests/test_memory_contracts.py -q
uv run --locked pytest tests/core/test_e2e_manual_runner.py -q
```

Runner API 用例单独执行。当前 pytest 9.1.1 在混合子目录、根层文件和父目录文件的路径顺序下，可能创建同名但不同对象的 collection Directory，使已有 `core` fixtures 无法匹配；拆分命令保留全部覆盖，不修改 fixtures 或产品代码。

五章主链节点是 `tests/core/quality/test_multi_chapter_continuity.py::test_five_chapter_formal_continuity_and_finalized_revision_isolation`。`coverage.json` 映射完整 26 项验收场景到实际节点。离线工程 PASS 不能替代 AI Behavior Acceptance 或 Human Prose Evaluation。

## 人工运行前准备

1. 先检查当前代码和数据库 migration 一致，数据库已升级至当前 head。不要用旧 Backend / Worker 测试新的 Memory 状态迁移。
2. 保持 Backend、Frontend、PostgreSQL 运行，停止所有持续轮询 Worker。Docker Worker 用 `docker compose stop worker`；本机 Worker 在其启动终端按 Ctrl+C，等待当前任务结束。不要同时保留本机和容器 Worker。
3. Backend 与手动 Worker 使用同一数据库。配置只写本机 TOML，密钥不写入夹具、命令行、报告或聊天。
4. 本机 `backend/config.toml` 使用已配置的真实 `agent_model_profile`，设置 `agent_execution_scope = "chapter-quality"`、`agent_max_attempts = 1`。Backend 的公开 `/api/v1/agent-execution/config` 必须显示相同 model profile。`one-task` 还会只读核对 Worker 配置数据库的 migration head、独立 Project 标识、Workflow、Task 与 API 身份；不同数据库、旧 migration 或不一致任务会在模型调用前被拒绝。配置变更后的 API 重启按主 README 的现有步骤执行。
5. 其他 Project 不得有待执行或已领取任务。脚本会通过正式 API 检查全局队列；存在其他任务时拒绝启动 Worker。通过原 Workspace 处理这些任务，不直接修改数据库。

`--worker-stopped` 是操作者对所有轮询 Worker 已停止的确认，脚本不能通过公开 API 证明另一个进程永远不会重新启动。人工运行期间不要重启后台 Worker，也不要在其他 Project 提交任务。

## 建立独立 Project 与批准 Profile

所有命令在 `backend/` 运行。下面的 `.runtime/e2e001-manual/project.json` 是忽略的本机运行状态，包含新建 Project / Chapter / Workflow ID，不含密钥。不会复用 Case 01～05。

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json init
```

命令只新建 Project 和 Profile Draft，不启动模型。先检查输出的完整 Profile，再显式批准其版本：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json approve-profile --expected-version 1
```

## 每章逐阶段执行

Chapter 01 的启动命令需要显式确认允许后续真实模型任务，以及后台 Worker 已停止。它仅提交 Requirement，不启动 Worker。

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json --allow-real-provider --worker-stopped start --chapter 1
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json status
```

复制 `status` 中的真实 `current_state`，一次只执行一个任务。例如需求阶段：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json --allow-real-provider --worker-stopped one-task --chapter 1 --stage C01_REQUIREMENT_INTAKE
```

`one-task` 调用现有 `python -m novel_os.worker --once`，执行至多一次 claim/attempt 后退出。它不会循环、自动重试或批准人工 Gate。执行后查看 `status` / Debug 再决定下一步。正常 Planning / Plan Review / Writing 分别使用当前状态 `C04_CHAPTER_PLANNING` / `C05_PLAN_REVIEW` / `C07_WRITING`；Quality Review 的 `C09_INTERNAL_REVIEW` 有两个 Reviewer 任务，需要分别显式执行一次。Revision、Feedback、Memory 的状态同样以 `status` 实际输出为准。若模型输出被阻断，先查看 Debug，不盲目重复付费调用。

### Gate 1：Plan Approval

在 C06 停下，通过 Workspace 或 trace 检查 Plan：MUST/FORBIDDEN、Knowledge owner、当前状态、Creative Freedom。确认后提交页面实际显示的 Plan 版本：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json --allow-real-provider --worker-stopped approve-plan --chapter 1 --expected-version 1
```

### Gate 2：Draft Acceptance / Revision

Writer 与两个 Reviewer 完成后，人工检查正文和 exact Draft / Review 绑定。需要 AI Review Revision 时，`revise --chapter N --review-id UUID --expected-version N` 走正式 Revision API。需要人工定向修订时，把反馈保存成本机 UTF-8 文件，再执行 `feedback --chapter N --version-id UUID --text 文件路径`。两者都需要前面的 `--allow-real-provider --worker-stopped` 标志；后续每个模型任务仍用 `one-task` 单独启动。

Chapter 04 特别要求：先观察 Draft v1 中的 False Fact Z，提交该章夹具中的 `human_feedback`，确认正式 Revision / Fidelity / Review 后生成 Draft v2。若真实 Draft v1 没有产生 Z，记录该轮污染测试未构成，不能直接修改数据库或伪造生成结果来宣称 PASS。

确认正文可接受后，使用实际 **ChapterVersion UUID**，而不是 version number：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json --allow-real-provider --worker-stopped finalize --chapter 1 --version-id <实际当前-Draft-UUID>
```

`finalize` 走现有 completion API，绑定 exact accepted version 并排队 A07。不会自动 Commit Memory，也不会自行执行 A07。用当前 C14 状态显式执行一个 Memory 模型任务。

### Gate 3：Memory Confirmation

在 C15 停下，逐条检查 Memory Proposal：evidence quote、source ChapterVersion、knowledge owner、SUSPECTS vs truth、状态 before/after、Thread identity、noise、conflict。只列出人工选择的候选 ID：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json confirm-memory --chapter 1 --proposal-id <实际-Proposal-UUID> --candidate <候选-ID-1> --candidate <候选-ID-2>
```

脚本没有“默认全选”。人工决定全部排除时，显式使用 `--confirm-empty`。确认走现有事务化 Memory Commit，只有成功后 Chapter 才能 COMPLETED。下一章 `start --chapter 2`～`5` 必须等上一章 COMPLETED，不能自动批量运行。

## 导出证据

导出只调用正式只读 API，可以在任何 Gate 前后执行，不调用 Provider。选择新的输出文件，避免覆盖已有证据：

```bash
uv run --locked python ../evals/e2e/multi-chapter/run.py --state .runtime/e2e001-manual/project.json export --output .runtime/e2e001-manual/chapter01-plan.json
```

Trace 包含 Input、全部 Plan / Draft 版本、WritingResult、Review、Human Feedback、Revision / Fidelity、Memory Proposal / Commit、Current / Historical Memory、Human Gate、Transition、Audit，以及每个 Task / Run 对应的 PromptLineage、ModelProfile 和 ContextPackage。Context 中保留 included / excluded、priority、authority、source、version；Memory body 保留原文 evidence 和 ChapterVersion 来源。

`memory_density` 仅记录 candidate / committed / excluded / duplicate / conflict 数量，不是质量评分。`execution_kind` 区分无模型尝试、Mock/Recorded、真实 Provider 尝试；报告中的 AI Behavior / Human Prose 均保持待人工确认。某个真实 Provider Run 存在不等于五章 E2E PASS。

使用 [manual-prose-evaluation.md](manual-prose-evaluation.md) 填写每章人工验收，再把 Trace 与根因分析汇入 `docs/reports/E2E-001-multi-chapter-continuity.md`。每次运行只执行明确选择的 suite/case，结束后停止，不自动续跑其他 case 或开始 NOVEL-015。
