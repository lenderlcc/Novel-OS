# E2E-001 人工验收记录

复制到忽略的 `.runtime/e2e001-manual/`，每章填写一次。采用 PASS / FAIL / NOT RUN 与具体证据，不做数字质量评分。Engineering Acceptance、AI Behavior Acceptance、Human Prose Evaluation 分开记录。

- Project ID：
- Chapter ID / sequence：
- Workflow ID：
- Provider / model / ModelProfile hash：
- Plan ID / version：
- Draft v1 ID：
- Revision / Fidelity result ID（如有）：
- Finalized ChapterVersion ID / version / content hash：
- Review ID / source ChapterVersion ID：
- Memory Proposal ID / Commit Batch ID：
- Planning / Writing ContextPackage ID / hash：
- Trace 文件：
- 人工验收者 / 时间：

| Gate | 人工决定 | exact version / candidate IDs | 理由与 evidence |
|---|---|---|---|
| Plan Approval | 未决定 | | |
| Draft Acceptance | 未决定 | | |
| Memory Confirmation | 未决定 | | |

| Continuity / AI Behavior | Result | Evidence / Failure layer |
|---|---|---|
| 当前人物位置、持有物、Object K 状态正确 | NOT RUN | |
| A knows X；B 未获得 X，不将 Global Canon 当成 B 的已知事实 | NOT RUN | |
| A 的 SUSPECTS / BELIEVES 没有晋升 Canon truth | NOT RUN | |
| T 隔章仍 OPEN；新证据更新同一 logical thread | NOT RUN | |
| 当前 Context 排除 superseded state，但历史可追溯 | NOT RUN | |
| Finalized v2 来源准确；Rejected / Superseded Draft 的 Z 未进入 Memory | NOT RUN | |
| Derived Summary 忠实，没有新增事实或覆盖高 Authority | NOT RUN | |
| Context 包含必需状态而不加载全部历史正文 | NOT RUN | |
| 相关 Memory 自然使用，没有逐条展示记忆 | NOT RUN | |

Memory Proposal 观察：

- Good candidates：
- Missing candidates：
- Wrong candidates：
- Noise candidates：
- Authority problems：
- Knowledge problems：
- Candidate / committed / excluded / duplicate / conflict count：

ContextPackage 观察：

- Required context missing：
- Irrelevant context included：
- Knowledge / future leak：
- Duplicate context：
- Context too large：
- Include / exclude reason、source version 是否可解释：

Human Prose 只做基本 sanity check，本轮不继续调 Writing Prompt / Quality Taxonomy。

| Prose observation | Result | 原文最小引用 / 说明 |
|---|---|---|
| Plan adherence / required outcome | NOT RUN | |
| Mechanical plan expansion / major deviation | NOT RUN | |
| Knowledge leak / over explanation | NOT RUN | |
| Emotion labeling / uniform rhythm | NOT RUN | |
| Template transition / dialogue functionalization | NOT RUN | |
| Character voice collapse / excessive closure / over-signposting | NOT RUN | |

失败定位层：Extraction / Commit / Query / Context Selection / Prompt Use / Writer。写明具体 Task / Run / source version，不能只写“Memory 不好”。

- Failure tag：
- Failure layer：
- Expected / actual：
- 最小可复现步骤：
- Blocking / required correctness fix / Phase 2 candidate：
- 本章 Engineering Acceptance：
- 本章 AI Behavior Acceptance：
- 本章 Human Prose Evaluation：
- 五章总结果：待五章完整证据后填写 PASS / PASS_WITH_BLOCKERS_RESOLVED / FAIL。
