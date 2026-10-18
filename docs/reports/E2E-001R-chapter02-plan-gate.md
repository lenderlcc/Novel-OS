# E2E-001R 第二章《没有证据的怀疑》— Plan Gate

日期：2026-10-09，Asia/Shanghai。执行完成时间：20:19:28。

第二章 Brief v1、Plan v1 和 Plan Review 均已通过产品执行链路产生。Plan Review 为 **PASS_WITH_WARNINGS**，一次 Planning iteration，18/18 项要求覆盖，无硬性阻断。流程停在 **C06_PLAN_APPROVAL / WAITING_HUMAN**；Plan 未批准，第二章尚无正文版本。

本报告是规划阶段的执行与审阅证据，不代表人工批准或正文质量验收。

## 1. 执行对象与前置核对

| 对象 | 核对结果 |
| --- | --- |
| Project | `688d6d8a-e6ae-4197-a320-c3cc1b81bf32` |
| 第一章 | `f20ff918-9967-4406-ba48-62cf1dac2956`，《独享的暗号》，COMPLETED |
| 第一章 current / approved version | `4 / 4` |
| 第一章已接受正文 | `11454080-c744-4aeb-9296-a872d365e32f`，Draft v4 |
| 第一章 Memory Commit | `e137524e-578c-49a3-81d8-10f9661bf68c`，COMMITTED，5 条正式 Entry |
| Memory 人工确认 | local-user，2026-10-09 14:57:05（Asia/Shanghai） |
| Writing Profile current / approved | `3 / 3`，APPROVED |
| Profile record ID | `2c20019e-3e5c-421f-9545-303d354f3291` |
| Profile logical ID | `688d6d8a-e6ae-4197-a320-c3cc1b81bf32` |
| Profile hash | `ea711d16a708b30fb53c3e09e9b284c3dff0dd754b90184611769c34706e77e2` |
| 第二章 | `749f1271-6897-4797-9e58-e2d1da271a7b`，《没有证据的怀疑》 |
| 第二章 Workflow | `333a12fe-4bca-44c9-9852-2854a9eba424` |

实际批准的 Profile v3 面向中文网文读者：第三人称、适中偏快节奏、高叙事密度、中高对白占比、清晰的关系兑现、低解释密度、高自然度。正文长度为 **2000–2500 字**。本轮未恢复旧测试 fixture 的 Profile v1，也未修改 Profile。

执行前后通过 API 和只读数据库核对：第一章 Chapter、历史 Draft、Workflow、已提交 Memory、Profile 指针和各 Profile 版本均保持不变。当前项目只有第一章和第二章。

## 2. 授权与执行范围

本轮授权来自用户对第二章新增 3 次单次任务调用的明确回复“是的授权”。旧第一章额度未复用。

- Provider / Model：Lingzhi / `gpt-5.6-sol`。
- 外发范围：第二章完整要求、相关设定与角色资料、必要的第一章已接受正文与正式 Memory、批准的 Profile v3、生成的 Brief 和 Plan。
- 仅执行 Requirement → Planning → Plan Review；每个任务实际 attempt 为 1。
- 失败、需要重做或人工关卡即停止；未自动重试或循环 Planning。
- 本轮已执行 **3/3 次**，授权记录状态为 STOPPED。

复用 `evals/e2e/multi-chapter/run.py` 的既有 `one-task` 操作和原 Worker `--once --task-id`，使用精确任务范围。Chapter 和 Workflow 通过产品 API 创建及提交；没有直接写数据库，没有伪造 Canon。

用户要求保存在 Workflow CREATE 输入中，随后通过正常 USER_SUBMITTED 事件启动。第二章原文 SHA-256：

`6f11865ef6de66ab3575f85dcac58bcd3c08b3a4f3cb5467f16dde38b82c2d5d`

原 E2E fixture hash 只标识已有场景基线；第二章新增用户要求以上述独立 hash 记录，不声称旧 fixture hash 覆盖新原文。

## 3. 可读 Plan v1

