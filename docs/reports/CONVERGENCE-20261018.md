# 2026-10-18 工程收敛与测试目的

## 本轮决策

用户要求立即收敛，不再反复修改第二章；测试阶段不再要求用户参与点击或确认。
助手可通过现有产品接口代办测试确认，必须核对具体版本和证据、保留审计。
这不是给模型增加 Authority，也不是删除生产 Human Gate，不代表用户亲自评价文笔通过。

冻结新功能、架构扩展、Writer/Review Prompt 调参和第二章正文修改。保留实际批准的
Profile v3，按以下目标区分工程通过与写作效果，不能用“测试数量”代替产品结果。

| 测试目标 | 判定依据 |
| --- | --- |
| 持续执行 | 同一项目新阶段任务无需手工逐个启动 Worker；空闲无模型调用 |
| 恢复与隔离 | Worker 退出可重启；其他项目任务不被消费；租约和次数限制仍生效 |
| 正确产物 | Plan/Draft/Review/Memory 绑定真实版本，历史不可变，没有重复写入 |
| 明确结束 | 完成、失败、待确认准确区分；模型失败保留证据，不无限重试 |
| 连续性 | 已确认信息可供后章使用；怀疑不晋升为事实，秘密不泄漏 |
| 初稿效果 | 记录重复信息、无效段落、人物具体性、实际变化与知识边界；不能用多轮人工修好的稿件证明改善 |

后续新章节保持模型、批准 Profile 与已有材料；保存初稿和第一次审阅。一般质量问题
先记录，最多一轮针对性修订用于比较；若同类问题继续出现，回到对应系统环节定位，
不反复改同一章。真实 Canon/知识冲突仍须处理，不能为赶进度自动放行。
本轮执行范围止于恢复和完成第二章，未新建第三章；五章真实生成效果仍未通过验收。

## 停滞根因与最小修复

实际项目 `688d6d8a-e6ae-4197-a320-c3cc1b81bf32`，第二章 Workflow
`333a12fe-4bca-44c9-9852-2854a9eba424` 在 C14 / WAITING_AGENT。
提取任务 `b9c9babd-2597-4d43-94f4-74677ce17ae5` 为 PENDING、attempt 0。
本机没有 Worker，Compose 也只有两个 PostgreSQL 服务。此前单次授权使用 `--once`，
执行完就退出；API/前端仍在线，使下一阶段任务只排队。

复用 AgentWorker → AgentQueue → Repository，仅增加 `--project-id` 过滤。
持续 Worker 可领取该项目后续任务；过滤同样约束过期租约，并与 task ID/type 取交集。
项目过滤为空队列时不回填全局历史任务。没有新增调度系统、表、依赖或迁移。

本机由 macOS launchd 托管原 Worker，配置仍读 `backend/config.toml`：

- Label：`com.novel-os.acceptance-worker`
- 安装文件：`~/Library/LaunchAgents/com.novel-os.acceptance-worker.plist`
- 固定范围：上述 E2E 项目；TOML `chapter-quality` / max_attempts=1 保持。
- 日志：`backend/.runtime/convergence-20261018/worker-service*.log`
- 查看：`launchctl print gui/$(id -u)/com.novel-os.acceptance-worker`
- 停止：`launchctl bootout gui/$(id -u)/com.novel-os.acceptance-worker`
- 恢复：`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.novel-os.acceptance-worker.plist`

托管范围只有 Worker；机器休眠/关机仍会停止服务，未宣称 API/前端也有进程托管。
不要同时运行另一个全局 Worker，或在本服务运行时使用要求 worker-stopped 的人工 runner。

## 第二章实际结果

