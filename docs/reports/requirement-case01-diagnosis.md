# Case 01 Requirement 语义分解诊断与修复

日期：2026-09-15。范围仅 Requirement 诊断、Prompt、Mock 标识及相关回归。
Writing 人工测试和后台 Worker 保持暂停；未开始 NOVEL-009。

## 结论

**原始缺陷已定位，Prompt 和工程校验已修订；真实模型的语义修复效果尚未验证。**

用户看到的 Case 01 不是一次真实模型输出，而是 `mock-default / mock-v1`
生成的确定性合同样例。该样例将整段输入同时复制到 intent、objective、outcome
和一条 MUST，并固定返回 0.95 confidence。Parser 与 Persistence 没有再次改变类别。

本次已授权的一次真实 Requirement 调用返回 `MODEL_TIMEOUT`；未收到模型结果，
未创建 Brief，未执行 Planning / Writing，未重试。不带凭据的官方地址 TLS 连接
检查也超时，不能据此断定密钥无效。后续用户已确认服务商为 Lingzhi，模型列表 GET
返回 200；配置已转为 Lingzhi / GPT-5.6 Sol，见下方增量说明。真实生成仍待新的单次授权。

## 原始 Case 与证据

- Project：`23c028ee-cd94-4965-af85-731e560c9633`
- Workflow：`65f50bbc-8484-4f60-91cd-9f3d5426edfe`
- Requirement Run：`3a1a141d-c31f-4c8f-9859-6830f742b845`
- 原文：`evals/requirements/v0.1/cases/R001.json`，保持四段原文和空行。
- 原文 SHA-256：`82490c0b11dc0722cede763d4558334b04a2f2879b12d5f845603ef84b1fb907`
- 原始 DB / Context / Lineage：`evals/requirements/v0.1/results/before/trace.json`
- 修改前 Provider 重放：同目录 `provider-output.json`。这是按历史 Context 重放的
  Mock 输出，不冒充历史保存的网络响应；解析后的 Brief 与历史 DB 全字段相等。

历史 Context 只有 TASK_INPUT、CHAPTER、PROJECT。新测试保持原文，使用隔离的
测试项目/章节和新 ID；没有覆盖原工作流、批准方案或历史证据。

## Requirement → Provider → Parser → Persistence

| 阶段 | 已检查代码 | 发现 |
| --- | --- | --- |
| Provider 选择 | `runtime_factory.py` | 当前配置选择 Mock；本次真实尝试显式使用既有 OpenAI profile |
| 输出生成 | `agents/provider.py`、`agents/planning_mock.py` | Mock 不理解 Prompt，复制 raw objective，不执行自然语言分类 |
| Prompt | 三个 Requirement 模块的 v1 | 有类别/来源约束，但对原子语义、最小证据、summary 分工和置信度指导不足；不是历史 Mock 输出的执行原因 |
| Parser | `agents/runtime.py`、`prompts/output.py` | JSON 解析、重复键拒绝、Pydantic 校验；无关键词分类或 raw-to-MUST fallback |
| Schema | `agents/planning_schemas.py` | 现有独立字段和分类数组足够承载结果；结构正确不代表语义正确 |
| 业务校验 | `services/planning_policy.py`、`services/planning_results.py` | 校验来源、literal quote、完整 structured Requirement、authority 和升级条件 |
| Persistence | `services/planning_results.py`、`repositories/planning.py` | `output.model_dump(mode="json")` 原样保存 Brief body；Repository 不重新归类 |

因此不能靠修 UI、修改 DB 已有 Brief 或添加中文关键词 fallback 解决根因。

## 本次修改

1. 新增 Requirement Agent、requirement-normalization、parse-chapter-requirement
   三个模块的 **v2**。旧 v1 保持可解析，历史 Lineage 不被改写。
2. Prompt 按完整语义、否定、情态、条件、时间范围分解原子命题；MUST / FORBIDDEN /
   SHOULD / PREFERENCE / PRESERVE 保持不同约束强度。不强制每个类别非空。
3. 明确 Intent、Objective、Required Outcome、Reader Effect 的各自职责；明确
   场景/对话/局部事件创作授权属于 Creative Freedom，其自由度不能改变重大方向或
   覆盖显式时序、已批准/锁定约束。
4. Raw input 的约束使用最小充分连续 quote，保留否定和限定语，维持 `text == quote`
   与源文子串校验。已结构化并批准的 Requirement 保留完整内容及原类别，不擅自拆分。
5. Confidence 按覆盖、解释不确定性、冲突、假设自评；Brief 与 envelope 保持一致。
   区间只用于报告，不声称统计校准；不会把 JSON 合法当成语义理解置信度。
