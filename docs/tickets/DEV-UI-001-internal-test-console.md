现在开始开发 Novel OS 内部人工测试界面：

DEV-UI-001 — Novel OS Internal Test Console

这不是正式产品前端。

本 Ticket 的唯一目标：

让产品/开发人员不需要 curl、不需要手工拼 JSON、不需要自己查询各种 UUID，
就可以通过浏览器完整测试当前已经实现的 Novel OS 能力：

自然语言需求
→ Requirement Agent
→ CreativeBrief
→ Planning Agent
→ Plan Review
→ Human Plan Approval
→ Writing Agent
→ Chapter Draft

并能够查看必要的 Debug / Lineage 信息。

==================================================
一、开始前必须阅读
==================================================

开始编码前先阅读：

1. docs/specs/01-PRD.md
2. docs/specs/02-AgentSpec.md
3. docs/specs/03-Data-Schema.md
4. docs/specs/04-Workflow-State-Machine.md
5. docs/specs/05-Internal-API-Tool-Contract.md
6. docs/specs/06-Technical-Architecture.md

以及：

docs/reports/NOVEL-001-implementation.md
docs/reports/NOVEL-002-implementation.md
docs/reports/NOVEL-003-implementation.md
docs/reports/NOVEL-004-implementation.md
docs/reports/NOVEL-005-implementation.md
docs/reports/NOVEL-006-implementation.md
docs/reports/NOVEL-007-implementation.md
docs/reports/NOVEL-008-implementation.md

重点检查当前真实 API：

- Project APIs
- Chapter APIs
- Requirement submission APIs
- Workflow APIs
- HumanGate APIs
- CreativeBrief query APIs
- ChapterPlan query APIs
- ChapterVersion APIs
- AgentTask / AgentRun debug APIs
- ContextPackage APIs
- PromptLineage APIs
- Generation/WritingResult APIs

不要根据设计文档猜 API。

必须先读取实际 FastAPI route / OpenAPI。

==================================================
二、核心原则
==================================================

这是：

Internal Test Console

不是：

Production Frontend。

判断是否完成的标准不是：

“看起来漂亮”

而是：

“我能否方便地测试 Novel OS”。

优先级：

Usability for testing
>
Correct workflow integration
>
Debug visibility
>
Visual polish

==================================================
三、技术栈
==================================================

使用已冻结技术栈：

Vue 3
TypeScript
Vite

可以使用：

Vue Router
Pinia

但如果当前规模不需要，不要为了架构完整性引入复杂状态管理。

HTTP Client：

优先使用简单统一 API client。

禁止把业务 API 调用散落在大量 Vue Component 内。

建议结构：

frontend/
├── src/
│   ├── api/
│   ├── components/
│   ├── views/
│   ├── types/
│   ├── composables/
│   ├── stores/         # 仅必要时
│   ├── router/
│   ├── App.vue
│   └── main.ts
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts

==================================================
四、不要做正式产品设计
==================================================

本 Ticket 禁止实现：

- 登录
- 注册
- OAuth
- RBAC
- 多用户协作
- 正式首页
- Marketing 页面
- Dashboard
- 富文本编辑器
- 正式小说编辑器
- Publishing UI
- Cover / Illustration
- Mobile responsive optimization
- Dark mode
- Theme system
- Complex Design System
- Animation framework
- Internationalization
- Notification center
- WebSocket infrastructure
- Complex SSE infrastructure
- Frontend persistence framework

只做：

Internal Test Console。

==================================================
五、核心用户流程
==================================================

页面必须让测试人员可以完成：

1. 选择 / 创建 Project
2. 选择 / 创建 Chapter
3. 输入自然语言 Chapter Requirement
4. 启动 Chapter Workflow
5. 查看 Workflow 当前状态
6. 查看 CreativeBrief
7. 查看 ChapterPlan
8. 对 Plan 执行 Human Decision
9. Approve 后触发 Writing
10. 查看最终 Chapter Draft
11. 查看 WritingResult metadata
12. 查看必要 Debug 数据

理想体验：

用户不需要复制：

project_id
chapter_id
workflow_id
gate_id
agent_task_id
context_package_id

前端自动管理这些 ID。

==================================================
六、主界面
==================================================

第一版可以只有一个主要页面：

Novel OS Test Console

布局建议：

--------------------------------------------------

顶部：

Project: [ select ]
Chapter: [ select ]

[New Project]
[New Chapter]

Workflow:
[Current State]
[Refresh]

--------------------------------------------------

Requirement

一个较大的自然语言输入框：