全章以 **Gu Che 第三人称限知**组织，地点为 Clock Tower，目标是继续追查 Missing Courier。Lin Lan 的指控始终处于无证据的怀疑层面。三个紧凑场景在 2000–2500 字内同时推动调查和关系。

### 场景 1：到达与质疑

Gu Che 正在 Clock Tower 复核 Missing Courier 的记录。Lin Lan 从 River Station 到达，尽早以核查中的时间问题质疑 Gu Che 是否与 Station Alarm 有关。

Gu Che 追问依据，要求区分疑点和证据，拒绝暗示性定责。Lin Lan 没有直接证据，但提出共同核查。两人的戒备上升，分歧通过追问与回避显现，不进入 Lin Lan 内心。

### 场景 2：争执转为共同核查

双方都想找到 Missing Courier，却对什么信息足以支持怀疑、各自该公开多少材料存在分歧。两人比较自己实际持有的记录，把争执转化为一个可继续调查的时间缺口。

这个缺口只能推动核查，不能证明 Gu Che 对 Station Alarm 负责。Gu Che 以可核对的信息回应；Lin Lan 承认现有材料不足，仍保留怀疑。第一章纸条内容没有向 Gu Che 披露，也不能通过精准推断自动获得。

### 场景 3：带条件的合作

两人围绕时间缺口确定下一步核查对象，在不信任尚存的情况下继续合作。关系从防御对峙转为有限的工作默契，避免直接完成和解。

结尾钩子是尚未对齐的时间记录。Station Alarm 责任仍未揭晓，午夜开盒机制未验证，Sealed Copper Box 保持完好；不安排开盒、损坏或变相测试。

### 自由发挥与边界

记录差异、核查顺序、追问方式和分工属于 Plan 提出的局部调查细节，尚未批准或提交为 Canon。Plan 的 `proposed_major_changes=[]`，未引入新的世界规则、组织或设施。正文不应把 Plan 中的结束状态清单直接写成验收式旁白。

## 4. Plan Review 与风险

- Brief v1：`5ec29f39-b17f-40f1-adc8-246e39cc5cfd`。
- Plan v1：`300683ff-7506-4c2f-979e-8c79644903d5`，PROPOSED，批准字段为空。
- Review：`a718e92a-f5fe-4e22-a6bf-3f329c871f5d`，精确绑定上述 Brief、Plan 和 Profile v3。
- verdict：PASS_WITH_WARNINGS；confidence：0.97。
- coverage：18/18；hard gate、missing requirement、forbidden violation、locked conflict、direction conflict、quality issue、over-specification issue 均为空。
- 迭代：1 次；未为了通过 Review 增加细节或继续迭代。

Review 的两项 LOW 风险：

1. 时间缺口不得在正文中被写成 Gu Che 涉事的客观证据。
2. Gu Che 不得通过叙述、精准推断或物品暗示自动获知 Lin Lan 的第一章纸条内容。

Reviewer 的建议是维持这两条边界，无需为审查增加场景、动作或对白细节。建议未升级为额外 User/System hard constraint。

另有正文执行前的工程风险：Plan 输出 `pov_character_id=null`，当前 Memory Subject 目录没有可绑定的 Gu Che 实体身份，模型未伪造 ID。现有 Writer Policy 在 character_id 为空时不会读取他人的 CHARACTER_KNOWLEDGE，但也无法检索 Gu Che 本人的结构化 Memory。后续正文执行仍需核对实际 Context，不能把此轮 Plan Review 当成已验证的正文知识隔离。

Planning 的作者上下文包含第一章已接受正文及正式 Memory，其中可见 Lin Lan 私有纸条内容；这是本轮授权的规划材料，**不等于 Gu Che 已知**。Plan 明确禁止向他释放该内容。本报告不声称规划模型从未看到暗号。

Task metadata 中 Review 的 PASS 与持久化 Review 的 PASS_WITH_WARNINGS 是既有 effective verdict 规则根据 logic_risks / recommendations 正常归一化的结果，不是版本绑定错误。

## 5. 版本化执行证据

三次调用均为真实 Provider 执行，SUCCEEDED / APPLIED，各 attempt 1。三个 Context 构建时均 READY，无必需来源缺失或 Authority 冲突，无 future/evaluator/recorded 来源；Planning 与 Review 实际载入 Profile v3 完整内容及 hash。

