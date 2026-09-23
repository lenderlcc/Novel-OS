# Case 01 · Writing 放行与 Draft 生成

日期：2026-09-16。用户授权开放 Writing / Draft 并继续 Case 01。
Workflow：`cc7a88d3-087d-4da6-a540-9a0463eddf46`。
Project：`0767f00f-1d3a-4e82-a779-17e78d4f2888`；Chapter：`ee59f19c-7815-4e91-99ca-619a10ebd311`。

## 放行范围

- 用户已在控制台批准 Plan v2；本次开始时 `approved_plan_version=2`，Writing task 已排队。
- 本机 `backend/config.toml` 从 `planning-only` 切换为 `chapter-writing`，同步重新生成 Docker 的
  `.runtime/config.toml`。不使用环境变量，credential 未改动，本机 config.toml 权限仍为 0600。
  Docker 生成文件沿用既有 0700 外层目录 / 0644 文件设计，供非 root 容器读取。
- API / Host Worker 已重新加载配置。允许 Requirement、Planning、Plan Review、Writing，
  使用 `lingzhi / gpt-5.6-sol`，每个任务最多尝试一次。
- Draft 是 Writing 校验成功后生成的不可变版本，不存在另一个 Draft Agent 权限。
  沿用已批准 Plan v2，没有重新审批或重做 Planning。

## 实际阻塞与最小修复

### Context 预算

原 Writing task `a4c55323-a1f4-4a31-80dc-d4f2baa99263`，Run
`d5072069-a4c7-47c4-9a75-ec38b293952a`，在模型调用前返回 `CONTEXT_BUDGET_EXCEEDED`。

| 项目 | 保守本地估算 |
| --- | ---: |
| CP-005 v3 总预算 | 48,000 |
| Prompt / Schema overhead | 23,539 |
| 输出预留 | 8,192 |
| 必需上下文 | 18,137 |
| 合计 | **49,868** |

估算器使用 UTF-8 字节上界，不代表 Provider 的实际计费 tokens。旧预算不足以容纳正常的中文计划。
新增 CP-005 v4，预算 100,000，与 Planning 使用相同的本地预算量级。
selector、APPROVED Plan、authority、status/version policy、REQUIRED_ONLY 知识策略保持不变。
旧 v3 文件/hash/binding 保留，超大 P0 仍然阻塞，不截断或忽略必需内容。

正常 RESUME 创建新任务和 v4 binding；没有直接修改任务状态或 immutable snapshot。

### Writing 输出操作请求

Task `f55631a7-a606-4f49-957f-7d27a56d92a9` / Run
`b88e24b7-a904-4dd3-89fc-0b130626d4e4` 完成真实模型调用，返回 3,166 字符正文，
但 envelope 附带 `proposed_changes=[{capability:PROPOSE_DRAFT,...}]`。
服务端按原规则拒绝并记录 `AUTHORITY_DENIED`，没有生成 Draft。

旧 Writing Prompt 未明确要求 envelope 的操作数组为空。新增 `write-chapter v2`：

- 顶层 `proposed_changes=[]`、`memory_proposals=[]`。
- PROPOSE_DRAFT 表示返回 `result.content`；应用层负责版本落库。
- 新事实/局部添加只进入 `proposed_new_facts` / `introduced_elements`。
- `scene_id` 与 `planned_function` 从已批准 Plan 精确复制，执行说明放在 execution_summary。

旧 v1 Prompt/hash、输出 Schema、Authority / Service 校验均不变；没有清洗掉非法操作后强行入库。
第二次恢复仍绑定同一 Plan v2，重新生成结果。

## 最终执行结果

**已生成 Draft v1，确定性检查 PASS。** 2026-09-16 11:13:09（Asia/Shanghai）完成。

- Workflow：`C08_DETERMINISTIC_CHECK`，`draft_version=1`。控制台显示“Draft 已生成，本次测试流程结束”。
  数据库存储的 WAITING_AGENT 是现阶段结束点的既有状态；没有后续 pending/running task。
- Plan：current_plan_version=2，approved_plan_version=2。
- Chapter：current_version=1，approved_version=null；正文为 DRAFT，没有自动审批。
- 正文 2,762 字符（包含标点和空白），仅一条 ChapterVersion、仅一条 WritingGeneration。
- `check_status=PASS`、`check_codes=[]`；原始输出的操作数组为空。
- Context CP-005 v4 READY，实际 envelope 估算 50,601；选中的 Plan source_version=2、status=APPROVED。
- `write-chapter v2`；Model Profile `lingzhi-structured`，`lingzhi / gpt-5.6-sol`。
- 正文、content hash、Context package hash、Task/Run/PromptLineage 与 WritingGeneration
  的关系逐项核对通过，原始 provider 正文与不可变 Draft 一致；找到两条相关版本/生成审计。

| 记录 | ID |
| --- | --- |
| Approved Plan v2 | f784571b-928c-4fd3-afcd-af4cce90a441 |
| AgentTask | 2fd5813b-5b08-4725-9813-f62c3d12ff4b |
| AgentRun | ce369307-c233-4028-8797-186e3949f95b |
| ContextPackage | f568b8fa-3b73-4b77-aa70-3dddf653a251 |
| PromptLineage | 60fa07ca-9883-4be0-8b78-c75d0cedc6c4 |
| WritingGeneration | 7440736a-beae-44cc-a4e6-8b00372e7a42 |
| ChapterVersion v1 | 5d47be90-ff62-4014-b3e0-71faec63e4dc |

content SHA-256：`28e3f7b24ca01c31ad94e1145535cc3d4f4d968acd5807f4c9a76e943bd06433`。
完整本机证据保存在 `backend/.runtime/case01-writing/result.json`（0600，不加入 Git）。

