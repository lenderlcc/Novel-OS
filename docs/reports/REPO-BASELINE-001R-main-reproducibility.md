# REPO-BASELINE-001R — Main Branch Reproducibility Verification

验证日期：2026-10-08。范围：001～014 的工程可复现性；真实模型行为与人工创作品质不在本次范围。

## 1. Executive Summary

原远端 main 存在 `TEST_DELIVERY_DRIFT`，不能复现此前完整工程验收。前端测试未交付，后端缺少正式回归与 support，部分已跟踪测试还在断言旧契约。

本次先实际验证未经修改的远端 main，再在 `fix/repo-baseline-001r` 补齐正式测试资产、移除一处历史 `.runtime` fixture 依赖并修正迁移说明。没有修改产品架构、Prompt、创作策略、业务 fixture 文本或依赖锁。

**原 origin/main = FAIL；修复候选 = PASS_WITH_WARNINGS。** 修复分支没有合并到 main；其结果不能归给原 main。真实 Provider 调用为 0。后端 1,799、前端 177、浏览器 16、Writing 离线 32 与历史契约专项 6 均实际通过；四项付费模型测试按 opt-in 跳过。

## 2. Remote Main Commit SHA

| 项目 | exact SHA / 状态 |
| --- | --- |
| 原工作区 HEAD / origin/main | `c8bda98e5aad53a5f1ca5260a0a81ac4957f3de6` |
| 实际远端 clean clone HEAD / origin/main | `c8bda98e5aad53a5f1ca5260a0a81ac4957f3de6` |
| 第一批资产；后端完整回归实际执行 source | `711a88a0f2efd1b00168d655770f5ae5fb7df96c` |
| Writing 工具复验实际 source | `0ea5724fc88b5ff813459094cfb173aad867a275` |
| Browser 最终语义定位修正；前端/浏览器复验 source | `9435fe5f30615f2809bac1ffbd27a014e2bac2e5` |
| 修复分支 | `fix/repo-baseline-001r`，未合并 |
| 本报告的后续提交 | 文档及验收记录；测试对应以上 source SHA |

已实际执行 status、branch、remote、fetch、HEAD/origin/main rev-parse 及 origin/main 最近五条日志。原工作区在 main，产品无未提交修改，但正式测试资产仍留在旧工作区。未改写任何已发布历史，没有 force push，也没有在原 main 开发。

## 3. Clean Clone / Worktree Method

本次使用实际 `git clone --branch main --single-branch git@github.com:lenderlcc/Novel-OS.git`，没有用旧工作区作为执行目录。

隔离验证根目录：`/Users/agiuser/novel-os/validation/repo-baseline-001r-20261008-91f22b22`。

| Checkout | 来源 / 用途 |
| --- | --- |
| `origin-main` | 直接 clone 远端 main，先验证原提交 |
| `fix` | 从原 main clean clone，创建指定修复分支，只准备正式资产与文档 |
| `verify-fix` | `git clone --no-local` 已提交的修复分支；重新安装依赖及完整后端/前端回归 |
| `verify-browser` | 第三个 clean clone；711 首次失败留存，后续 clean checkout 0ea5724 / 9435fe5 独立浏览器服务与数据库复验 |
| `verify-tools` | 0ea5724 的第四个 clean clone；新 venv 与独立 tools_test 执行正式离线 runner |

另一开发环境复验时，使用实际待验收 commit（原 main 或获确认后的修复分支），不要复制个人配置/运行结果。按 README 创建全新的开发验证库和独立 `_test` 库，填写新 `backend/config.toml`，默认 Mock、Provider Key 缺失，再执行：