- 已存在的 accepted Draft v6：`4d09c0cd-9425-4cba-9123-c839771fec49`。
- 1 次真实 Lingzhi `gpt-5.6-sol` Memory 提取成功，无重试。
- Run：`dd85c03a-8af7-45a5-aea1-1bbf5925f8b6`；Proposal：`9a0878dc-c8be-457f-985a-c5be479e9e90`。
- 助手核对正文后，通过 `/workflows/{id}/memory/confirm` 选择 2 条无冲突候选：条件合作、警报责任尚未确定。确认原因注明用户测试代办授权。
- Batch：`ba26f7c3-a6c1-44ff-aa85-70a14b2385ba`；canon_revision 1 → 2。
- Workflow：C16_COMPLETED / COMPLETED，state_version 68。
- 全部 Draft、批准 Profile、原 5 条 Memory 和其他任务记录前后相同。未直接写数据库。

## 保留的 Memory 问题，不计为通过

本轮共 5 条候选，只提交上述 2 条。其余 3 条保留在原 Proposal，未修改或强行提交：

| Candidate | 实际原因 / 证据 | 处理 |
| --- | --- | --- |
| linlan_alarm_suspicion | CHARACTER_KNOWLEDGE / SUSPECTS 的 uncertainty 被 blocking_uncertainty 当作阻塞，已有 Lin Lan ID 仍未归一化 | 疑似认知不确定性与身份混淆；未提交，不宣称怀疑记忆已保存 |
| update_joint_record_recheck | 模型 existing_entry_id 返回 logical_id `2c9db064…`，校验要求 record id `51198a57…` | 引用合同问题待核；保留原第一章记录，不替换 |
| missing_courier_whereabouts | OPEN 状态相同但 statement 不同，且未提供 state_before，现有规则判 CONTRADICTION | 保留已有去向未知记忆；不得猜测等价或绕过状态变更校验 |

因此“第二章流程完成”与“Memory 提取完整正确”分别报告；后者仍有缺口。没有为了
收尾将以上候选视为有效、改成空提案，或放宽 Canon/Authority 冲突检查。

## 验证

进程托管实测：向空闲 Worker 发 SIGTERM，PID 46745 → 46772 自动恢复；任务记录相同，
无新增模型尝试。完整结果、前后快照与调用记录在 `backend/.runtime/convergence-20261018/`。

变更文件：`backend/novel_os/worker.py`、`services/agent_queue.py`、
`repositories/agent_tasks.py`（3 个生产文件，共增加项目筛选参数和 SQL 条件）；
`backend/tests/core/workflow/test_project_worker.py`、`tests/test_acceptance_worker_cli.py`；
以及 README、本报告和 PROJECT-STATUS。没有提交或推送，之前的其他未提交修改保留。

- 独立复核：无生产代码阻塞发现；指出并修正新增测试中过期租约更新遗漏版本递增。
  修正后独立执行项目隔离 5 项通过，覆盖后续任务、进程替换、外项目过期租约、过滤交集和旧队列回填。
- 项目隔离 + 五章 Recorded Provider 连续性：6 项通过。该五章测试没有真实调用，不能证明真实文笔改善。
- CLI：6 项通过；任务范围与次数限制相关测试另有 12 项通过。
- 租约/独立进程恢复/Memory 事务回归：53 项通过（313.12 秒）。上述分组去除项目隔离复跑后共 77 个不同用例通过。
- ruff check、ruff format --check（本轮相关文件）、git diff --check 通过。
- API 数据库 health 与前端均返回 200，常驻 Worker 运行正常。
- 实际工作台显示“章节已完成”、Draft v6 当前版本，以及“已确认的记忆已保存”；临时验证页已关闭。

第一次混合指定测试路径时有 53 项出现 fixture 发现错误，未当作通过；随后按目录重新
执行相应用例。没有为此更改生产逻辑。此次不是全仓库全量验收。

结论：本轮队列恢复、项目隔离、进程重启和第二章正常选择确认通过；Memory 候选完整性
仍有上述 3 项缺口，后续章节初稿效果尚未验证，不能宣称真实五章验收整体通过。