6. Mock 保留工程 fixture 行为，标明 `MOCK_SEMANTICS_NOT_EVALUATED`，confidence
   改为 0（表示未测量语义），不再用 0.95 暗示已理解请求。没有加入 NLP 分类器或
   生产 Case 01 特例。继续使用 Mock 仍不会得到真实语义分解。
7. `RequirementAgentResult` 增加内外层 confidence 一致性校验，拒绝不一致的模型
   输出，避免 Task metadata 与持久化 Brief 出现两个分值。新增两个方向的负例。
   既有 HIGH impact + confidence < 0.6 + unsafe inference 澄清规则保持不变；
   正常业务结果的升级元数据仍由既有最终任务状态决定。

没有 JSON schema 字段形状/API/DB migration/依赖变更；Pydantic 增加跨字段校验。
模型输出的类别是否符合自然语言含义，仍需
真实模型输出与人工评审；现有 Pydantic 和 literal-source 校验不宣称能证明该语义。

## Case 01 应评审的语义

以下是人工评审锚点，不是预先填入真实响应的结果：

| 维度 | 人工锚点 |
| --- | --- |
| Intent | 有限缓和关系，保留未解决张力 |
| Objective | 通过不得不合作的小事推动关系变化 |
| MUST | 关系出现一点缓和；中段小事迫使合作；保留结尾有限变化这一结果 |
| FORBIDDEN | 不直接和解；结尾不彻底说开 |
| SHOULD | 前半段气氛稍紧张 |
| PREFERENCE | 合作中可产生新的认识，不能擅自提升为必然事件 |
| Creative Freedom | 自行设计具体场景、对话和合作事件；不能覆盖关系和时序边界 |
| Evidence | 每项有原文最小充分引用，不能把整段混合强度的原文当一条 MUST |
| Confidence | 解释与证据支持自评分值；一个样本无法证明概率校准 |

## 真实尝试

命令（本次已执行一次，不能自动重跑）：

```bash
uv run pytest tests/core/workflow/test_requirement_semantics.py::test_case01_one_live_requirement_attempt --live-model -s
```

- Profile：`openai-structured`，Model：`gpt-4o-mini-2024-07-18`。
- Endpoint：既有 `https://api.openai.com/v1/responses`，未猜测或发送到其他服务商。
- Prompt：Requirement 三模块 v2；确切 pins / hashes / compiled messages 已保存。
- 结果：1 attempt，`MODEL_TIMEOUT`，pytest 1 failed，30.95 秒。
- 保存目录：`evals/requirements/v0.1/results/20260915T115519Z-356a851a/`。
- `request.json`、`trace.json` 已保存；Provider 未返回结果，因此没有
  `provider-output.txt`、`usage.json`、`parsed-output.json` 或持久化 Brief。
- 仅一次 `AgentWorker.run_once()`，没有循环或 transport retry。临时 schema 已清理，
  超时任务不会被后台 Worker 自动重试。
- API credential 写入 Git 忽略的本机 `backend/config.toml`，权限 0600；没有写入
  Prompt、报告、测试 fixture 或 Git 可提交文件。默认 profile 仍为 Mock。

## Verification

- 重点离线回归：74 passed / 1 live skipped / 275 deselected，75.31 秒。
- 新增离线测试 9 项：Case01 人工标注的完整链路、四种否定/情态样例的保真、Mock
  confidence/升级标记、v2 选择与旧 v1 pin 可解析，以及两个 confidence 不一致负例。
- 补充 confidence 校验后的重点回归：11 passed / 1 live skipped / 340 deselected，
  5.26 秒；包含两种安全低置信度歧义继续处理的既有用例。
- 新增一次显式 opt-in 的真实 Requirement 测试；默认全量测试跳过外部调用。
- 首次按跨目录文件交错传参的组合命令出现 66 个 fixture-not-found setup errors，
  其余 63 passed / 1 skipped；按目录收集重新运行后 74 passed。没有修改 fixture
  基础设施来规避业务失败；以目录收集和全量结果作为正式验证记录。
- 独立 Review 发现并修复内外层 confidence 不一致问题，复核无 Critical / Required。
  删除了公共 metadata 中冗余的 Requirement 特判，复用既有最终任务状态逻辑。
- Docker 后端已重建并启动，容器中三个 Requirement Prompt 模块均为 v2，新的
  confidence validator 已加载。Backend / PostgreSQL 均 healthy，`/health` 与
  `/health/db` 返回 OK；后台 Worker 保持停止。
- 通过当前开发 API 再次对比：原 Case01 Brief body 和原文均未改变，工作流仍为
  `C06_PLAN_APPROVAL`。
