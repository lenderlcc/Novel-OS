# NOVEL-005 — Prompt Runtime & Model Provider

日期：2026-09-11。开发分支：`wfg/novel-005-prompt-runtime`。基线：`31d298b`，已审查的 NOVEL-004。
状态：实现、验证与独立只读审查完成。未进入 NOVEL-006，等待用户 Review。

## 1. Implementation Summary

实现版本化、组合式 Prompt Runtime、统一模型请求/响应、Mock 与 OpenAI Responses Adapter，
以及每次执行的不可变 PromptLineage。复用原 AgentTask、AgentRun、Worker、ResultHandler 和
Workflow 的权限、租约、重试、幂等、人工审批与 stale result 保护。

新增内容按职责分组：

| 路径（相对仓库根目录） | 内容 |
| --- | --- |
| `backend/novel_os/prompts/` | module contracts、Git registry、compiler、output contract、task definitions、prompt/model orchestration |
| `backend/novel_os/prompts/library/` | 10 个 v1 module 的 manifest 与 Markdown 正文 |
| `backend/novel_os/providers/` | provider contract、error policy、profiles、default adapter、OpenAI adapter |
| `backend/novel_os/domain/prompts.py` | 纯 Domain PromptLineage |
| `backend/novel_os/models/prompts.py` | Lineage ORM |
| `backend/novel_os/repositories/prompt_lineages.py` | 持久化、历史摘要校验、事务锁 |
| `backend/novel_os/services/prompt_lineages.py` | 租约校验、绑定事务、审计、读取 |
| `backend/novel_os/api/prompt_schemas.py` | 独立 API DTO |
| `backend/novel_os/agents/demo_schema.py` | RequirementSpec / SmokeAgentResult |
| `backend/novel_os/runtime_factory.py`、`prompt_demo.py` | 配置装配、隔离 demo CLI |
| `backend/alembic/versions/0006_prompt_runtime.py` | 增量 frozen DDL |
| `backend/tests/prompts/`、`tests/core/workflow/test_prompt_*.py` | 单元、服务、数据库、API、迁移与并发测试 |

局部修改：AgentRuntime / Mock provider、既有阶段映射名称、Worker / Queue / ResultHandler 接入点、
API 路由、Alembic metadata 注册、TOML 配置 / Docker 配置渲染、日志等级、测试和 README。

依赖：将已经锁定的 `httpx 0.28.1` 从 dev 移到 production dependencies，支持 HTTP Adapter。
未引入供应商 SDK，也未升级其他依赖；lockfile 仅改变 httpx 所属依赖组。

## 2. Prompt Runtime Architecture

```text
Workflow → AgentTask
→ Worker → Queue claim/start（短事务）
→ AgentRuntime / AuthorityValidator
→ TaskDefinitionRegistry → PromptRegistry → PromptCompiler
→ ModelProfileRegistry → ModelRequest
→ PromptLineageService.bind（短事务，先于模型调用）
→ DefaultAdapter → ModelProvider / vendor Adapter（事务外）
→ ModelResponse → JSON parser → 同一 Pydantic model
→ AuthorityValidator → ExecutionResult
→ 原 ResultHandler → 原 WorkflowRuntime（原子应用事务）
```

Domain 不依赖 FastAPI/ORM。Compiler/Provider 不查询 DB 或 Memory。Repository 不 commit/rollback。
Provider 不选择 Workflow event，不创建内容版本，不修改审批或 Canon。

## 3. Prompt Module Format

每个版本独立目录含 `manifest.json` 和 `content.md`。metadata 必须显式声明 module_id、module_type、
version、status、description、content_path、dependencies、compatible_agents、compatible_task_types、
created_at 和 content_hash。额外字段、重复 JSON key、非法类型/版本/状态/摘要会被拒绝。

ModuleType：SYSTEM_POLICY、AGENT_ROLE、TASK_TEMPLATE、SKILL、QUALITY_PROFILE。
状态：DRAFT、EXPERIMENTAL、STABLE、DEPRECATED、RETIRED。version 为正整数。
依赖使用 exact module ID/version，不能依赖模糊的 stable 指针。