“描述你希望这一章发生什么……”

按钮：

[Start Workflow]

--------------------------------------------------

CreativeBrief

显示：

Intent Summary
Chapter Objective
Must
Should
Preferences
Forbidden
Preserve
Required Outcome
Desired Reader Effect
Creative Freedom
Assumptions
Ambiguities
Conflicts

如果尚未生成：

显示 Waiting / Processing。

--------------------------------------------------

Chapter Plan

显示：

Objective
Required Outcome
Opening Function
Scenes
Character Progression
Plot Progression
Information Release
Ending Function
Ending State
Constraints
Preserved Elements
Risks
Proposed New Elements
Proposed Major Changes
Requirement Coverage

--------------------------------------------------

Plan Human Gate

如果 Workflow 正处于：

C06_PLAN_APPROVAL

显示：

[Approve]

[Reject]

[Request Alternative]

[Modify]

并提供反馈文本框。

用户不需要填写：

gate_id
artifact_version
state_version

这些由前端从 API 当前状态自动读取并提交。

--------------------------------------------------

Chapter Draft

Writing 完成后显示完整：

ChapterVersion.content

正文必须是阅读友好的文本区域。

不要默认显示：

JSON。

--------------------------------------------------

Writing Metadata

默认折叠。

展开后显示：

scene_execution
introduced_elements
proposed_new_facts
plan_deviations
unresolved_questions
assumptions
knowledge_risk_flags
style_notes
confidence

==================================================
七、Debug / Advanced 区域
==================================================

页面底部提供：

Advanced / Debug

默认折叠。

至少可以查看：

Workflow History

Agent Tasks

Agent Runs

ContextPackage

PromptLineage

Generation Lineage

WritingResult raw structured data

Current / Approved ChapterPlan version

Current / Approved ChapterVersion

这些信息是开发 Debug 用。

不要和普通产品视图混在一起。

==================================================
八、状态展示
==================================================

Workflow 状态必须转成人可理解的展示。

至少支持当前已有：

C00_CREATED
C01_REQUIREMENT_INTAKE
C02_CONTEXT_ASSEMBLY
C03_REQUIREMENT_READY
C04_CHAPTER_PLANNING
C05_PLAN_REVIEW
C06_PLAN_APPROVAL
C07_WRITING
C08_DETERMINISTIC_CHECK
C09...
C90_BLOCKED
C91_FAILED
C92_CANCELLED

即使当前人工测试主要到 C08，
也不要遇到未知状态直接崩溃。

UI 可以同时显示：

C07_WRITING

Writing

之类：

Machine State + Human-readable Label。

==================================================
九、Workflow Progress
==================================================

增加一个简单 Progress 区域：

Requirement
→ Context
→ Planning
→ Plan Review
→ Human Approval
→ Writing
→ Draft

可以：

已完成 ✓
正在执行 …
等待用户 ⏸
失败 ✕
Blocked ⚠

不需要复杂 Stepper 组件。

重点是让测试者马上知道：

“现在卡在哪里”。

==================================================
十、自然语言输入
==================================================

Requirement 输入必须是：

raw natural language。

前端禁止要求测试人员填写：

must[]
forbidden[]
creative_freedom
required_outcome
JSON

这些应该由：

Requirement Agent

解析。

Test Console 本身就是为了验证：

自然语言 → Structured Requirement

这一能力。

==================================================
十一、Human Gate
==================================================

Human Gate 必须走真实已有 API。

绝对禁止前端：

直接修改 ChapterPlan.status

直接修改 approved_version

直接改 Workflow state

直接 update database

正确：

UI
→ HumanGate API
→ Backend Service
→ Approval
→ WorkflowRuntime

必须保持版本绑定。

如果 Backend 返回：

VERSION_CONFLICT

UI 应明确显示：

“当前方案已发生变化，请刷新后重新审批。”

不要自动偷偷重试旧 Approval。

==================================================
十二、Plan Reject / Alternative
==================================================

Reject：

提供文本反馈框。

例如测试人员输入：

“整体太保守，希望第二个场景冲突更明显，但不要改变结尾方向。”

前端只提交原始反馈。

禁止前端自己解释成：

must
forbidden
change_scope

解释由 Backend / Agent 完成。

Request Alternative：

调用已有 HumanGate action。

如果 Backend 要求 feedback：

允许附带自然语言反馈。

==================================================
十三、Modify
==================================================

如果已有 MODIFY HumanGate semantics：

UI 提供：

“我希望这样修改方案：”

自然语言输入框。

不要做复杂的：

