# NOVEL-002 — Core Domain & Persistence

**Priority:** P0  
**Depends On:** NOVEL-001

## Goal

落地第一批正式 Domain：

- Project
- Requirement
- Decision
- Lock
- Chapter
- ChapterPlan
- ChapterVersion

## Key Rules

- Requirement / Decision 分离
- Approved 数据 immutable
- 新修改产生新 version
- Approval 绑定具体 version
- Lock 必须在 Service 层真实生效
- Chapter.current_version 与 approved_version 分离
- Repository 不自行 commit
- API DTO ≠ ORM Model

## Required Tables

- projects
- requirements
- decisions
- locks
- chapters
- chapter_plans
- chapter_versions
- audit_records

## Critical Constraints

- `UNIQUE(project_id, chapter.sequence)`
- `UNIQUE(logical_id, version)` for versioned entities
- 同一 target 最多一个 active lock
- ChapterVersion content immutable
- expected_version 冲突返回 409

## Services

- ProjectService
- RequirementService
- DecisionService
- LockService
- ChapterService
- PlanningService

## Required APIs

- Projects CRUD minimal
- Requirements create/list/get/approve/supersede
- Decisions create/list/approve
- Lock / release
- Chapters create/list/get
- Chapter Plans create/list/get/approve
- Chapter Versions create/list/get/approve

## Acceptance Focus

必须验证：
- Approved Requirement 不可原地改
- Locked Decision 不可普通修改
- 新 ChapterVersion 不改变旧 approved_version
- stale approval 被拒绝
- 所有 approval / lock / version mutation 有 Audit
- migration upgrade/downgrade
- negative tests complete

## Exit Gate

只有版本、Lock、Approval、Transaction、Audit 都稳定后才进入 Workflow。
