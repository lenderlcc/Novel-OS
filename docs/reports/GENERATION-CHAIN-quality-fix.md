# Generation Chain — 正文重复与修订漏检的最小修复

日期：2026-10-11。范围：生成链路工程修复与离线回归，不修改已批准的创作数据。

## 真实依据与边界

- Project：`688d6d8a-e6ae-4197-a320-c3cc1b81bf32`。
- 第二章《没有证据的怀疑》：`749f1271-6897-4797-9e58-e2d1da271a7b`。
- Workflow：`333a12fe-4bca-44c9-9852-2854a9eba424`；本轮只读核对为 `C09_INTERNAL_REVIEW / PAUSED`、state version 38、Draft v4。没有恢复任务或生成新稿。
- 已批准的 Writing Profile v3 确实进入原 Writer；没有用 fixture 偏好替换，也没有改其 2000–2500 字要求。
- 原 Writer run：`f1b4e862-67a0-4400-8299-5790a452408a`，Context：`1f472ab8-1924-4fbd-9d23-37ba0d52b6a4`（CP-005 v7）。通过已保存版本与输入重建的完整 Prompt hash 与记录一致：`11644bd46d61cdf5f58ac888599dc6bf84da42ff87d7d5b2c0424810cd3bd24c`。这证明应用层输入可复现，不代表存在原始 HTTP 请求存档。
- 实际材料位于 `backend/.runtime/e2e001r-20261009-chapter02/`。原计划把已知时间差与后续核查安排当作推进；原正文反复解释怀疑与证据。原 Narrative Review 已识别部分程序化对白，但修订后的审阅输入没有对应的冻结反馈与前稿，无法独立比较目标是否达成。
- Draft v2–v4 对应的后续质量任务曾按“新稿完成后停止”的边界取消，attempt 为 0，不能将它们描述为“模型已审阅但漏检”。本补丁补齐以后正常审阅所需的证据，不绕过暂停状态自动重跑。

## 最小修复

| 环节 | 修改 | 保持的边界 |
| --- | --- | --- |
| Planning / Plan Review | 新增 `plan-chapter v11`、`review-chapter-plan v7`。区分已有事实、本章信息或人物选择的后果、下一步安排；材料不足时使用现有 assumptions / risks / quality_issues 报告缺口。 | 不要求每章新增重大事实，不强制场景数，不靠扩写补篇幅，不把建议升级为硬约束，不更改批准 Profile。 |
| Writer Context | 新增 CP-005 v8，复用现有 serializer，仅在模型输入中删除与嵌套 `planning` 完全相同的重复字段。 | 不改原 snapshot、版本与来源；差异值和额外 metadata 保留；历史 v7 序列化不变；预算与最终输入共用同一投影。 |
| 修订后的独立审阅 | 新增 CP-006 v5 可选 `review-revision-outcome`，复用 RevisionRepository / RevisionContextReader，通过准确的 Project / Chapter / Workflow / Draft version 找到生成该稿的 RevisionResult。输入包含冻结反馈、解释、RevisionPlan 目标及前稿段落。 | 不依赖可能已清空的 active revision request；初稿、独立人工新稿不继承旧目标；证据为 A7 / DIAGNOSIS_ONLY，不成为 Canon。旧保真契约没有足够证据时省略该可选项，兼容旧记录。 |
| Narrative Review | 新增 `review-chapter-narrative v5`。用当前稿原文核对重复是否真正减少、描写是否有作用、删减后行为与衔接是否合理。A06 的“已修复”和 Fidelity PASS 不能替代文字效果判断。 | 复用现有 QualityIssue / severity / verdict；不把所有 P2 自动升为 FAIL，不自动启动下一轮修订。 |

没有新增模型输出 Schema、数据库表、Migration、引擎或平行执行路径。历史 Prompt 文件未覆盖，新版本供正常的新任务选择；已冻结的历史任务不重新绑定。

实际历史 Context 的纯内存新投影由 **21643 减至 17904 字符**（约 17%），无信息删减。这不是 Provider token 计费数，也不能单独证明文字质量提高。

## 回归验证

所有集成测试使用本轮独立临时 PostgreSQL 数据库和 Mock / RecordedProvider；没有读取实际 Provider credential，没有真实模型调用，没有写入真实项目。

| 检查组 | 结果 |
| --- | --- |
| Planning 路由、历史 hash、两个不同场景下的软建议与 Authority 边界、Profile / exploration 兼容 | 166 passed |
| Writer 投影、预算、私有知识隔离、人物与写作上下文及相关契约 | 102 passed |
| 既有 Quality vertical slice 与 Fidelity | 60 passed |
| 新增修订审阅证据单元及完整产品流程回归 | 9 passed |
| 独立 review 的投影、质量契约、预算、引文与 Prompt registry 交叉回归 | 189 passed，无阻断发现 |
| `ruff check novel_os tests` | PASS |
| `ruff format --check novel_os tests` | PASS，452 files |
| `git diff --check` | PASS |

各检查组有重叠，不相加宣称唯一测试总数。新增回归覆盖：Feedback → Revision → Draft v2 → 两路 A05；清空 active request 后人工重新审阅仍获得准确目标；独立人工 Draft v3 不继承旧反馈；跨 Project / Chapter / Workflow 隔离；完整证据超预算明确阻断，不截断证据；旧版本兼容及历史 hash 保持。

另一次扩大至 493 项的重复回归在 13 项通过、无失败时主动停止，不计为全组通过。本轮没有执行全仓库验收或真实模型质量评测。临时测试数据库、端口转发和配置已清理。

## 仍需创作数据与真实验证的部分

1. 当前实际项目缺少正式批准的人物行为画像，原 Writer 的 Gu Che POV identity / 合法 Knowledge 绑定不足。没有凭空建立性格、批准画像或把 Lin Lan 的秘密灌入 Writer；也没有新增基于“限知”等关键词的硬阻断。后续需要从真实创作资料通过既有审批路径补齐。
2. 修复不能自动给现有第二章计划增加有效事件。原 Plan 与 Draft v4 保留；材料容量不足时，应由创作决策补充有依据的行动与后果，或明确接受较短正文。
3. 单元和集成测试证明输入、版本、预算与权限闭环，不能证明模型已经减少水字数。没有将 Mock 结果作为文学质量验收。

后续获授权后，可选两个不同章节场景，在固定真实 Profile、人物资料、模型与输入版本下验证：先检查 Plan 是否把旧结论误当新发现，再检查每段新增信息或人物选择的作用、重复论证、删减后的因果衔接。对照时分别改变 Plan 或链路输入，保留运行证据并盲读，不以字数、短句数量或自动 PASS 代替人工判断。

**结论：已修复确认的工程缺口；后续章节的真实文字效果尚未验收。** 本轮没有改第二章正文、批准偏好、Memory 或第三章，没有提交或推送代码。