## 4. Prompt Directory Structure

```text
backend/novel_os/prompts/library/
  system/novel-os-core/v1/
  agents/simulation-role/v1/
  agents/requirement-demo-role/v1/
  tasks/simulation-{ack,plan,draft,review}/v1/
  tasks/requirement-demo/v1/
  skills/structured-reporting/v1/
  quality/runtime-quality/v1/
```

沿用 NOVEL-003 的 package resource 布局，资源随 wheel / Docker 安装，避免依赖仓库工作目录。
不含 Project、Chapter、人物、Canon 或用户反馈等具体内容。

## 5. PromptRegistry

从 Git 文件加载正文，校验 metadata、正文 hash、重复 ID/version、依赖缺失/循环、文件路径边界。
只允许读取 library 内的 Markdown 正文。加载完成后保存不可变 resolved module；不会在模型调用期间
重新读取同一路径而更换内容。`reload()` 先完整校验再替换 registry，不半更新。

同版本只允许调整 status，不能借更新 manifest hash 修改正文或其他执行 metadata。
跨进程重启后，exact resolve 的 expected_hash / expected_execution_hash 校验及 LineageService
的数据库历史比较保护正文与执行 metadata。后者在模型调用前检查，覆盖新进程和并发 Worker。

## 6. Prompt Version Resolution

未指定版本：选择该 module 最高的 STABLE version。EXPERIMENTAL 不替代 STABLE；DRAFT、
DEPRECATED、RETIRED 均不参与默认选择。exact 查询允许读取历史 metadata；RETIRED 拒绝新编译。
显式选择其他非 retired 版本可用于受控测试，不改变默认选择。

编译时 stable 立即解析为具体 version/hash。已准备的请求持有该不可变组合；后续 registry reload
不会改变它。新尝试可选择新 STABLE，旧 Run 的 Lineage 不变。没有回填旧 Run 的隐式升级。

## 7. PromptCompiler

接收已解析模块、agent/task identity、可信 scope、constraints DATA、调用方提供的 context_payload
和 OutputContract。输出 provider-neutral messages、模块集合、contract 和 compiled hash。

Compiler 是纯函数式装配，不读取 session、人物、事件、Memory 或 Canon，不做 retrieval、ranking 或 token budget。
错误组合在执行前失败；不允许调用者用传入数组的次序改变层级。

## 8. Compilation Order

固定顺序：System Policy → Agent Role → Task Template → Skills → Quality Profile →
Authority/Constraints → Context DATA → Output Contract。

非 Skill 的静态层必须恰好一个模块；Skill 按 module ID/version 排序，重复模块拒绝。
编译时检查层类型、Agent / Task 兼容范围、依赖是否完整包含、retired 状态与内容摘要。

## 9. Prompt Hash Design

SHA-256 输入包括 compiler version、agent/task type、精确模块 pins、固定顺序的 messages、
schema ID/version。正文和字符串规范化 CRLF/CR 为 LF；JSON key 排序、固定分隔符，禁止 NaN。

request_id、timestamp 和 transport metadata 不进入 hash。Context 的实际数据仍进入 hash。
同内容的新 module version 会产生不同 compiled hash。模型 Profile 单独保存 hash 与完整安全参数。
当前 compiler_version 为 2。每个 pin 的 execution_hash 是除 status 外全部 manifest 字段的规范化
SHA-256，包含正文 hash、module_type、依赖、兼容范围等；不用手工维护第二份摘要。状态晋升不改变
执行摘要。即使最终 messages 相同，依赖或兼容性变化也改变 compiled hash，并触发同版本历史冲突。

## 10. PromptLineage

一条 Lineage 对应一个 Run，保存 task/run/lineage IDs，system/role/task/skill/quality 的
exact module ID/version/content_hash/execution_hash，schema ID/version/hash，模型 Profile ID/hash/安全参数快照，
compiler version、compiled hash 和 DB 时间。

不保存 Prompt 正文、完整 Context、Provider raw body、headers 或 API Key。
历史正文依赖 Git 中对应版本；Lineage 用于追溯执行配置，不保证重新运行模型生成相同文字。

