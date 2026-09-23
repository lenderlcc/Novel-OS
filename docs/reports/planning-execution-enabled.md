# 开放 Planning 后续业务流程

日期：2026-09-15。用户授权开放 Planning 并继续后续流程；保留人工方案审批。

## 修改

- 新增 `lingzhi-structured` ModelProfile：Lingzhi / `gpt-5.6-sol`，Responses structured
  output，120 秒 timeout，8192 输出 token 上限，不指定 temperature。
- 使用 TOML 配置 `agent_model_profile = "lingzhi-structured"`、
  `agent_execution_scope = "chapter-writing"`、`agent_max_attempts = 1`。
- `chapter-writing` 只领取 `PARSE_CHAPTER_REQUIREMENT`、`PLAN_CHAPTER`、
  `REVIEW_CHAPTER_PLAN`、`WRITE_CHAPTER`；不领取历史/模拟任务。
- 保留 `lingzhi-requirement` 的原 profile hash 和 Requirement-only 限制。新 Profile
  必须显式配对业务 scope。模型名、凭据和执行范围仍由服务端配置文件控制。
- 前端准确区分单一 Requirement 与完整业务阶段。审批、Context/Authority、
  Version 和 Draft 写入规则不变；未实现 NOVEL-009，也未代替用户批准方案。
- 每个 AgentTask 最多一次模型尝试；既有 Plan Review 不通过触发新的规划迭代的
  业务规则保留。私有输出捕获继续启用，失败不会自动技术重试。

## 当前流程

- Workflow：`b740882e-c39e-45a8-959b-7201e2197088`。
- 已有 Requirement Task `98abe452-6a19-4e82-bb48-5574665abc16` SUCCEEDED，
  未重新调用或改写 Requirement。
- 已排队 Planning Task `382e964b-29e0-4be5-8907-2a1400df8130` 已被新的 Worker
  领取，首次尝试进入 RUNNING。claim / PromptLineage 使用新 Profile。
- Plan Review 后仍需用户在页面批准方案，之后才调度 Writing。

## 运行中定位的 Planning 约束格式问题

真实 Planning 在 v3～v6 的 constraints 中给原文加了 `[MUST <id>]` / `[FORBIDDEN <id>]`
标识前缀。原文虽完整包含在字符串中，整个列表元素却不等于 Brief.text。真实模型 Review
给出 PASS 或 PASS_WITH_WARNINGS，服务端的严格字符串校验据此追加 MISSING_MUST，并将
最终结果改为 FAIL。私有捕获的模型原文与持久化结果支持这一结论。

根因是 Planning v1 Prompt 只要求“包含每条约束”，没有清楚说明这是整个字符串的精确
相等约定，以及标识应放在哪个字段。没有发现 Parser 添加前缀或 Persistence 修改正文。

局部修复：新增 `plan-chapter` Prompt **v2**，明确 MUST/FORBIDDEN/CHANGE_REQUEST 的
原文作为完整 constraints 元素，PRESERVE 原文作为 preserved_elements 元素；禁止加
标签/前缀、合并、转述或变更空白。标识与说明分别放在 requirement_coverage 的对应字段。
v1 及其 hash 保留，Schema、校验器、Authority 和持久化实现均不变，没有 Case 01 特判。

额外测试：新 Prompt 选择与 v1 pin/hash 可解析；带标识前缀的约束即使模型 Review
声称通过，仍必须被服务端拒绝。修订后相关回归 **140 passed / 1 live skipped /
349 deselected**。

发现现有 Workflow **没有业务规划迭代次数上限**；`agent_max_attempts = 1` 只限制
单个任务的技术尝试，不能限制 REVIEW_FAILED 后的新规划任务。此前“最后一轮”的口头
说明不准确，已向用户更正。已停止常驻 Worker（允许在途第四轮 Plan 完成），然后改用
`--once` 逐个推进当前 Review、新 Prompt 的 Plan 和 Review，避免继续无界调用。
新增业务循环上限属于后续需要处理的问题，本次没有悄悄改变 Workflow 架构。

## 最终运行结果

- 新 Prompt 生成 **Plan v7**，五条 MUST/FORBIDDEN 均作为完整原文元素存在；
  精确校验缺失项为零。PromptLineage 确认 `plan-chapter` v2，profile 为
  `lingzhi-structured`，未覆盖 v1 或旧方案。
- Plan v7 的真实 Review 结果 **PASS_WITH_WARNINGS**，hard_gate_issues 为空。
  提示包括合作载体仍抽象、合作机制规定较多和约束重复；这些意见保留给人工审批。
- Workflow 到达 **C06_PLAN_APPROVAL / WAITING_HUMAN**，HumanGate 绑定 v7，
  `approved_plan_version` 仍为空；未代替用户批准，未生成正文。
- 本次从排队 Plan 开始，共推进五轮 Plan/Review，每个任务各一次模型调用；
  原已成功 Requirement 未再次运行。前四轮保留为失败 Review 历史，第五轮通过。
- 新增 Prompt/负例经独立复核 Approve；相关最终回归 140 passed / 1 live skipped，
  Frontend 41 passed，Ruff check/format（235 files）、git diff --check PASS。
- 页面已定位到 **人工审批 · Plan v7**，显示 **Approve · 批准并写作** 按钮。
  在没有新的可领取任务、且已到人工审批后，重新启动常驻本机 Worker，以便用户
  在页面批准后自动执行 Writing。配置保留四个正式业务阶段和单任务一次尝试。
- 业务规划循环仍无总次数上限，这是已记录的现有限制；本次手动逐任务复测成功
  不代表已经实现这一预算。后续若出现反复 Review FAIL，仍需停止并诊断。

## 验证

- Backend 相关回归：**134 passed / 1 live skipped**，两项现有弃用 warning。
- 覆盖四阶段 Provider/schema 映射、旧 Profile hash 不变、TOML Docker 渲染、错误
  scope 拒绝、模拟任务与正式任务共存时过滤、开放范围后继续 Planning/Review 并停
  人工审批、单次 attempt budget 和公开配置不泄密。
- Frontend：**41 passed**；lint、typecheck/build PASS。
- Ruff check / format（234 files）和 git diff --check PASS。
- 独立 Review 初次发现 unrestricted all 会领取模拟任务，已改为显式业务 scope 并
  补充负例；最终 Approve，无剩余 Critical/Required。
- 无依赖或迁移变更。本次没有重新运行全库 migration 或全量 pytest。

## 运行方式

- Docker 重建停在依赖下载，已中止；不将其记录为成功构建。
- Docker Backend/Worker 已停止。当前 Backend 以本机 uvicorn 监听 127.0.0.1:8000，
  Worker 在本机使用同一 TOML，原 PostgreSQL 容器及数据保持运行。
- 停止容器后 Colima 的 8000 SSH 转发未自动解除，已仅取消这个旧端口转发；
  没有停止 SSH master，也未改动 PostgreSQL 的转发、密钥或 TLS 设置。
- Backend health / DB health OK，公开执行配置返回新 Profile 和四种业务 task；
  前端 5173 已重载并选择原项目/章节，显示 Planning 正在生成。
- 可复用 README 中的本机启动命令；Docker 完整重建仍待依赖下载恢复。