Scene drag-and-drop editor
Structured Plan editor

当前测试重点是：

自然语言 Human Feedback。

==================================================
十四、Writing 状态
==================================================

用户批准 Plan 后：

UI 应能看到：

Waiting for Writing
或
Writing…

之后自动/手动刷新直到：

Chapter Draft available。

不要让用户再手工调用：

Writing Agent endpoint。

Agent 应由现有 Workflow 自动调度。

==================================================
十五、状态刷新方式
==================================================

第一版优先：

Polling

例如：

workflow active 时每 1～2 秒查询一次。

当进入：

HumanGate waiting
Completed
Blocked
Failed
Cancelled

降低/停止 Poll。

除非当前 Backend 已经存在稳定 SSE 接口，
否则不要为了本 Ticket 新建复杂 Realtime infrastructure。

后续正式前端再升级 SSE。

==================================================
十六、Error UX
==================================================

不要只：

console.error()

至少在页面展示：

Error Code
Human-readable message
request_id

典型：

VERSION_CONFLICT

CONTEXT_BLOCKED

MODEL_ERROR

AGENT_FAILED

WORKFLOW_BLOCKED

VALIDATION_ERROR

DATABASE_UNAVAILABLE

如果 Backend 已有统一错误结构：

直接使用。

==================================================
十七、Blocked 展示
==================================================

如果 Workflow：

C90_BLOCKED

必须展示：

Blocked

以及：

block_reason

如 Backend 提供 missing context/conflict：

也显示。

禁止表现成：

“加载中……”

无限转圈。

==================================================
十八、Failed 展示
==================================================

如果：

C91_FAILED

显示：

Workflow Failed

以及：

error code
error message
request ID

Debug 区可以查看：

AgentRun / WorkflowHistory

方便定位。

==================================================
十九、Draft 展示
==================================================

正文区域必须：

适合真实阅读。

要求：

- 保留段落
- 正常换行
- 可滚动
- 宽度适合阅读
- 不直接用 JSON `<pre>` 展示正文

同时显示：

Chapter Version

Status

例如：

Version 2
DRAFT

如果：

approved_version != current_version

Debug 区应明确展示：

Current: v2
Approved: v1

==================================================
二十、版本信息
==================================================

在 Test Console 中明确展示：

ChapterPlan:
Current Version
Approved Version

Chapter:
Current Version
Approved Version

这是人工验证版本安全的重要手段。

特别方便测试：

approved = v1
current = v2 DRAFT

==================================================
二十一、CreativeBrief 展示
==================================================

CreativeBrief 不要直接显示 raw JSON。

至少对：

must
should
forbidden
preserve
assumptions
ambiguities

使用简单 list。

confidence 可以显示。

Debug 区仍然可以提供：

Raw JSON。

==================================================
二十二、ChapterPlan 展示
==================================================

Scenes 建议：

Scene 1
- Function
- Objective
- Required change
...

Scene 2
...

不要追求复杂视觉设计。

目标：

人工能快速判断：

“这个 Plan 是否符合我的需求”。

==================================================
二十三、Context Inspector
==================================================

Debug 区提供 ContextPackage Inspector。

至少显示：

Profile
Version
Package Hash
Status
Token Budget
Estimated Tokens

Included Items:
- source type
- source id/version
- priority
- authority
- status
- selected reason

Excluded Items:
- source
- reason

这样人工发现：

“Writer 为什么看到了不该看的信息？”

可以直接查。

==================================================
二十四、PromptLineage Inspector
==================================================

只展示：

Module ID
Version
Hash

例如：

System Policy v1
Writing Role v2
WRITE_CHAPTER v1
scene-execution v1
dialogue v1
natural-prose v1

ModelProfile
Compiled Prompt Hash

默认不要展示完整 System Prompt。

如果已有 dev-only Prompt Preview API：

可以放在更深层 Debug。

禁止前端自行 reconstruct Prompt。

==================================================
二十五、Agent Inspector
==================================================

至少显示：

AgentTask
- Agent
- Task Type
- Status
- Attempt count

AgentRuns
- attempt
- status
- provider/model
- duration
- error if any

这样人工测试遇到：

“为什么停很久？”

可以判断是在：

Context
Queue
Model
Result Validation
Workflow

哪一层。

==================================================
二十六、Project / Chapter 创建
==================================================

如果已有 Backend API：

直接接。

只要求最小字段。

如果创建 Project 当前要求大量开发字段：

Test Console 可以提供合理开发默认值。

但：

不能绕过 Backend validation。

禁止前端直接 DB seed。