```bash
git clone --branch main --single-branch git@github.com:lenderlcc/Novel-OS.git novel-os-baseline
cd novel-os-baseline
# checkout 实际待验收的 exact commit；当前 main 尚未含修复资产
cp backend/config.example.toml backend/config.toml
chmod 600 backend/config.toml
# 填写本次新建 PostgreSQL 验证库 / *_test；不使用个人开发库或真实 Key
cd backend
uv --no-cache sync --locked --python 3.13
uv run --locked alembic upgrade head
uv run --locked alembic downgrade -1
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked pytest tests -q -p no:cacheprovider
uv run --locked ruff check
uv run --locked ruff format --check
cd ../frontend
npm ci
npm test
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Docker 使用 README 的 fresh `prepare_docker` 和 build/health 步骤。并发回归与 browser/aux runner 应分配不同 `_test` 数据库或顺序执行；不把本次机器上的 SSH、PG 凭据、旧 venv/node_modules/runtime 当作移植资产。

每个验证 checkout 初始 Git status 为空，不存在 `.venv`、`node_modules` 或历史 `.runtime`。本次新生成的 keyless TOML、Docker 挂载配置和运行结果是验证产物，不是来自原工作区的输入。原工作区测试只作为修复资产的来源；最终测试读取的是已提交文件的另一次 clean clone。

## 4. Git Tracked Test Assets

| 正式资产 | 原 main | 修复提交 |
| --- | ---: | ---: |
| Backend tests/support/fixture 文件 | 66 | 131 |
| Backend pytest modules | 55 | 117，完整 collection 见第 7 节 |
| Frontend unit tests/support/fixture | 0 | 15（13 个测试文件） |
| Frontend browser specs / host | 0 | 7（6 个 specs + host） |
| Playwright config | 0 | 1 |
| Writing 离线 runner / lineage audit | 0 | 2 |
| E2E-001 fixtures/runner/docs | 13 | 13，未改变 |
| NOVEL-013 eval fixtures/templates | 5 | 5，未改变 |
| NOVEL-014 eval fixtures/templates | 5 | 5，未改变 |

精确纳入 89 个缺失正式文件、15 个已跟踪测试更新，另新增 1 个稳定历史契约 fixture；加上 README，共 106 个文件。没有纳入旧运行日志、个人密钥、缓存、DS_Store、旧 venv/node_modules 或整套 `.runtime`。

资产 SHA manifest：`2759a4380949f447bf3520a365e72fe6702823178a07903e3f103f1eb51b13d1`。静态闭包审阅确认测试 import、共享 factories、fixture 和 runner 所需文件都已跟踪。

## 5. Repository Completeness

原 main 完整性 **FAIL**：缺少 009～014 正式回归、前端回归及 README 已引用的 Writing 离线工具。已有产品源码、migration、Prompt 库、Context/Quality profile、E2E/013/014 场景与锁文件完整。

修复提交补齐正式工程资产。历史契约回归原来读取 `.runtime/validation001/runtime-task-contract-audit.json`，现在读取稳定的 `backend/tests/fixtures/historical-contract-pins.json`。

该 fixture 从已提交历史源码 `38de644b835ae06eed82b39a9959a11f5b0d6d9b` 的 Git archive 生成：历史 Pydantic Schema 经历史 Task Registry 计算 schema hash，历史 Prompt Registry 读取 immutable module pin。只保存六类任务需要的旧 schema/hash/task-prompt pin；不读取旧 runtime，不用当前契约重新定义旧期待。独立审阅重新生成并逐项确认一致。

fixture SHA：`3c3cddf0c918f94c906ef7486eebbb25d7909e574bd1ec89a55aea68efd1e934`。原测试 assertions 保留，仅替换输入路径与 pin 读取方式。

## 6. Dependencies / Lockfiles

| 项目 | 实际验证 |
| --- | --- |
| Host Python | 3.13.12；项目声明 >=3.12,<3.15 |
| Docker Python | 3.13.16，当前 `python:3.13-slim`，满足 locked Python 范围 |
| uv | 0.9.30 |
| Backend | 新 `.venv`，`uv --no-cache sync --locked --python 3.13` 成功 |
| Backend lock | `backend/uv.lock` 已跟踪，未改变 |
| Node / npm | 22.22.0 / 10.9.4 |
| Frontend | 每个 checkout 新 `node_modules`，`npm ci` 成功 |
| Frontend lock SHA | `79cfbcec87122ad273adf7e6906770eb06d8ca957c35362ec729bb3ce63714fd` |
| PostgreSQL | 新隔离容器 16.15，tmpfs 数据目录 |

两套 backend 新环境锁定包一致，包括 SQLAlchemy 2.0.52、Pydantic 2.13.5、Pydantic Settings 2.15.0、FastAPI 0.141.1、Alembic 1.19.2、pytest 9.1.1、ruff 0.16.6。没有升级依赖或修改锁文件。Docker backend/worker 的 27 个运行依赖一致。

`npm ci` / `npm audit` 返回一项已有间接依赖 `source-map-js` high advisory（GHSA-68fv-2mgg-jv7q）；安装与工程门禁正常，锁文件未调整。此安全告警保留为已知问题，不等于本次工程测试失败，也没有声称完成安全修复。

## 7. Backend Full Regression

| 完整执行 | 原 origin/main `c8bda98` | 修复 clean clone `711a88a` |
| --- | ---: | ---: |
| Collected / unique / JUnit records | 784 / 784 / 784 | 1,803 / 1,803 / 1,803 |
| PASS | 750 | 1,799 |
| FAIL / ERROR | 31 / 0 | 0 / 0 |
| Real-provider opt-in SKIP | 3 | 4 |
| Exit code | 1 | 0 |
| 实际运行时间 | 579.04 秒 | 2,091.91 秒 |
| Full suite requested / completed | true / true | true / true |
| 外部网络尝试 / real calls | [] / 0 | [] / 0 |

修复资产使实际 collection 从 784 增为 1,803；新增的 Requirement 单次真实模型 opt-in 用例解释 SKIP 从 3 增为 4。修复后实际数量与此前 1,799 PASS / 4 SKIP 一致，但这里记录的是新的完整运行，未复制旧结果。四项 SKIP 分别为 paid Planning、单次 Requirement、paid Writing、live OpenAI；没有其他跳过。

原 main 与修复 clean clone 的 `ruff check`、`ruff format --check` 均 PASS（397 / 461 文件）；已有两个第三方 deprecation warnings 不影响 exit code。`git diff --check` PASS。

完整运行使用该 checkout 的新 `.venv` 和已有 pytest 配置：`pytest tests -q -p no:cacheprovider --junitxml=...`，没有按失败用例选择性重跑、deselect、改变 markers 或忽略失败。Strict markers / `-ra` 由原 pyproject 生效。

本次外部验证脚本只增加 keyless Mock 配置断言、实际 HTTP/socket 外连阻断、独立 Mock `--once` 子进程配置检查及 collection/exit code 收据；不改业务测试、输入、期望、顺序或返回码。收集列表、JUnit、命令、开始/结束时间和 source SHA 分别留存。

首次运行受 SSH 桥失效及验证脚本 str/Path 类型错误影响，证据以 `*-env-interrupted*` 单独保存；它们不作为最终产品结论。恢复后重新初始化本任务独立测试库，并从头完整重跑。

## 8. Frontend Regression

| 命令 | 原 origin/main | 修复 clean clone |
| --- | --- | --- |
| `npm ci` | PASS，新安装 | PASS，新安装 |
| `npm test` | FAIL：No test files found，0 tests | PASS：177 / 13 files，0 fail / skip（最终9435fe5重新执行） |
| `npm run lint` | PASS | PASS |
| `npm run typecheck` | PASS | PASS |
| `npm run build` | PASS，67 modules | PASS，67 modules |

新的 177 个实际通过用例覆盖 Workspace、导航、Profile、Exploration Debug、Draft selector、Review、Revision、Feedback、Memory 等现有功能；没有复制历史结果。前后 tracked frontend SHA 一致。

完整浏览器在单独 `verify-browser`、新 `repo_baseline_browser_test`、测试端口 8011/5174、tracked Mock host 中实际运行 **16 PASS / 0 FAIL / 0 SKIP / 0 flaky**（source `9435fe5`，81.741 秒）。85 次 Mock，0 real / forbidden / external。没有复用旧 13-check smoke 作为本次 full-suite 结果。

首次711为12 PASS / 4 FAIL，第二次0ea为15 PASS / 1 FAIL，两次完整失败、trace、截图及源 SHA 均保存。测试端口已关闭；Playwright 的 SIGTERM 未触发 host 的 finally schema 清理，本次仅手动清除所拥有的 browser UUID schema，最终0表；不宣称自动 cleanup PASS。

## 9. Integration / E2E

完整后端回归中的 `test_checkpoint_phase2.py` **5 PASS**、`test_multi_chapter_continuity.py` **1 PASS**、`test_validation001_runtime_contract.py` **41 PASS**。单章 full Recorded slice 与五章 Workflow 场景均实际完成，不把辅助专项结果重复累加到 1,799。

本次 clean run 新生成三份 checkpoint compatibility 记录（legacy 13、exploration-only 14、exploration-and-profile 14 个 Context sample）及一份含五章的 `e2e001-offline-trace.json`，已附 source SHA 与 SHA256 manifest 留存。

单章 Phase 2 兼容性回归包含 legacy、exploration-only、exploration-and-profile 三种路径；在正常 Workflow、Human Gate fixture、Service 与 Worker 路径中执行 Requirement → Exploration → Planning → 人工审批 fixture → Writing → Review → Revision / Feedback Revision → Finalization → Memory Commit → Next Chapter。

五章工程场景验证 Canon continuity、状态转换、知识防火墙、Belief vs Truth、Open Thread、Draft/Revision 隔离和 Context retrieval，包含完整 lineage 核对。Recorded/Mock 输出只替代模型返回，不以直接插入业务结果冒充 Workflow E2E。初始人物/画像 fixture 不等于跳过生产链路。此结果不证明真实模型创作品质。

补齐的 Writing 离线 runner 从已跟踪 W001～W008 fixtures 选择既有测试节点，并复用 read-only lineage audit，不新增产品路径。

该 runner 在新 clean clone `verify-tools`、fresh locked venv、新空 `repo_baseline_tools_test` 中实际复验 **32 PASS / 0 FAIL / ERROR / SKIP**（source `0ea5724`），包含 15 个 PASS Draft 与 9 个 BLOCKED/no-Draft WritingResult。24 个结果的 Plan / ContextPackage / PromptLineage / AgentTask / AgentRun / ModelProfile / WritingResult 全部绑定一致，Prompt 重编译与严格 metadata 校验通过。实际 CP-005.v7 的 id/version/hash 对齐 immutable binding，不查询 latest。

同一 clean clone 中 6 项历史契约 pin 专项 **6 PASS**，运行前后没有旧 `.runtime` 输入；它们是专项复验，最终 full-suite 计数不重复累加。

## 10. NOVEL-013 / 014 Regression

完整回归实际结果（均包含在 1,799 中）：

| 模块 | PASS |
| --- | ---: |
| Creative Exploration Workflow | 31 |
| Exploration Context | 10 |
| CharacterProfile Context | 27 |
| CharacterProfile 本地 Service/API | 28 |
| CharacterProfile Interpretation Lineage | 13 |
| CharacterProfile Contract | 18 |
| CharacterProfile POV regressions | 3 |
| Context/Authority validation | 27 |
| 带历史数据 Phase 2 migration | 1 |

上述模块及单章/五章 E2E 的 assertion 全部通过；不将辅助 runner 与 full-suite 同一节点的复验相加。

验收项目：Candidate=A7；未选择 Candidate 不进入 Writer/Memory；只选择 approved CharacterBehaviorProfile；Draft Profile 不泄漏；Relationship Modifier 按相关人物筛选；Character Profile 不绕过 Knowledge Firewall；无 Profile 历史项目兼容；Profile 更新触发 freshness 保护。

本次修复没有改 Exploration Prompt、Candidate Policy、Writing Prompt、Character Voice Prompt 或 Memory Retrieval。已有 E2E/013/014 fixture 原文与基线哈希保持一致。

## 11. Migration

实际 head 是 `0021_writing_output_contract`，前驱 `0020_character_report_lineage`。分别在原 main 的 `repo_baseline_migration_test` 和修复提交的 `repo_baseline_fix_migration_test` 执行：

| 操作 | 原 main / Docker 环境 | 修复 clean clone / Host 环境 |
| --- | --- | --- |
| upgrade head | PASS，0021 | PASS，0021 |
| downgrade -1 | PASS，0020 | PASS，0020 |
| upgrade head | PASS，0021 | PASS，0021 |
| alembic check | PASS，无新 operations | PASS，无新 operations |

README 原来的“当前 head 0007”已修正为动态 `alembic heads/current`，保留 0007 的历史说明。所有回滚都只作用于本任务独立迁移库，没有对用户开发库执行 downgrade。带历史数据的合法 guard 由正式 migration regression 检查。

## 12. Docker

**原 origin/main 实际构建与容器验证 PASS**：backend、worker 分别从 clean source `--no-cache build` 成功；backend 非 root 启动，health / health-db 均 200 且有 request ID，migration compatible。

独立 internal network、tmpfs PG、只读挂载新 keyless 配置；没有启动付费 Worker 处理用户任务。Worker 只执行 `--help`，网络为 `none`。没有重启用户已有应用。

493 个产品/迁移文件逐 SHA 与原 Docker 两个 role 完全一致。修复提交这 493 个文件也逐 SHA 一致：这是产品同源证明，**不冒充修复分支重新 build**。本次变化仅为正式测试与文档，镜像产品内容没有变化。

初次 Docker Hub anonymous token timeout 按已有 README 的先 pull 步骤恢复，未改产品。

## 13. Real Provider Calls

**REAL PROVIDER CALLS = 0。** 该结论由 keyless Mock 配置、实际 transport/outbound guard、子进程限制及浏览器共同 Provider 入口 guard 联合验证，不是 Provider 账单计数。 所有新 TOML 使用 `mock-default`、Provider Key 字段缺失；没有读取、复制或使用原个人密钥。测试中的 Provider transport 是 Mock/Recorded，真实物理 HTTP/socket 外连由验证护栏阻断。子进程只允许明确 keyless Mock 的独立 `_test` 配置。

未运行 E2E-001R、NOVEL-013R、NOVEL-014R，未启动真实付费 Worker。没有付费 API opt-in、没有消费模型额度。

## 14. Problems Found

| 分类 / 问题 | Failure → Root Cause | Minimal Fix → Regression |
| --- | --- | --- |
| A / TEST_DELIVERY_DRIFT | 远端缺正式后端/前端测试与 support；此前“不提交测试”策略留下交付缺口 | 精确补齐 89 文件 + 15 已发布契约的测试更新；committed clean clone 完整复验 |
| A / 隐藏 runtime fixture | 历史契约测试把一次运行输出当稳定输入 | 从已提交历史源码冻结最小正式 fixture；原 assertion 保留；干净环境执行 |
| A / Writing runner 缺失 | README 引用的两个离线工具未跟踪 | 补齐已有工具；复用现有 cases/pytest/lineage 链路 |
| C / 旧测试契约断言 | 已发布的 schema、prompt、profile、migration chain 改变而对应测试未交付 | 对照实际公开契约与兼容性路径纳入既有更新，不放宽 Authority 或改产品 |
| C / README head 过时 | “当前 0007”是历史说明 | 用 heads/current 查询，明确隔离迁移验证 |
| D / Docker Hub / Colima | 镜像 token 初次超时；host 55441 forwarding 拒绝连接 | 已有先 pull 说明 + 验证专用 SSH，不重构应用 |
| D / 验证桥生命周期 | 前台工具会话回收导致中途数据库连接拒绝，PG 本身正常 | 独立后台 SSH daemon；两次污染 run 独立归档；新空测试库完整重跑 |
| 验证工具 / 路径类型 | guard 为 Settings.from_file 传 str 而不是 Path，引入两项假失败 | 修改 checkout 外验证脚本，不改产品/测试期望；独立审阅后全量重跑 |

原 main 最终 31 项失败均属 C：5 项当前 Profile/Schema pin、1 项前章原正文隔离期待、11 项 PlanReview cross-field invariant、7 项非法 Writer operation 提前 Schema 拒绝、5 项历史 migration 快照/当前 head 断言、2 项 Requirement fixture envelope/result confidence 不一致。独立审阅逐项对照已发布源码，未发现这 31 项中有需要放松产品约束的正确性问题。

补齐资产后的额外实际复验又发现两类 C：browser source711 首次 16 项为 12 PASS / 4 FAIL（旧 Draft 文本和旧阶段断言）；Writing 离线 runner 首次 32 项为 9 PASS / 23 hook FAIL，32 个业务测试 body 全部 PASS，23 个 hook 均因工具硬编码 CP-005.v3。后续修复只对齐 test/support 的真实 Writer lineage 与 immutable bound Profile，不调整产品、场景原文或当前创作策略。第二 browser 全套（source0ea）为 15 PASS / 1 FAIL，旧共享 CSS selector 匹配三个区域造成 strict-mode failure；只改为正文审阅的唯一语义 region，原正文内容与 metadata 不泄漏断言保留，再独立复验。

## 15. Fixes Required / Applied

已提交修复 `711a88a`：正式资产交付、历史契约 fixture、迁移文档。后续兼容修正 `0ea5724fc88b5ff813459094cfb173aad867a275` 仅三个文件：两份 browser spec 与已有 Writing lineage audit。浏览器保留版本/DRAFT/approval 指针及真实 Writer Context/Prompt hash；离线工具复用现有 ContextProfile parser 与 Registry 校验绑定的 id/version/hash，绝不取 latest。产品源码、业务模型、数据库 migration、Prompt、Authority、Memory 查询和依赖锁无变化。另 `9435fe5` 只对正文审阅 browser assertion 使用唯一语义区域，消除共享 CSS selector 的多区域歧义。不删除原工作区未提交文件，不覆盖个人 TOML。

新测试资产不是新功能实现；本 Ticket 明确授权補齐正式工程资产。临时日志与整套历史 `.runtime` 不纳入版本管理。

复验后续提交时，后端完整执行仍在原 immutable `711a88a` checkout；`0ea5724` / `9435fe5` 仅改两份 browser spec 与独立复验的 Writing 工具。后端产品、测试、fixtures、运行 profiles 和 locks 的 Git blob input closure 完全一致，逐文件证据单独保存。不能把新 SHA 描述成“已重新执行完整后端”；各命令实际 execution SHA 在收据中明确记录。

需要用户 Review 后确认合并该分支，并对合并后的 **新 origin/main exact SHA** 做复验，才能让 main 成为绿色可复现基线。当前未发布到 main 的修复不能替代原 main 的 FAIL。

## 16. Local vs Clean Comparison

| 来源 | 工程结果的用途 |
| --- | --- |
| 历史旧工作区 1799 PASS / 4 SKIP、前端 177 | 仅识别应交付资产范围，不作为本次证据 |
| 原远端 clean clone | 本次原 main 实际结果，第 7/8 节 |
| 已提交修复的 clean clone | 本次修复实际结果，独立列示，不归给 c8bda98 |

原工作区 143 个初始 dirty/untracked 文件及个人配置仅比较 SHA，全部保持原样；原 main 与 origin/main 指针未移动。正式测试来源的文件哈希已保留，最终执行目录的 tracked 文件哈希单独记录。

## 17. Known Environment Limitations

Colima 本机端口转发不可靠，本次通过只属于验证环境的后台 SSH 桥连接新 PG。另一台机器若 Docker port forwarding 正常，按 README 的独立测试库即可运行，无须复制本机 SSH 或个人配置。

Docker Hub 首次下载依赖网络，已恢复。浮动 `python:3.13-slim` / `postgres:16-alpine` 标签不保证未来字节级镜像一致，本次记录实际版本与 image digest；Python/Node 应用依赖由现有 locks 固定。没有把镜像基础层浮动等同于应用测试不完整。

浏览器测试宿主在 SIGTERM 后未执行 finally 自动 schema 清理；本次完整记录并仅手动清除自己拥有的测试 schema，最终0表、测试端口关闭，不涉及用户库。

已有 `source-map-js` high npm audit 告警未在本 Ticket 升级修复。后端另有 Starlette TestClient/httpx 与 anyio BlockingPortal 的两项第三方 deprecation warnings，未因此改锁文件。真实模型行为与人工 prose evaluation 保持待验收。

## 18. Independent Review

独立审阅 **REVIEW_COMPLETE**：Ticket 第十八节十二项均已核对，原 main FAIL、候选 PASS_WITH_WARNINGS，可交用户 Review；本次范围内没有未解决产品正确性阻塞。

审阅者独立交叉解析原/fix collection、JUnit node set、guard 与全部 proof hash；重新实际比对 792 / 882 个 tracked 文件、143 个原 dirty/untracked/个人配置 hash、六类历史契约 pin、十三类当前任务契约及七份本次新 E2E 输出。真实执行 SHA、Docker 同源限制、三项真实验收 PENDING 和警告在最终报告中均准确。只推送指定 fix 分支供 Review 符合第十六节；main 合并仍待用户确认。

机器可读审阅 `independent-review.json` SHA256：`6970e4df1175ee625f1a6ec81e0bccb01cfa02ab9c528c1fd0fd6513c5fddb16`；Markdown 审阅 SHA256：`c47b567c1a1aaca78bcccf970fecf523039f0281711520161277232693e96b2e`。

独立审阅者使用 fresh context，只读核查，不运行真实模型。发现并纠正验证脚本的 str/Path 错误与 full-suite 摘要判定问题；测试自身没有被跳过或改写。审阅记录保留于本次独立 artifacts。

## 19. Pending Real Acceptance

E2E-001R、NOVEL-013R、NOVEL-014R = **REAL ACCEPTANCE PENDING**。Recorded/Mock 的工程 PASS 不构成真实模型行为 PASS 或人工创作品质 PASS。需要用户另行显式触发真实模型与人工验收。

未开始 NOVEL-015、016、017。

## 20. Final Result

**REPO-BASELINE-001R = FAIL（对本次实际验证的远端 origin/main `c8bda98`）。**

回答“今天换一台电脑 clone 当前 origin/main，是否可得到同样可信的完整工程测试结果”：**NO**，正式资产未交付且前端测试无法运行。

**修复候选 `9435fe5` = PASS_WITH_WARNINGS。** 后端完整执行 SHA 为 `711a88a`；其 747 个 backend execution input closure 文件与 `9435fe5` 完全相同。Writing 工具实际执行 `0ea5724`，该工具在 `9435fe5` blob 未改变；前端与完整浏览器实际执行 `9435fe5`。每一项结论对应实际执行收据，没有声称新 SHA 重新跑过后端完整命令。

候选剩余警告：已有 npm 间接依赖 advisory、第三方 deprecation、浏览器宿主退出清理限制与本机 Colima/Docker 网络限制。没有发现本次已验证范围内未解决的产品正确性阻塞。main 仍须用户 Review / 合并并复验新 exact SHA，才能改变原 main 的 FAIL 结论。

修复等待用户 Review / 合并确认，依据本 Ticket 第十六节“不允许直接在 main 上继续开发”“待用户确认后再合并”，不自动合并 main。所有新验证日志、JUnit、collection、hash manifest、隔离证明和独立 Review 保留在上述验证根目录的 `artifacts/`；不把旧日志当作本次证据。关键收据 SHA256 如下，便于核对原始材料：

| 新验证收据 | SHA256 |
| --- | --- |
| `backend-origin-result.json` | `b2cf458ca10b0bfdef53002899697946ea874553181f2aadc27e481e1c125f16` |
| `backend-fix-result.json` | `453e3ff5a4eed0c3cdd6f0f9c7898f5c069dfbcc30e9d7238b99e30f39a28cb0` |
| `backend-input-equivalence.json` | `f28c76ec682edd01d3f8f5504f23d516254fbc5b6b556452ab46e083178f1eb5` |
| `engineering-e2e-manifest.json` | `9c12bdd2149c5a54251dff0ee448f1631218eada0c0dc7a9bbf27f7629eb877b` |
| `frontend-latest.json` | `ec0e2db2ca4adc12095d06e371e8d99b26aaf1f2a6c3ef3efe50c243cd64ce54` |
| `browser-final.json` | `225d6e83ec536989665a57d1e6aa18bf775f152746e6a03b71b2e4e4be74452a` |
| `migration-fix.json` | `47f200c652a1bfd99c52bef073229ebcc1468a13208dfc154ea60b98464c7ad9` |
| `workspace-integrity.json` | `d149ba0c460c9afb3f0f5d541c0bd8d6244549e491a79c2eadb56e6e0667c28e` |

验证资源清理 **PASS**：两只专属容器、internal network、两只任务镜像标签与验证 SSH daemon 已按精确身份清理，8 条变更命令全部 exit 0。四个执行测试库最终0表，两个迁移验证库40表；全部随专属 PG 的 tmpfs 释放。用户 8000 / 5173 应用 PID、Colima、非任务容器与共享基础镜像保持原样。全部 source、日志、收据保留。

- `independent-review.json` SHA256：`6970e4df1175ee625f1a6ec81e0bccb01cfa02ab9c528c1fd0fd6513c5fddb16`。
- `independent-review.md` SHA256：`c47b567c1a1aaca78bcccf970fecf523039f0281711520161277232693e96b2e`。
- `cleanup-final.json` SHA256：`aedd909e04f513a25bb387f10437538ab5f4b069be1424dbf526cebf200d788e`。
- `cleanup-final.md` SHA256：`d4cbd86e5d91d84077e8c7bf79b16f2a65bb6539ab6abaf1b07f72ef04e9403a`。
