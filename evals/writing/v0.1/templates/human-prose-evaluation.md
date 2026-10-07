# Real Provider Writing Smoke — 人工验收模板 v0.1

状态：**NOT_RUN / NOT_EVALUATED**。复制后填写；不要把空表或 Mock 文本记为已通过。

## 执行与授权

| 字段 | 记录 |
|---|---|
| 评阅人 / 日期 | 待填 |
| Git commit / case ID / case hash | 待填 |
| Provider / Model / ModelProfile hash | 待填，不记录 credential |
| 人工付费 opt-in 人 / 时间 / 授权范围 | 未授权 |
| 最大调用次数 / 每次输出 token / 超时 / 费用上限 | 待填；仅一次 smoke，不自动消费 API |
| 实际调用次数 / token / 延时 / 实际费用 | 未运行；费用未知不得填 0 |
| 模型失败、重试、人工修改输入的全部记录 | 待填；不得只挑成功结果 |
| Human Plan Gate 批准者 / Plan ID / 精确 version | 待填 |
| Draft current_version / approved_version，生成前后 | 待填 |
| 最终 state / check_status / check_codes | 待填；C08 PASS 不等于文学合格 |

## 输入与完整 lineage

逐项保存私有文件路径及 SHA-256，引用可供评阅人实际打开的证据。合成 fixture 也要保存具体生成的批准 Plan，不能只填一句需求。

| 对象 | ID / version / hash / 文件路径 |
|---|---|
| Approved Plan：objective、scenes、required_outcome、constraints、ending_state | 待填 |
| Previous approved chapter：正文及具体版本；被排除的 current Draft | 待填 |
| 未来信息允许范围、禁止透露信息；角色的知识/信念/怀疑/误解边界 | 待填 |
| ContextPackage：ID/profile/version/hash 与完整 snapshot | 待填 |
| PromptLineage：ID、模块 pins、compiled_prompt_hash、output schema | 待填 |
| AgentTask：ID / workflow / state_version | 待填 |
| AgentRun：ID / attempt / disposition | 待填 |
| ModelProfile：完整非敏感配置及 hash | 待填 |
| WritingResult：ID / metadata / check_codes / content_hash | 待填 |
| ChapterVersion Draft：ID / version / 完整正文 / SHA-256 | 待填 |

## 评阅方法

先阅读批准 Plan 和授权知识范围，再通读正文。对照实际段落判断，不相信 `scene_execution.function_completed`、`plan_deviations=[]` 或模型 confidence 的自报。不要因风格偏好把所有解释、情绪词或过渡都判错；记录对当前场景造成的具体影响。

每项选择 `PASS / CONCERN / FAIL / NOT_EVALUATED`，附原文短摘录和段落位置。严重程度为 `NONE / MINOR / MAJOR / BLOCKER`。每项都要填写；没有对应情节时说明为何无法评价，不能默认为 PASS。

| 维度 | 检查问题 | 结果 / 严重程度 | 段落证据 / 影响 / 备注 |
|---|---|---|---|
| Plan adherence | 是否落实批准版本的场景意图、约束、人物方向？ | NOT_EVALUATED | 待填 |
| Required outcome | 必需结果是否真正发生，结尾状态是否吻合？ | NOT_EVALUATED | 待填 |
| Mechanical plan expansion | 是否只把 Plan 条目逐句扩写，缺少行动和互动的因果？ | NOT_EVALUATED | 待填 |
| Major deviation | 是否擅改主线、核心角色、能力/历史、世界规则、结局方向？是否漏报？ | NOT_EVALUATED | 待填 |
| Knowledge leak | 角色是否无来源知道 GLOBAL_ONLY、未来计划或未批准 Draft 的事实？ | NOT_EVALUATED | 待填 |
| Over explanation | 行动/对话已表达后，是否重复解释动机、意义和情绪？ | NOT_EVALUATED | 待填 |
| Emotion labeling | 是否依靠情绪标签代替可感知的行为、语气与细节？ | NOT_EVALUATED | 待填 |
| Uniform rhythm | 句式、段落长度和推进速度是否不随场景压力变化？ | NOT_EVALUATED | 待填 |
| Template transition | 场景/段落转换是否套话化，缺少事件或感官衔接？ | NOT_EVALUATED | 待填 |
| Dialogue functionalization | 对话是否只承担讲解背景/任务，缺少人物目的、回避与回应？ | NOT_EVALUATED | 待填 |
| Character voice collapse | 不同人物是否表达习惯、词汇与反应趋同？ | NOT_EVALUATED | 待填 |
| Excessive closure | 是否每段/每场都总结点题，过早收束仍应开放的张力？ | NOT_EVALUATED | 待填 |
| Over-signposting | 是否反复提示转折、伏笔、重要性，代替事件本身？ | NOT_EVALUATED | 待填 |

## 人工结论

- Engineering Acceptance：待引用工程报告，不能用人工“感觉正常”覆盖工程失败。
- AI Behavior Acceptance：NOT_EVALUATED；按 Plan、required outcome、偏离和知识边界证据单独判断。
- Human Prose Evaluation：NOT_EVALUATED；不计算缺省平均分，不使用 LLM judge。
- 是否具备可用 Writing Draft：待填。
- 必须修复的具体问题（段落、根因假设、影响、复测方式）：待填。
- 可以接受的限制及批准人：待填。
- 下一阶段放行：待人工 Review；重大方向偏离、核心结果缺失或确认知识泄漏不得被其他文体优点抵消。

一篇 smoke 仅证明这一次输出，不证明真实模型稳定性，不据此自动批准正文、写入 Canon 或开始 NOVEL-009。