## 11. TaskDefinitionRegistry

描述 agent/task type、五类 Prompt references、OutputContract、模型 Profile、capabilities 和
retry policy 标识。实际尝试预算仍属于持久化 AgentTask。

13 个现有 MOCK_* Task 使用 simulation prompts。额外 INTERNAL_SMOKE_TEST 只供隔离 CLI demo，
不加入 Workflow scheduler，也不创建新的 Agent identity。

原 `agents.registry.TaskDefinition` 更名为 `StageTaskMapping`，保持既有状态/事件映射不变。
新 TaskDefinition 不包含 state、next_state、next_event 或 success_event。

## 12. Output Contract Generator

`OutputContractGenerator` 调用正式 Pydantic model 的 `model_json_schema()`，生成 canonical JSON Schema。
Compiler 将其直接嵌入 Output Contract。Parser 保存并使用同一个 model 类进行 `model_validate()`。

现有 Workflow Task 使用原 AgentResult；demo 使用其严格子类 SmokeAgentResult / RequirementSpec。
没有第二份手写 JSON Schema。OpenAI schema dialect 转换仅由生成的 schema 派生。

## 13. ModelProfile

Git 文件 `providers/profiles.toml` 当前只有两个 Profile：

| Profile | Provider / Model | 能力 |
| --- | --- | --- |
| mock-default | mock / mock-v1 | text；本地结构化校验 |
| openai-structured | openai / gpt-4o-mini-2024-07-18 | text + native structured output |

均配置 timeout=30 秒、max_output_tokens=4096、temperature=0.2，stream=false。
校验 ID、能力声明、参数范围与 support flag 一致性；不在 Profile 中放密钥。
Snapshot/hash 记录执行时参数，后续 Profile 文件变化不改写历史配置。

## 14. ModelProvider Interface

统一 `generate(ModelRequest) → ModelResponse`、`generate_structured`、`get_capabilities`。
`stream` / `count_tokens` 保留明确的 unsupported 接口，返回不可重试 MODEL_INVALID_REQUEST，
不伪造估算结果或声称已实现流式执行。

DefaultAdapter 在调用前校验 provider identity、Profile 所需能力和结构化支持。
无供应商 SDK 类型进入 Worker、AgentRuntime、Compiler 或 Workflow。

## 15. ModelAdapter

DefaultAdapter 处理能力匹配与统一调用。OpenAIAdapter 集中处理 role/input 映射、text.format、
generation 参数、正文抽取、usage、完成原因和错误。

