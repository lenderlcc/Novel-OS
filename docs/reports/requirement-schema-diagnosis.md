# Requirement Schema 失败诊断

日期：2026-09-15。范围仅 Requirement；未继续 Planning/Writing。

## 当前结论

**具体校验根因尚未确认，不能宣布修复。** 已确认真实模型返回了文本，错误发生在
本地结果验证链路。旧代码没有保留响应原文或具体 Pydantic 错误，无法根据
`SCHEMA_PARSE_ERROR` 推断是哪一个字段、跨字段规则或写入前检查失败。

本次先补齐默认关闭的本机诊断捕获，以便取得下一次人工授权调用的原文，再离线
重放定位。没有放宽 Schema、加入 fallback、修改分解规则或硬编码 Case 01。

## 已确认的证据

- Workflow：`57098d06-dc8f-47e2-b766-56db9eb295f3`
- Task：`828bdf38-ab0a-40f1-933e-5bc1d55da34f`
- Run：`9cce21e3-b680-4ea0-924d-8cb1282e085a`
- 类型：`PARSE_CHAPTER_REQUIREMENT`；provider `lingzhi`；model `gpt-5.6-sol`。
- 一次尝试，Provider latency 56,647 ms；input 10,515 / output 2,380 / total 12,895 tokens。
- 错误：`SCHEMA_PARSE_ERROR`。这与此前 Docker DNS 导致的 `MODEL_UNAVAILABLE` 不同。
- Run 只保留安全模型摘要，不含原始响应和具体字段错误。普通 JSON 格式错误另映射
  为 `FORMAT_ERROR`；不能因此进一步推定失败的是 text/quote 或 confidence。
- 网关只读个人日志查询未获管理访问权限，未取得历史响应；未尝试绕过权限。
- 原始输入 SHA-256：`82490c0b11dc0722cede763d4558334b04a2f2879b12d5f845603ef84b1fb907`。
  Case 01 人工标注仍只存在于 eval，不进入业务执行路径。

## 诊断设施

- `agent_capture_outputs` 默认 false，仍由 TOML 配置，环境变量不参与配置。
- Composition root 按配置包装 Provider，在模型返回后、Parser 前捕获原文和
  task/attempt、模型、Prompt/Schema hash、安全用量摘要。
- 文件在 Worker 工作目录的 `.runtime/agent-output/`；目录 0700、文件 0600；
  Git 忽略、不由 API 暴露。不写入密钥、请求头、任意响应 metadata 或错误正文。
- 每个 task/attempt 独占一个文件；不覆盖旧证据。记录构造、写盘和日志失败均
  不替换原模型结果、不触发额外 Provider 调用。
- 原 Parser、Authority、业务校验和 Persistence 路径保持不变；无迁移或依赖新增。

## 本机状态与验证

- 检查无 PENDING/CLAIMED/RUNNING Requirement 后，在本机配置开启捕获并重启
  Host Worker。保持 `requirement-only` / `agent_max_attempts = 1`；Compose Worker 停止。
- 前端 HTTP 200；Backend health、DB health 均 OK；公开执行配置显示 Lingzhi /
  GPT-5.6 Sol / 仅 Requirement / 单次尝试。
- `pytest tests/prompts tests/test_config.py`：**115 passed / 1 live skipped**；
  两项现有 Starlette/anyio 弃用 warning。
- 新增捕获测试 5 项：解析前保留无效输出、权限与敏感 metadata 排除、独占写入、
  Provider 失败无重试、记录/日志异常隔离，以及默认关闭与构造无调用。
- 全 Backend `ruff check`、`ruff format --check`（234 files）、`git diff --check` PASS。
- 独立代码 Review：Approve，无剩余 Critical/Required。
- 本轮未自动执行真实模型生成。此前全量 813 passed / 4 live skipped 属于
  Worker 修复基线；本次捕获改动执行上述相关回归，没有冒充再次完成全量运行。

## 后续必要步骤

1. 等待用户授权一次诊断调用，或由用户在页面以同一原文创建新的 Workflow。
   120 秒 / 8192 输出 token 上限，单次不重试；不执行 Planning/Writing。
2. 保存的原文先离线执行同一 OutputContract；若 Parser 通过，继续核对 Authority
   和写入前业务校验，明确失败字段和触发条件。
3. 仅根据实际证据修复根因，加入通用负例和回归，保留约束强度、证据、版本与
   Authority 边界。禁止把历史失败 Workflow 改写为成功。

当前验收：诊断可用性 PASS；具体 Schema 缺陷修复和真实语义验收 **PENDING**。