| 阶段 | Task ID | AgentRun ID | Prompt Template |
| --- | --- | --- | --- |
| Requirement | `0fcd9e60-2f23-4623-9cf0-37f1d22114a7` | `3edc2f6a-3f52-48f1-93cd-39c69dd5b8bc` | parse-chapter-requirement v4 |
| Planning | `224f3214-1161-458e-bca1-e153cb23b1e2` | `46e1d0cc-9fa1-48ee-92a9-ea427fcf765a` | plan-chapter v10 |
| Plan Review | `54eaad4e-ebc0-47e7-9782-e5529a76726e` | `7749798b-8721-48f8-8013-07ae35c32e2e` | review-chapter-plan v6 |

| 阶段 | ContextPackage ID | PromptLineage ID |
| --- | --- | --- |
| Requirement | `538c1be3-ec2f-498d-89af-893e8d422a94` | `e05d97f7-0274-44ad-8a6a-9fc383e81fb3` |
| Planning | `44d2b760-eb76-49ba-8511-597b4d6ee579` | `23300e0f-2b68-4734-9c91-fe0f35488ea4` |
| Plan Review | `437d68bc-2971-4422-b518-b849c5724d61` | `b0599cb1-7a0a-465f-8743-6de3aeb922fc` |

ModelProfile 为 `lingzhi-structured`，profile hash、Prompt 内容 hash、输入绑定和 source versions 保存在完整 trace 中。流程推进后旧 Context 的 freshness 可变为 STALE，不改变上述构建时及执行时的成功记录。

## 6. 停止边界与后续调用估计

| 核对项 | 实际值 |
| --- | --- |
| Workflow | C06_PLAN_APPROVAL / WAITING_HUMAN，state_version 7 |
| Human Gate | `647be624-b116-4a7a-9e16-9f72743d0f96`，WAITING |
| Gate 绑定 | Plan `300683ff-7506-4c2f-979e-8c79644903d5` v1 |
| Plan 审批字段 | 空 |
| Chapter 2 current / approved plan | `1 / null` |
| Chapter 2 current / approved prose | `null / null` |
| 新增 AgentRun | 全局 152 → 155，恰好 3 个 |
| 第二章 Draft / Memory | 0 / 0 |
| 当前活动任务 | 0 |
| 后台连续 Worker | 未运行；不会自动消费后续任务 |
| 第三章 | 未创建或执行 |

正常成功路径中，人工批准 Plan 后生成正文需 **1 次 Writer**；再执行合规与叙事两类质量审阅需 **2 次**，合计最少 **3 次新调用**。若人工接受正文并推进 Memory，通常另需 **1 次 Memory Extraction**，随后仍须人工确认提交。修订或失败处理可能增加调用，不能预先保证固定总数。

上述只是估计，不是继续执行的授权。本轮 3 次额度已经耗尽，Plan、Draft、Memory 仍分别由用户确认。

## 7. 本地证据

证据目录：`backend/.runtime/e2e001r-20261009-chapter02/`，位于当前本机仓库；该运行目录被 Git 忽略。

- `authorization.json`：本轮授权、已消耗 3 次和 STOPPED 状态。
- `chapter02-user-requirement.txt`、`verification.json`：原始用户要求及输入核对。
- `01-requirement.json`、`02-planning.json`、`03-plan-review.json`：各阶段持久化产物与状态。
- 各阶段 `*-context.json`、`*-prompt-lineage.json`：版本化 Context 与 PromptLineage。
- `final-verification.json`：API / 只读 DB 停止边界及前置数据不变核对。
- `full-trace.json`：复用现有 runner 导出，lineage_errors 为空；整体验收仍为 PENDING_HUMAN_REVIEW。
- `plan-gate.jpg`：页面已显示“等待人工审批方案”。

本轮没有修改产品架构、Prompt、业务代码或实体，没有执行迁移或重新跑全量自动测试；这是限定范围的真实规划验收。完成后停止，等待人工 Review。