如果某些正式初始化 Workflow 尚未实现：

可以增加明确的：

DEV ONLY convenience action

但必须：

最终仍调用正式 Service/API

不能直接写数据库。

==================================================
二十七、Frontend API Layer
==================================================

建立清晰统一 API Client。

例如：

api/
├── client.ts
├── projects.ts
├── chapters.ts
├── workflows.ts
├── humanGates.ts
├── creativeBriefs.ts
├── plans.ts
├── writing.ts
└── debug.ts

实际结构可根据现有 API 调整。

统一处理：

base URL
JSON
errors
request-id
typing

禁止 Component 到处手写 fetch。

==================================================
二十八、TypeScript Types
==================================================

不要大量：

any

至少对核心 UI 数据定义：

Project
Chapter
Workflow
CreativeBrief
ChapterPlan
HumanGate
ChapterVersion
WritingResult
AgentTask
AgentRun
ContextPackage
PromptLineage
ApiError

如果 Backend 有 OpenAPI：

可以考虑生成或半自动同步 TypeScript 类型。

但不要为了本 Ticket 引入复杂 codegen pipeline。

==================================================
二十九、Backend 修改原则
==================================================

优先：

不修改 Backend。

先检查现有 API 是否足以支持 Console。

只有当出现：

后端已有数据，但完全没有安全读取入口

或者：

当前完整 Workflow 无法通过正式 API 驱动

才允许增加最小 Backend API。

新增 Backend API 必须：

- 只通过 Service
- 不直接 Repository from route
- 不绕过 authority
- 不绕过 HumanGate
- 不绕过 Workflow
- 不允许客户端伪造 actor
- 有测试

禁止为了前端方便增加：

POST /set-workflow-state
POST /approve-anything
POST /run-agent-directly
POST /set-approved-version

==================================================
三十、CORS / Local Development
==================================================

支持本地开发：

Frontend Vite
Backend FastAPI

优先使用：

Vite proxy

避免扩大 CORS 配置。

如果必须 CORS：

只添加本地开发允许来源。

不要：

allow_origins=["*"]

作为正式默认。

==================================================
三十一、Environment
==================================================

Frontend 提供：

.env.example

例如：

VITE_API_BASE_URL=/api

不要把：

Provider Key
Database URL
Secrets

放前端环境变量。

Frontend 绝对不能拿到：

LLM API Key。

==================================================
三十二、最小视觉要求
==================================================

不要花大量时间美化。

只要求：

- 信息层级清楚
- 正文可读
- JSON Debug 可折叠
- Error 显眼
- Human Action 明确
- 当前状态明显
- 不拥挤到无法测试

可以使用简单 CSS。

如果项目没有现成 UI library：

不要为了这个 Ticket 强制引入大型 UI framework。

==================================================
三十三、页面状态
==================================================

至少正确处理：

Initial

Loading

Empty

Processing

Waiting Human

Writing

Blocked

Failed

Draft Ready

不能所有异步状态都只显示：

Loading...

==================================================
三十四、Debug Mode
==================================================

建议通过：

VITE_ENABLE_DEBUG_PANEL=true

或等价 dev config

控制 Advanced 区。

Test Console 默认开发环境开启。

不要把 Debug 控件混成正式业务入口。

==================================================
三十五、必须测试的人工主流程
==================================================

UI 必须能够完整执行：

E2E-UI-A

Create / Select Project
↓
Create / Select Chapter
↓
Input Natural Language Requirement
↓
Start Workflow
↓
See Requirement Processing
↓
See CreativeBrief
↓
See ChapterPlan
↓
See HumanGate
↓
Approve
↓
See Writing
↓
See Chapter Draft

过程中：

测试人员不需要手工复制任何内部 ID。

==================================================
三十六、Plan Reject 流程
==================================================

E2E-UI-B

Natural Language Requirement
↓
Plan generated
↓
User Rejects:

“方案太保守，希望冲突更强，但不要改变结尾方向。”

↓
New Planning Iteration
↓
New Plan Version
↓
UI shows new Plan
↓
User Approves
↓
Writing

必须能看到：

Plan v1
Plan v2

旧版本不能消失或被原地覆盖。

==================================================
三十七、Request Alternative
==================================================

E2E-UI-C

Plan v1
↓
Request Alternative
↓
Plan v2
↓
展示新方案

不需要手工触发 Agent。

==================================================
三十八、Version Safety UI Test
==================================================

人为制造：

ChapterPlan:

approved = v1
current = v2 DRAFT

UI 必须明确显示。

如果尝试用过期 Gate 批准：