OpenAI 使用生成的 Pydantic tagged union schema 派生 native dialect：带 discriminator 的 oneOf
转换成 anyOf（各分支 required literal kind 互斥），const 转成单值 enum；返回后仍按原 model 校验。
接口字段依据 [OpenAI Structured Outputs 官方文档](https://developers.openai.com/api/docs/guides/structured-outputs)。

## 16. MockModelProvider Integration

保留 NOVEL-004 所有 scenario 和持久化 attempt_number 语义。Mock 接收完整 ModelRequest，
包括 CompiledPrompt、OutputContract 和 ModelProfile，返回统一 ModelResponse。

Malformed / authority violation / quality failure 都走原 parser、validator、handler，没有 `if mock`
绕过编译或验证的路径。原测试 double 只调整为返回 ModelResponse；既有业务断言未弱化。

## 17. Real Provider Integration

实现固定 `https://api.openai.com/v1/responses` 的 HTTP Adapter。使用 `text.format` 的 native JSON Schema，
`store=false`，禁用 redirect、HTTP 客户端内部重试与环境 proxy 配置。设置 socket timeout，读取响应时
检查总耗时与 2 MB 响应上限；任何结构化结果必须再经本地校验。

真实调用通过本地 TOML 的 `agent_model_profile="openai-structured"` 与 `openai_api_key` 显式启用。
CI 默认 Mock；HTTP 格式通过 MockTransport 覆盖。未配置真实密钥，因此本次没有验证云端账号/模型可用性。

## 18. ModelResponse

包含 content、provider、model、TokenUsage(input/output/total)、finish_reason、latency_ms 和内存 metadata。
实际持久化只采用第二次 allowlist 处理后的有限非负 token 数、latency、固定 finish reason。

忽略供应商回显的 model 名称、response ID、headers 和任意 metadata；Run 的模型标识来自已验证 Profile。
Mock 不伪造真实 token 计费数，usage 为 null。

## 19. Error Normalization

| 错误 | Retryable |
| --- | --- |
| MODEL_AUTH_ERROR | false |
| MODEL_RATE_LIMIT | true |
| MODEL_TIMEOUT | true |
| MODEL_UNAVAILABLE | true |
| MODEL_INVALID_REQUEST | false |
| MODEL_CONTEXT_LIMIT | false |
| MODEL_OUTPUT_INVALID | true |
| MODEL_CONTENT_BLOCKED | false |
| MODEL_PROVIDER_ERROR | false |

认证失败不盲目 retry；insufficient_quota 映射为不可重试参数/配置错误。
OpenAI HTTP 200 的 failed 响应也按 error.code 规范化：server_error → MODEL_UNAVAILABLE，
rate_limit_exceeded → MODEL_RATE_LIMIT，均使用已有技术重试预算；不误落到不可重试的未知错误。
原 FORMAT_ERROR / SCHEMA_PARSE_ERROR 继续进入技术重试，同 Task / 新 Run。超过预算才终结。
Prompt 配置冲突不发起模型请求，以 PROMPT_CONFIGURATION_ERROR 终结当前 Task。
未知供应商错误不泄漏原始异常。Worker 不分析 SDK 异常字符串。

## 20. Structured Output Validation

处理顺序：ModelResponse → 字符串/150,000 字符上限 → 拒绝重复 key 的 JSON parser → 同一 Pydantic
model → SUCCESS output kind 与 task contract 匹配 → AuthorityValidator。ResultHandler 仍在应用边界再校验。

NaN/Inf、非法正文、额外字段、伪造 APPROVED/authority、next_state/next_event、跨 task/target proposal
继续拒绝。Provider native structured output 不替代这条链路。

## 21. Prompt / Context Trust Boundary

Context 使用独立 user message、`UNTRUSTED_DATA_ONLY` 与 JSON data 包装，不能插入新的 message role。
System Policy、Role、Authority、Output Schema 不从 Context 读取。Constraints 同样明确标为 DATA，不能授予权限。

注入语句被保留为数据供模型理解；不能保证模型永远不受文字诱导，但即使模型返回非法操作，原 schema、
capability validator 与系统固定 event mapping 仍会阻止审批、状态伪造和越权持久化。

## 22. Secret Handling

Settings 继续只读取 TOML / 显式参数，环境变量和 dotenv 无效。API Key 使用 SecretStr。
prepare_docker 省略 None，并仅在受保护的配置文件 sink 解封 SecretStr；权限沿用私有父目录和容器只读挂载。
PostgreSQL 专用 credential 文件不会获得 API Key。

不记录 exception string、validation input、raw output 或 provider headers。即使 application DEBUG，
httpx/httpcore 保持 WARNING，避免供应商 header/reason phrase 进入 wire diagnostics。
凭据、含引号/反斜线/变量样式的字符串 roundtrip 已覆盖。

## 23. Persistence

仅新增 `prompt_lineages`。复合 FK `(agent_run_id, task_id)` 保证同 Task；run 唯一绑定一个 Lineage；
DB trigger 禁止 UPDATE/DELETE，hash/version 有基本 CHECK。无 Prompt body 表。

Binding 采用 Project → Workflow → Task 锁顺序，重新核验 status、owner/token、attempt 和 DB 租约时间。
同一 module/version 的首次发布按排序获得 PostgreSQL transaction advisory locks，防止不同 Project 的
并发 Worker 发布冲突 hash。历史比较只查询 metadata；Repository 不自行结束事务。
比较包括正文和 execution hash；SQL 使用 IS DISTINCT FROM，缺少执行摘要的旧 pin 也不能被当成
相同定义。新字段存入现有 JSONB，无 DDL 变化，无历史回填，0001..0006 migration 文件保持不变。

Lineage 与 Audit 同事务，先提交再调用 Provider。审计失败则一起回滚，不出现部分绑定。
模型标识在 claim 创建 Run 时写入，不修改原 AgentRun immutable trigger 或历史输入 metadata。

## 24. API / Inspector

`GET /api/v1/agent-runs/{run_id}/prompt-lineage` 返回独立 DTO，包含精确 pins、Schema/Profile 摘要与安全参数。
不返回 ORM，不暴露 prompt/context/secret。未知 Run 或尚无 Lineage 返回统一 404。

无 Prompt Preview、Prompt 编辑、Task 创建或新的权限写入 API。旧 Run 不自动回填 Lineage。
隔离 demo 入口为 `python -m novel_os.prompt_demo --text ...`，没有数据库交互。
旧 compiler v1 Lineage 仍可读取；若 pin 未记录 execution_hash，响应显式返回 null。新编译使用
严格的 ModulePin，必须带 execution_hash，不因历史 DTO 的兼容性而放宽运行时绑定。

## 25. Tests Added

新增测试覆盖：registry metadata/duplicate/hash/dependency/stable/exact/lifecycle、compiler 顺序/规范化/注入、
Pydantic 来源、Profile/capability、Mock/真实 Adapter 共用运行时、全部错误类别、凭据、response bound、
API inspector、Run history、并发、回滚、复合 FK、迁移与旧 Worker 回归。
本轮 Review 修复新增 HTTP 200 临时故障的分类/恢复、metadata 变化后的摘要/历史冲突、并发
metadata 首次发布、状态晋升摘要不变、旧 Lineage 读取和缺失摘要拒绝等回归。

| 测试文件 | 重点 |
| --- | --- |
| `tests/prompts/test_registry.py` | 模块合法性、版本 coexist、reload 与历史摘要 |
| `tests/prompts/test_compiler.py` | 固定顺序、确定性、Schema 来源、Context trust、分层 |
| `tests/prompts/test_providers.py` | Mock/native adapter、错误、能力、秘密、demo、opt-in smoke |
| `tests/core/workflow/test_prompt_lineages.py` | 事务、API、历史、重试、秘密、租约、stale、并发 |
| `tests/core/workflow/test_prompt_migration.py` | 带数据 roundtrip、旧记录快照、metadata drift |
| `tests/test_config.py`（扩展） | 可选 secret / 特殊字符 / Docker TOML roundtrip |

## 26. Prompt Versioning Test Result

PASS：v1 STABLE + v2 EXPERIMENTAL 仍选择 v1；晋升 v2 后新编译使用 v2，旧 prepared request 和已存 Run
仍绑定 v1。正文不同但 version 未变，文件 hash、reload 或历史 pin 校验拒绝。
新进程即使同时改写 manifest hash，仍在与旧 Lineage 比较时拒绝模型执行。

## 27. Prompt Hash Test Result

PASS：输入 module 数组倒序、JSON key 插入顺序变化、CRLF/LF、不同 request_id/timestamp 不改变摘要。
真实 Context 变化、新 module version 均改变摘要；output schema hash 单独记录。

## 28. Structured Output Test Result

PASS：有效 Mock/native HTTP 输出生成 AgentResult；格式错误、重复 key、额外字段及不符 Schema 的 native 输出
均拒绝并走技术重试。RequirementSpec demo 成功，simulation=true，无业务持久化。

## 29. Provider Error Test Result

PASS：全部九类错误的持久化 Worker 路径均已测试。可重试错误记录 FAILED Run 后，新 Run 可正常成功；
不可重试错误一次终止，无无限重试。HTTP status、timeout/connect、refusal、incomplete 和 malformed body 有单元覆盖。

## 30. Secret Leakage Test Result

PASS：模拟密钥没有出现在 caplog、AgentTask、AgentRun、PromptLineage、AuditRecord 或 inspector response。
原始 metadata / usage / finish reason 的异常输入经过 allowlist，不能把字符串型敏感值写入运行摘要。
Docker 配置保留实际 key，None 不写 TOML null，环境变量不覆盖文件。

## 31. Prompt Injection Test Result

PASS：Ignore previous instructions、Approve this plan、Set state completed、system administrator、伪造 role/next_state/
next_event/capabilities 都只进入 Context DATA；可信 instructions / authority / contract 不变。
NOVEL-004 越权与伪造输出测试继续通过，结果 handler 与审批控制权未改变。

## 32. Mock E2E Result

PASS：原完整 Worker Mock E2E 经过 C06 和 C12 两个人工审批 Gate 到 C16；租约恢复、进程执行、
技术重试、quality failure、cancel/stale、内容校验均保持原语义。C14/C15 仍只模拟交接，不写 Canon。

本地 CLI demo 返回 SUCCESS RequirementSpec。wheel 在仓库目录外解包后执行相同 demo 也通过，
确认 10 manifests、10 bodies、profiles.toml 全部包含在打包产物内。

## 33. Real Provider Smoke Result

默认测试：SKIP，必须显式 `--live-model` 才进入真实请求分支。
另执行 `pytest tests/prompts/test_providers.py -m live_model --live-model`：1 skipped，原因是本地 TOML 未配置密钥。
没有发起真实模型请求或产生模型费用。云端实网 smoke **未验证**，不以 MockTransport 结果代替实网结论。

## 34. Migration Result

开发库显式执行并通过：

```text
alembic upgrade head     0005_agent_runtime → 0006_prompt_runtime
alembic downgrade -1    0006_prompt_runtime → 0005_agent_runtime
alembic upgrade head    0005_agent_runtime → 0006_prompt_runtime
alembic check           No new upgrade operations detected.
```

Review 修复后再次执行 upgrade head（已在 0006）、downgrade -1、upgrade head、alembic check，
全部通过，最终 head 仍为 0006_prompt_runtime；此修复无 DDL 变化。

开发库降级前检查新表为 0 行。独立测试还使用真实 Core/Workflow/Task/Run/Audit 数据验证往返：
只删除 Lineage 表，其他表逐行快照相同，再升级后 Worker 继续运行。旧 0001..0005 文件未改写。
降级会删除 Lineage 数据，不会自动恢复；生产有运行记录时不应把它当作无损回滚。

## 35. Full pytest Result

Review 修复后执行 `uv run --locked pytest -q --tb=short --show-capture=no`：
**430 passed, 1 skipped, 2 warnings in 112.34s**。
原有 326 项回归全部通过；NOVEL-005 共新增 104 项通过（含本轮 13 项回归），
另 1 项真实调用 smoke 按默认策略跳过。日志：`/tmp/novel005-review-fix-pytest.log`。

新增回归在修复前执行时，11 个用例失败，覆盖两个原缺陷及 metadata 并发首次发布；
修复后 Prompt/Lineage/Migration 定向验证为 102 passed、1 skipped。

首轮全量发现可选 API Key 在 Docker TOML 中被渲染为 null，导致 3 个旧配置测试失败；已修复并新增两项回归。
既有 TestClient/httpx 和 AnyIO 弃用提示仍有 2 条，不为本阶段升级稳定依赖。

## 36. Lint Result

`ruff check`：PASS。`ruff format --check`：PASS，142 files already formatted。
`git diff --check`：PASS。`uv build`：PASS，sdist 与 wheel 均成功。
Docker build backend：PASS；容器及 health / health/db 结果：Healthy；GET `/api/v1/health` 返回 `{"status":"ok"}`，
GET `/api/v1/health/db` 返回 `{"status":"ok","database":"ok"}`。

## 37. Acceptance Criteria PASS / FAIL

| 用户列出的验收项 | 结果 |
| --- | --- |
| 1–5：合法模块、非法 metadata、重复版本、同版本内容冲突、未知依赖 | PASS |
| 6–9：stable / exact / experimental / deprecated / retired | PASS |
| 10–13：固定编译顺序、稳定 hash、版本敏感、排除 transport 动态值 | PASS |
| 14–18：同一 Pydantic contract、合法/非法结果、Mock 完整链路 | PASS |
| 19–23：Profile、unsupported capability、统一错误与重试 | PASS |
| 24–26：log / DB / Lineage 无 secret | PASS |
| 27–30：Context 不能改权限、state/event、不能自批 | PASS |
| 31–33：精确 Lineage、stable 变化后历史保留、正确 Run/Task FK | PASS |
| 34：同一 AgentRuntime 的 Mock + Real Provider abstraction | PASS（真实 HTTP Adapter 由 MockTransport 验证） |
| 35：真实 smoke opt-in，无凭据跳过 | PASS（实网结果未验证） |
| 36–39：Worker / stale / Workflow ownership / 原 001–004 回归 | PASS（原有 326 项全部通过） |
| 独立只读 Review；Required/Blocking 修复 | PASS |
| 无 006/007 及之后的业务实现 | PASS |

并发验证：同 Run 双重 bind 只产生一条 Lineage；不同 Project 同版本不同 hash 并发绑定时，只有一个成功，
另一个 VERSION_CONFLICT。两个事务完成，无死锁，历史不被覆盖。

## 38. Architecture Deviations

实施前/过程中已说明并局部处理的冲突：

1. **迁移编号占用**：请求写 0005_prompt_runtime，但现有 0005_agent_runtime 已发布；根因是前期 Review
   修复占用了额外 revision。只新增 0006，不覆盖旧链；影响限编号与验证起点。
2. **TaskDefinition 职责冲突**：004 同名类型保存阶段与事件映射。局部更名为 StageTaskMapping，新增
   不含事件的 execution TaskDefinition。没有改变任何已有 Workflow 转换。
3. **Run identity immutable**：运行后补写 model/input metadata 被旧 DB trigger 拒绝。改为 claim 创建 Run
   时写模型标识，Lineage 独立外键绑定，原 trigger 不变，历史不回填。
4. **TOML optional secret**：新增 None/SecretStr 需要 Docker renderer 省略空值并在保护文件 sink 解封；
   只改序列化细节，保留配置来源、权限和服务凭据隔离。

本轮用户 Review 确认并修复两项 P2：HTTP 200 临时 Provider 错误误判终态，以及 fresh Worker
未校验同版本执行 metadata。新增回归先在原实现上复现失败，再验证修复；未重构原 Workflow、
Agent 租约、结果处理或表结构。Provider 分类与 metadata 修复分别交由独立 reviewer 复核，
均未发现剩余 Required；另分别定向验证 13 和 47 项通过。

## 39. Known Issues

- 无已知阻塞 NOVEL-005 的实现问题；实网 Provider 调用未验证，账号/网络/模型可用性仍需配置凭据后 smoke。
- 本地单用户 Prototype 的既有身份模型保持，没有新增多租户鉴权。
- 不保存完整 Context，不能只凭 DB 重建当时全部输入；精确模块和执行配置可追溯，正文需对应 Git 版本。
- 历史 hash 比较扫描 Lineage metadata，公共模块的首次绑定事务会短暂串行化；未做大规模运行历史性能优化。
- 新进程重载依赖 Git 与持久化 pins；不实现文件 watcher 或在线 Prompt 发布管理 API。
- 修复前的旧 pin 没有 execution_hash 时无法恢复其历史 metadata；保留原记录并拒绝复用这种
  未知定义，需要为涉及模块发布新版本。升级前应停止旧 Worker。本机开发库修复前为 0 条 Lineage。
- 只有当前两个 Profile，一个 Worker 同时执行一个任务；尚无流式输出、token counting、生产 Worker supervision。
- 两条既有依赖弃用 warning 保留。

## 40. Deferred Items

未实现 NOVEL-006 Context Engine、MemoryQueryService、context profiles/retrieval/ranking/token budget、
未来知识过滤、人物知识检索、Canon search 或 Vector Retrieval。

未实现 NOVEL-007 CreativeBrief / Requirement workflow / Planning vertical slice，未实现 008 Writing、
009 Review、010 Revision、011 Feedback、012 Memory Commit 的真实业务能力。

未引入 Vector DB、Redis、Kafka、Graph DB、Frontend。Prompt demo 只验证运行时，后续开发等待用户 Review。
本阶段不自行提交、推送、合并或继续 NOVEL-006。