- 第一轮全量在补充上述 validator 后主动中止，重新启动最终全量。
- **最终全量 `uv run pytest`：793 passed / 4 live skipped / 2 warnings，532.89 秒。**
  包含 NOVEL-001～008、DEV-UI 只读接口及本次修复的离线测试。两项 warning 为现有
  Starlette/httpx 与 anyio 弃用提示；无失败。日志保存在
  `evals/requirements/v0.1/results/offline-pytest.txt`。
- **`ruff check`：PASS；`ruff format --check`：229 files already formatted；
  `git diff --check`：PASS。**

人工注入结构化响应的测试只证明数据没有被 Parser 或持久化改写，不冒充真实模型
语言理解测试。完整 AI Behavior Acceptance 和 confidence calibration 保持未通过验收。

| 验收层级 | 结果 | 含义 |
| --- | --- | --- |
| Engineering / 数据链路 | PASS | 自动回归、Schema 校验、证据与持久化保真、Docker 健康检查通过 |
| AI Behavior / Case01 真实语义 | NOT VALIDATED | 唯一一次真实调用超时，无模型结果可评审 |
| Confidence 经验校准 | NOT VALIDATED | 仅增加自评指导与一致性校验，尚无独立样本集测量 |
| Human Prose / Writing | PAUSED | 本任务未恢复人工 Writing 测试 |

## 剩余事项与范围

1. 服务商已确认，Lingzhi 模型列表可访问；生成端点和 Structured Outputs 兼容性待实际验证。
2. 获得新的单次调用授权后，使用同一 Case01 原文再次获取真实输出，逐项人工评审。
3. 增加独立语义样本后再讨论置信度的经验校准。
4. Mock 的外层 warning code 只存在于 Provider 输出，现有持久化策略不保存外层
   issue 列表。当前通过 Mock 的 reader-effect 占位文案提示未评估语义，另可通过
   Run provider/model 和 confidence=0 识别；这不是实际读者效果评估。

没有恢复 Writing，没有执行真实 Planning，没有实现 Review Agent、QualityEngine、
Memory 或 NOVEL-009。原始用户工作流和其 Mock 结果保留用于追溯。

## 后续增量：Lingzhi 文件配置与 GPT-5.6 Sol

用户提供 Lingzhi Responses 使用说明，随后要求使用 5.6，且不得使用环境变量。
没有安装或修改 Codex CLI，没有编辑 `~/.codex/config.toml`。

- 只读 `GET https://lingzhi.agibot.com/v1/models` 返回 HTTP 200；5.x 列表包含
  `gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.5`，没有 `gpt-5.6` 通用别名。
  使用旗舰档 `gpt-5.6-sol`，模型定位参考
  [OpenAI 官方模型文档](https://developers.openai.com/api/docs/models/gpt-5.6-sol)。
- 本机 `backend/config.toml` 设置 `requirement_smoke_profile = "lingzhi-requirement"`、
  `lingzhi_base_url = "https://lingzhi.agibot.com/v1"`，使用单独的 `lingzhi_api_key`。
  用户提供的 Lingzhi 密钥已从误用的 `openai_api_key` 字段迁移，防止再发往官方端点。
- `agent_model_profile` 保持 `mock-default`；单次测试档案不会启动后台真实调用。
- 新 Profile 的 provider 为 `lingzhi`，model 为 `gpt-5.6-sol`，timeout 120 秒，
  max_output_tokens 8192；不覆盖 temperature，保留服务端默认生成参数。
- 复用 Responses adapter，保留 HTTPS、无 redirect、无 retry、`trust_env=False`、
  `store=false`、响应大小上限和本地 Schema 校验。Provider 只允许绑定其固定的可信地址；
  Lingzhi 的模型来源明确记录到 Run/PromptLineage，不标成 OpenAI 官方调用。
- 旧四个 ModelProfile 的内容和 hash 保持不变。新增 nullable temperature 仅允许新
  profile 省略采样覆盖，旧 profile 仍显式传 0.2。
- One-shot Capture 使用配置选择 Provider；保存实际 base URL；第二次执行会在传输前
  拒绝。离线完整链路验证已覆盖 Lingzhi lineage、一次性限制、密钥不进入证据文件、
  无 Planning / Writing 产物。
- 本轮专项回归：Provider/Prompt/配置 **109 passed / 1 skipped**；Requirement/Lineage
  **38 passed / 1 skipped**；Ruff check、format check（230 files）、diff check 通过。
  上文 793 passed 是接入 Lingzhi 前的全量记录，本轮没有把它冒充新 Provider 的真实验收。
- 本轮新增真实生成调用数：**0**。只读取模型列表，不生成内容；后台 Worker 继续停止。

独立 Review 复核无 Critical / Required。Docker 已更新，容器读取到
Lingzhi / gpt-5.6-sol、正确 base URL 和独立凭据，后台 provider 仍为 Mock。
`/health` 和 `/health/db` 均 OK。模型生成仍未执行，等待新的单次授权。
