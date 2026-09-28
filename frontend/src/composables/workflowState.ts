import type { Workflow, Task, ExecutionConfig } from '../types/models'

const names: Record<string, string> = {
  C00_CREATED: '已创建，等待提交需求', C01_REQUIREMENT_INTAKE: '正在理解需求',
  C02_CONTEXT_ASSEMBLY: '正在组装上下文', C03_REQUIREMENT_READY: '需求已整理',
  C04_CHAPTER_PLANNING: '正在生成方案', C05_PLAN_REVIEW: '正在检查方案',
  C06_PLAN_APPROVAL: '等待人工审批方案', C07_WRITING: '正在写作',
  C08_DETERMINISTIC_CHECK: 'Draft 已生成，本次测试流程结束',
  C09_INTERNAL_REVIEW: '正在审阅正文', C10_REVISION: '审阅完成，建议修改', C11_INTERNAL_PASS: '审阅完成',
  C90_BLOCKED: '流程受阻', C91_FAILED: '流程失败', C92_CANCELLED: '流程已取消',
}
export const stateLabel = (state: string) => names[state] ?? `当前阶段暂不提供操作（${state}）`
export const currentTask = (w: Workflow, tasks: Task[]) => tasks.find(t =>
  t.workflow_instance_id === w.id && t.workflow_state === w.current_state && t.workflow_state_version === w.state_version && !['SUCCEEDED', 'CANCELLED'].includes(t.status))
export const isReviewResume = (w: Workflow, tasks: Task[]) => !w.simulation && w.workflow_definition_id === 'chapter-planning' && w.workflow_definition_version === 3 && ['PAUSED', 'BLOCKED'].includes(w.status) &&
  (w.resume_state === 'C09_INTERNAL_REVIEW' || (w.resume_state === 'C08_DETERMINISTIC_CHECK' && tasks.some(t => t.workflow_instance_id === w.id && ['REVIEW_CHAPTER_COMPLIANCE', 'REVIEW_CHAPTER_NARRATIVE'].includes(t.task_type))))
export function resumeCallsModel(w: Workflow, config?: ExecutionConfig | null, tasks: Task[] = []): boolean {
  if (!config || config.provider === 'mock' || w.simulation) return false
  const taskTypes: Record<string, string> = { C01_REQUIREMENT_INTAKE: 'PARSE_CHAPTER_REQUIREMENT', C04_CHAPTER_PLANNING: 'PLAN_CHAPTER', C05_PLAN_REVIEW: 'REVIEW_CHAPTER_PLAN', C07_WRITING: 'WRITE_CHAPTER', C09_INTERNAL_REVIEW: 'REVIEW_CHAPTER_COMPLIANCE', C10_REVISION: 'PLAN_CHAPTER_REVISION' }
  const type = isReviewResume(w, tasks) ? 'REVIEW_CHAPTER_COMPLIANCE' : taskTypes[w.resume_state ?? w.current_state]
  return Boolean(type && (!config.task_types || config.task_types.includes(type)))
}
export function progressLabel(w: Workflow, tasks: Task[], config?: ExecutionConfig | null): string {
  if (w.status === 'PAUSED') return '流程已暂停'
  if (w.revision_request_id && w.current_state === 'C10_REVISION' && w.status === 'WAITING_AGENT') {
    const task = currentTask(w, tasks)
    if (task?.status === 'PENDING' && config?.task_types && !config.task_types.includes(task.task_type)) return '本阶段执行已停用'
    return task?.task_type === 'VALIDATE_REVISION_FIDELITY' ? '正在检查修改结果' : task?.task_type === 'REVISE_CHAPTER' ? '正在修改正文' : '正在分析修改范围'
  }
  if (w.revision_request_id && w.current_state === 'C09_INTERNAL_REVIEW' && w.status === 'WAITING_AGENT') return '正在重新审阅'
  if (w.status !== 'WAITING_AGENT' || !/^C0[1-9]_/.test(w.current_state)) return stateLabel(w.current_state)
  const task = currentTask(w, tasks)
  if (!task) return '等待任务调度'
  if (task.status === 'PENDING') {
    if (config?.task_types && !config.task_types.includes(task.task_type)) return '本阶段执行已停用'
    return task.attempt_count > 0 ? '等待后台重试' : '等待后台执行'
  }
  if (task.status === 'CLAIMED') return '任务已领取，准备执行'
  if (task.status === 'RUNNING') return stateLabel(w.current_state)
  return '任务已结束，正在同步流程状态'
}
export const isWritingWorkflow = (w: Workflow) => !w.simulation && w.workflow_definition_id === 'chapter-planning' && [2, 3].includes(w.workflow_definition_version)
export function pollDelay(w: Workflow | null, tasks: Task[] = [], config?: ExecutionConfig | null): number | null {
  if (!w || !isWritingWorkflow(w) || w.current_state === 'C00_CREATED' || w.current_state === 'C08_DETERMINISTIC_CHECK' ||
    /^C9/.test(w.current_state) || ['PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED', 'BLOCKED'].includes(w.status)) return null
  if (w.current_state === 'C10_REVISION' && w.revision_request_id && w.status === 'WAITING_AGENT') {
    const task = currentTask(w, tasks)
    return task?.status === 'PENDING' && config?.task_types && !config.task_types.includes(task.task_type) ? null : 1500
  }
  if (['C06_PLAN_APPROVAL', 'C10_REVISION', 'C11_INTERNAL_PASS'].includes(w.current_state)) return null
  const task = currentTask(w, tasks)
  if (task?.status === 'PENDING' && config?.task_types && !config.task_types.includes(task.task_type)) return null
  return (/^C0[1-7]_/.test(w.current_state) || (w.workflow_definition_version === 3 && w.current_state === 'C09_INTERNAL_REVIEW')) ? 1500 : null
}
export const stages = [
  ['需求', 1], ['Context', 2], ['Planning', 4], ['Plan Review', 5], ['人工审批', 6], ['Writing', 7], ['Draft', 8],
] as const