应显示 VERSION_CONFLICT，

不得：

假装成功。

==================================================
三十九、Failure UI Test
==================================================

用 Mock / Dev Scenario 制造一次：

Agent failure

UI 应显示：

FAILED / BLOCKED

而不是无限 loading。

Debug 区应能看到对应 AgentRun。

==================================================
四十、Tests
==================================================

至少实现：

Frontend Unit Tests / Component Tests
（按当前项目最轻量可行方案）

重点：

- API error handling
- Workflow state rendering
- CreativeBrief rendering
- Plan rendering
- HumanGate action payload
- Version conflict display
- Draft rendering
- Debug panel rendering
- Poll stop/start behavior

如果引入浏览器 E2E 工具不会明显扩大 Scope：

可以使用 Playwright。

至少建议有一个：

Happy Path Browser E2E

但如果环境成本较高，
不强制引入复杂测试基础设施。

==================================================
四十一、Backend Regression
==================================================

前端开发完成后：

Backend 全量 tests 必须继续 PASS。

不能为了 Console：

削弱：

authority
version
HumanGate
Workflow
Context
Prompt
Agent

安全规则。

==================================================
四十二、Frontend Quality
==================================================

至少执行：

npm / pnpm / current package manager install

typecheck

lint

build

tests

实际命令按创建的 frontend 工具链确定。

必须：

TypeScript build clean。

不要大量 ts-ignore。

==================================================
四十三、Docker
==================================================

如果当前 Docker Compose 已有：

backend
postgres

可以增加：

frontend

或者：

开发模式单独 Vite。

当前 Ticket 不要求生产级 nginx。

如果增加 Docker：

确保：

backend / postgres 既有服务不受破坏。

==================================================
四十四、README
==================================================

更新开发说明。

至少描述：

如何启动 Backend

如何启动 Frontend

如何配置 API

如何创建测试 Project

如何启动 Chapter Workflow

如何进行 Plan Approval

如何查看 Draft

如何打开 Debug Panel

==================================================
四十五、Scope Guard
==================================================

本 Ticket 完成后不得继续：

NOVEL-009

不要实现：

Quality Engine
Full Review Agent
Revision Agent
Human Chapter Acceptance
Memory Commit

即使 UI 中可以预留：

“Review unavailable yet”

也不能提前实现业务。

==================================================
四十六、独立 Code Review
==================================================

完成后进行一次独立只读 Review。

重点检查：

1. Frontend 是否绕过 Workflow
2. Frontend 是否绕过 HumanGate
3. Frontend 是否能伪造 actor
4. Frontend 是否直接写 approved state
5. Frontend 是否直接调用 Agent
6. Secret 是否泄露到 Browser
7. Error handling
8. Polling cleanup
9. Race / stale view
10. VERSION_CONFLICT UX
11. API typing
12. `any` 滥用
13. Backend security regression
14. Scope creep

Blocking / Required 问题必须修复。

==================================================
四十七、完成报告
==================================================

完成后生成：

docs/reports/DEV-UI-001-implementation.md

至少包括：

1. Implementation Summary
2. Purpose / Scope
3. Frontend Architecture
4. Page Structure
5. API Integration
6. Project / Chapter Selection
7. Requirement Input
8. Workflow Progress
9. CreativeBrief View
10. ChapterPlan View
11. HumanGate Interaction
12. Writing / Draft View
13. Version Display
14. Error Handling
15. Debug Panel
16. Context Inspector
17. PromptLineage Inspector
18. Agent Inspector
19. Polling / Refresh Strategy
20. Backend Changes
21. Frontend Tests
22. Browser E2E
23. Backend Regression
24. Build / Typecheck / Lint Result
25. Docker Result
26. Manual Test Instructions
27. Acceptance Criteria PASS / FAIL
28. Architecture Deviations
29. Known Issues
30. Deferred Items

完成以后停止。

不要开始 NOVEL-009。

==================================================
四十八、最终验收目标
==================================================

DEV-UI-001 完成后，

一个不熟悉 Novel OS 内部数据库/API 的人，

应该能够只通过浏览器完成：

“I want this chapter to ...”

↓

AI understands

↓

AI plans

↓

Human reviews Plan

↓

Human approves

↓

AI writes

↓

Human reads Draft

测试人员不应该需要知道：

workflow_id
gate_id
context_package_id
agent_task_id
state_version
artifact_version

这些系统细节由 Test Console 自动处理。

Debug 时才允许展开这些信息。

最终目标：

Make Novel OS testable as a product,
not merely callable as an API.