本阶段共三条 Writing task / run：一次本地预算阻断（没有模型调用）、一次真实输出权限拒绝、
一次真实成功。**实际 Provider 调用 2 次**；分别报告 usage 总 tokens 15,217 / 14,712。
没有自动技术重试，两次恢复均走有审计的 RESUME；两份失败证据完整保留。

## 人工验收提示

页面已切换到该 Workflow 的“章节正文”。本次内容使用暂用姓名“林峤 / 周遥”和阅览室场景；
原始需求没有提供具体人物或世界背景，Writing metadata 已记录后续需确认/替换这些局部设定。
正文质量、计划执行程度和人物声音等待用户人工验收；确定性 PASS 不表示文学质量评审通过。
未调用 Review Agent / QualityEngine，也未自动推进 NOVEL-009。

## 验证

| 检查 | 结果 |
| --- | --- |
| Context + 全部 Writing + scoped worker + Lingzhi + 新预算回归 | **180 passed, 1 skipped**；付费自动 Writing smoke 未开启 |
| Writing contract + 新预算 + output policy（包含 Prompt v2） | **61 passed** |
| `ruff check` | PASS |
| `ruff format --check` | PASS |
| `git diff --check` | PASS |

日志：`/tmp/case01-writing-validation.log`、`/tmp/case01-writing-envelope-tests.log`。
两个命令覆盖有重叠，不把通过数相加作为独立测试总数。
本次配置/Prompt/profile 修改采用上述定向回归；上次全量 866 passed 不冒充本次全量执行。

新增/更新测试覆盖：中文结构化 Plan + 原生 Schema + 输出预留预算、P0 完整保留、
超大 P0 仍阻塞、旧 v3 hash 与来源策略不变、三处最新 profile 断言、旧 Prompt hash 保留、
v2 输出约定。已有 negative tests 继续拒绝包括 PROPOSE_DRAFT 在内的操作请求，且不产生正文版本。
独立只读复核：两项最小修复均无剩余 Critical / Required。

未引入新依赖、表、migration、Agent 或 NOVEL-009 功能。未提交或推送代码。

## STYLE-001 B2 与测试台工程修复

2026-09-16 的 Style B 重跑暴露了测试台编排问题，而非 Writing 模型错误：

- `planning-only` 是 Worker 领取范围，却被临时当成了人工 Gate。Plan 获批后 Workflow 会正常进入
  `C07_WRITING`，但 Worker 按配置拒绝领取 `WRITE_CHAPTER`，于是 Writing 与 Draft 都停住。
- 两个 Project 都显示为“测试”，下拉框没有稳定标识，导致人工审批落到错误的同名记录。
- 前端只在初次加载时读取执行策略；后端重启或配置切换后，手动刷新仍可能显示旧范围。
- 即使 Writing 未开放，旧 UI 仍允许点击“批准并写作”，能够主动制造悬空的 C07。

修复后，完整 Case 01 始终使用 `chapter-writing`，人工 Gate 单独负责审批阻断。Project 与
Workflow 选项显示 UUID 前八位；审批区再次显示目标 Project / Workflow。手动刷新会重新读取
执行策略，APPROVE 提交前还会再次向后端校验 `WRITE_CHAPTER`，关闭时不发送审批请求。
误审批 Workflow `b740882e-c39e-45a8-959b-7201e2197088` 已取消，未发生模型调用；队列清理后
只留下 B2 的一条 Writing task。

B2 Workflow `da39e1f2-cbd3-4b7d-95e3-63ce7334b48d` 使用人工批准的 Plan v4，单次真实调用成功：

- Workflow 到达 `C08_DETERMINISTIC_CHECK`，Plan current/approved 均为 v4。
- 新建不可变 Draft v2；Chapter `current_version=2`、`approved_version=null`，没有自动批准正文。
- WritingResult deterministic check PASS，`check_codes=[]`，正文 SHA-256
  `5760f35f6dea54b956a0cca5e3eef34a3865b7a0fa81e82c424a7317bca59408`，共 3,105 个字符。
- Provider `lingzhi` / `gpt-5.6-sol`，调用 62,544 ms，11,614 input tokens、4,110 output
  tokens、15,724 total tokens；一次尝试，无重试。
- CP-005 v5 绑定 exact approved Plan v4 和 Project WritingProfile v1；Profile hash 为
  `ac5d7feeb0064f3a26825603d0b4ac5d93718d66637646d5383c17f74acb03cf`。

| B2 lineage | ID |
| --- | --- |
| Approved Plan v4 | `df29fbed-82fa-4739-a201-bbd445bace3e` |
| AgentTask | `9cbf2d69-a963-476f-b51b-8661b32f2fe9` |
| AgentRun | `0b00f01b-d5bb-4eb9-945f-ad6c22144076` |
| ContextPackage | `b0796bb7-c7cc-405e-b1fd-0bfb03c7ff26` |
| PromptLineage | `3fcdadb6-53a1-46af-84db-5f0e966d3e9b` |
| WritingGeneration | `a47f8a0d-27f9-4954-9a8c-6f112846642b` |
| ChapterVersion v2 | `3778093f-6189-4a99-aa16-740bd8a228d5` |

完整只读证据位于 `evals/writing/v0.1/case-01/writing-b-retry/`。回归结果：前端 48 个单元测试、
TypeScript、ESLint、build 全部通过；浏览器 E2E 8/8 通过，覆盖完整审批 Writing、负向审批、
版本冲突、lineage、current/approved 分离和配置文件隔离。人工 A/B 文学质量评价仍待完成。
