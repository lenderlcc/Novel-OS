# Requirement 页面任务等待问题修复

日期：2026-09-15

## 根因

- 当前流程 `d72e413b-8ef0-439f-af1d-62a710e7b8a5` 停在 C01 / WAITING_AGENT；Requirement Task 为 PENDING，attempt_count=0，没有 AgentRun。独立 Worker 没有启动。
- 之前的 Lingzhi 配置只用于单次 eval 入口，普通 Worker 的配置选择尚未支持该 profile。
- 页面标题仅看 Workflow 阶段，把未领取的 C01 也显示成“正在理解需求”。

## 实现

- Worker 支持文件配置 `agent_model_profile="lingzhi-requirement"`；该 profile 必须同时设置 `agent_execution_scope="requirement-only"`。
- Repository 在候选任务查询时筛选 task_type，包含过期租约恢复路径，避免其他类型的旧任务阻塞需求任务。
- 受限 Worker 仅处理已调度的正式 Requirement，不补调度旧模拟流程，不领取 Planning、Plan Review 或 Writing。
- `agent_max_attempts=1` 收紧执行预算。原始 Task.max_attempts 保持不可变；有效上限存入不可变 Run.input_metadata.attempt_limit，正常完成、失败、过期恢复和后续领取均遵守同一上限。
- 旧 PENDING retry 已达到收紧上限时直接终止并记录 result_metadata.attempt_limit / Audit，不再遗留无限等待。默认 Worker 也不能扩大前一 Run 的上限。
- 增加只读 `/api/v1/agent-execution/config` 返回模型、执行范围、次数上限，不暴露密钥。此接口不代表 Worker 在线，两个进程应使用同一配置。
- UI 区分等待调度、PENDING、CLAIMED、RUNNING、PAUSED。被执行范围排除的阶段显示停用并停止自动轮询。
- 暂停流程上方提供继续按钮，仍调用原有 Workflow RESUME API。费用提示根据恢复阶段和执行范围判断；人工审批阶段或被排除的阶段不会错误提示恢复即调用模型。
- Compose 新增可选 `worker` profile，独立进程读取与 Backend 相同的 TOML，不新增端口发布。

## 原记录与人工操作

已通过原有 API 暂停上述流程并保留输入事件。旧 PENDING Task 按现有生命周期取消，未产生 Run；Resume 将按现有 Workflow 调度规则创建后续 Task，继续读取相同原文。

本机 Backend / Worker 已配置为 Lingzhi gpt-5.6-sol、Requirement only、每任务最多一次尝试。
启动 Worker 前确认开发库没有可执行 Requirement；由测试者在浏览器点击
**继续理解需求（调用真实模型）** 后执行。不会自动推进 Planning / Writing 的 Agent。

这里的次数上限针对每个 Task；手动创建新流程或恢复流程是新的执行决定，不是整个服务器一生只能调用一次。

## 验证

| 检查 | 结果 |
| --- | --- |
| 后端定向：执行、租约、独立进程、Requirement、范围限制 | 49 passed / 1 live skipped |
| 配置和 Provider 回归 | 110 passed / 1 live skipped |
| 前端 Unit / Component | 41 passed |
| 浏览器 E2E，隔离测试库、强制 Mock | 8 passed |
| TypeScript / ESLint / Vite build | PASS |
| Ruff check / format --check / git diff --check | PASS |
| Docker Backend、health / health/db、配置查询 | PASS |
| Docker Worker 进程 | 启动正常，但后续人工测试发现容器无法解析 Lingzhi 内网域名，已停止 |
| 本机独立 Worker / Lingzhi 只读 model catalog | PASS：进程运行，HTTP 200，gpt-5.6-sol 可用 |
| 后端全量 pytest | 813 passed / 4 live skipped / 2 既有弃用警告，520.47 秒 |

新增负向测试覆盖：暂停不执行、失败不自动重试、收紧旧重试预算、普通 Worker 不能扩大过期手动任务预算、过期的非 Requirement 任务不被领取、排除的旧 Plan 不饿死新 Requirement、只读配置无凭据、暂停恢复费用提示与范围一致。

初次回归中的六个失败精确定位到现有数据库禁止修改 Task.max_attempts。修复改用 Run 快照，没有修改 migration 或放宽数据库保护。前端未知阶段回退及恢复费用提示也已补充回归。

## 独立 Review

独立只读审查完成，两个 Required（预算收紧的审计证据、暂停恢复费用提示）均已解决；无剩余 Critical / Required。独立验证前端 41 项测试、lint、build 及后端定向静态检查通过。

## 人工测试追加：MODEL_UNAVAILABLE

测试者在页面点击继续后，创建 Task `1392ad27-4975-4a10-ad5f-7f47dc9ce81a`、Run
`0601e350-0baf-41e1-beb8-fe3b260fc863`。只执行一次，约 90ms 后返回 MODEL_UNAVAILABLE，
流程进入 C91_FAILED，单次限制正确阻止自动重试。

同一地址的只读网络对照：本机 DNS / TLS / HTTP 正常；容器内 socket.getaddrinfo 复现
`Temporary failure in name resolution`。这次问题位于 Docker 到内网域名的解析边界，
没有证据表明是模型输出或 Parser 错误。

已停止 Compose Worker，改用本机独立 `python -m novel_os.worker --config config.toml`，
保留 Requirement only / attempt limit 1 / TLS verification / file-only config。
本机携带凭据的 GET /v1/models 返回 200，并确认模型存在；没有再次 POST /responses。
失败历史保持不变，原文已填回当前页面供测试者点击 Start Workflow。原文 SHA256 仍为
`82490c0b11dc0722cede763d4558334b04a2f2879b12d5f845603ef84b1fb907`。

## 范围与限制

- 保留 API → Service → Repository → Database 和独立 Worker，未改产品架构、业务实体或数据库迁移。
- 没有新增 Agent 直调接口；没有执行 Planning / Writing、Review Agent 或 NOVEL-009。
- 自动测试全部使用 Mock 或离线 transport。测试者发起的一次真实尝试因上述网络错误失败，排查只做只读 catalog 查询，没有自动重试内容生成。真实模型语义分解质量仍待验收。
- 配置查询是配置说明，不是 Worker 心跳监控。Worker 停止时页面会明确显示任务等待；运维可通过 Compose ps / logs 检查进程。
