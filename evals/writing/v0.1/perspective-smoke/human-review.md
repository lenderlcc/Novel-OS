# STYLE-002 — 第三人称真实 Writing Smoke

状态：NOT_RUN / NOT_EVALUATED。未获得本次 Profile 的显式审批和本次真实调用授权；不要用之前 Case 03 的重试授权运行此 smoke。

## 准备与授权

使用独立测试项目，创建第 1 章；创建并人工批准 `narrative_perspective=THIRD_PERSON` 的 Profile。若复制当前项目的其他偏好，逐项保持原值，不调节密度、节奏等设置。普通细节由正常 Planning 处理。

简单测试需求：

> 两位同伴在车站碰面，一人发现车票落在咖啡馆，通过一次简短交流约定由谁回去取票。结尾二人仍准备同行，不新增重要设定。

先确认授权范围是完整 Requirement → Planning → Review → 人工批准 Plan → Writing，还是只运行已批准 Plan 的一次 Writing。记录调用次数上限；每次失败保持人工重试，不自动消费。不要更改 Case 01 / 02 / 03 的已有输出。

## 执行证据（运行后填写）

| 项目 | 记录 |
|---|---|
| 授权人 / 日期 / 范围 / 次数上限 | 待授权 |
| Project / Chapter / Workflow | 未运行 |
| Profile record id / profile_id / version / hash / authority | 待填，必须 exact APPROVED / A5_USER_PREFERENCE |
| Profile narrative_perspective | THIRD_PERSON |
| 批准 Plan id / version | 待填 |
| ContextPackage id / hash / CP-005 version | 待填，核对 Profile 三元绑定与字段 |
| PromptLineage id / compiled hash / write-chapter version | 待填，必须使用 v4 或其经审核后继版本 |
| AgentTask / AgentRun | 待填 |
| ModelProfile / provider / model / hash | 待填，不保存 credential |
| WritingResult / ChapterVersion id / version / content hash | 待填 |
| 实际调用次数 / 用时 / tokens / 失败记录 | 未运行 |

## 人工验收

| 检查 | 结论与原文段落 |
|---|---|
| 正文主体的叙述者采用第三人称 | NOT_EVALUATED |
| 没有把整体叙述改成第一人称 | NOT_EVALUATED |
| 对白中的“我”“你”“我们”符合自然表达，不误判为违例 | NOT_EVALUATED |
| MUST / FORBIDDEN、批准 Plan 方向未因偏好改变 | NOT_EVALUATED |

判断叙述声音与对白的区别，通读全文；不统计“我”的词频，不以模型自报作为真实性证明。Profile → Context → Prompt 的工程证据不等于模型实际遵守。此 smoke 不评调其他文风维度，其他反馈仅记录。

Engineering Acceptance：见 STYLE-002 报告。AI Behavior Acceptance：NOT_RUN。Human Perspective Evaluation：NOT_EVALUATED。
